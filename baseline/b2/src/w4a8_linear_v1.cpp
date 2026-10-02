// B2 首版可综合 W4A8 线性核。
// 目标是先验证打包布局、INT32 部分和、逐组缩放和错误语义，不追求最终吞吐率。

#include "w4a8_linear_v1.hpp"

namespace {

// 四舍五入到指定 tile 的整数倍，调用前保证 value 为正且不会溢出。
std::uint32_t round_up(std::uint32_t value, std::uint32_t tile) {
    return ((value + tile - 1U) / tile) * tile;
}

// 将四位二进制补码扩展为八位有符号整数。
std::int8_t decode_w4(std::uint8_t nibble) {
    const std::int32_t decoded =
        (nibble < 8U) ? static_cast<std::int32_t>(nibble)
                      : static_cast<std::int32_t>(nibble) - 16;
    return static_cast<std::int8_t>(decoded);
}

// 写回一次调用的可审计状态；成功计数只由成功路径递增。
void write_meta(
    w4a8_b2::KernelMeta* meta,
    std::uint64_t previous_completed_count,
    std::uint64_t job_id,
    std::uint32_t status,
    std::uint32_t done,
    std::uint64_t algorithm_weight_bytes,
    bool increment_completed_count) {
    meta->abi_magic = w4a8_b2::kAbiMagic;
    meta->kernel_build_id = w4a8_b2::kKernelBuildId;
    meta->job_id = job_id;
    meta->status = status;
    meta->done = done;
    meta->hw_completed_count = previous_completed_count +
                               (increment_completed_count ? 1ULL : 0ULL);
    meta->algorithm_weight_bytes = algorithm_weight_bytes;
}

// 在正式计算前按打包字节顺序检查有效权重中的保留码 -8。
// 同一字节的两个 lane 共用一次读取；填充的 K 和 N 不参与检查。
bool contains_invalid_w4(
    const std::uint8_t* w_packed,
    std::uint32_t n,
    std::uint32_t k,
    std::uint32_t group_count) {
    bool invalid = false;
    const std::uint32_t output_block_count =
        (n + w4a8_b2::kOutputTile - 1U) / w4a8_b2::kOutputTile;

    for (std::uint32_t output_block = 0; output_block < output_block_count;
         ++output_block) {
        const std::uint32_t output_first = output_block * w4a8_b2::kOutputTile;
        const std::uint32_t outputs_left = n - output_first;
        const std::uint32_t valid_lanes =
            (outputs_left < w4a8_b2::kOutputTile) ? outputs_left
                                                 : w4a8_b2::kOutputTile;
        const std::uint32_t valid_bytes = (valid_lanes + 1U) / 2U;
        const bool odd_tail = (valid_lanes & 1U) != 0U;

        for (std::uint32_t group = 0; group < group_count; ++group) {
            const std::uint32_t inputs_left = k - group * w4a8_b2::kGroupSize;
            const std::uint32_t valid_inputs =
                (inputs_left < w4a8_b2::kGroupSize) ? inputs_left
                                                    : w4a8_b2::kGroupSize;
            const std::uint64_t group_base =
                (static_cast<std::uint64_t>(output_block) * group_count + group) *
                w4a8_b2::kGroupSize * 16ULL;

            for (std::uint32_t remainder = 0; remainder < valid_inputs;
                 ++remainder) {
                const std::uint64_t input_base = group_base +
                                                 static_cast<std::uint64_t>(remainder) *
                                                     16ULL;

                for (std::uint32_t packed_lane = 0; packed_lane < valid_bytes;
                     ++packed_lane) {
#pragma HLS PIPELINE II = 1
                    const std::uint8_t packed_byte =
                        w_packed[input_base + packed_lane];
                    const bool low_invalid = (packed_byte & 0x0FU) == 0x08U;
                    const bool high_valid = !odd_tail || packed_lane + 1U < valid_bytes;
                    const bool high_invalid =
                        high_valid && (packed_byte & 0xF0U) == 0x80U;
                    invalid = invalid || low_invalid || high_invalid;
                }
            }
        }
    }

    return invalid;
}

}  // namespace

// 按正式字节布局读取一个输出 lane 和一个 K-group，并产生 bit-exact INT32 部分和。
std::int32_t w4a8_group_sum(
    const std::uint8_t* w_packed,
    const std::int8_t* xq,
    std::uint32_t output_block,
    std::uint32_t output_lane,
    std::uint32_t group,
    std::uint32_t group_count,
    std::uint32_t token,
    std::uint32_t padded_k) {
    std::int32_t sum = 0;

    for (std::uint32_t remainder = 0; remainder < w4a8_b2::kGroupSize; ++remainder) {
#pragma HLS PIPELINE II = 1
        const std::uint64_t byte_offset =
            (((static_cast<std::uint64_t>(output_block) * group_count + group) *
                  w4a8_b2::kGroupSize +
              remainder) *
                 16ULL) +
            output_lane / 2U;
        const std::uint8_t packed_byte = w_packed[byte_offset];
        const std::uint8_t nibble =
            (output_lane % 2U == 0U) ? (packed_byte & 0x0FU)
                                     : ((packed_byte >> 4U) & 0x0FU);
        const std::int8_t weight = decode_w4(nibble);
        const std::uint64_t activation_index =
            static_cast<std::uint64_t>(token) * padded_k +
            group * w4a8_b2::kGroupSize + remainder;
        const std::int8_t activation = xq[activation_index];

        sum += static_cast<std::int32_t>(weight) *
               static_cast<std::int32_t>(activation);
    }

    return sum;
}

// HLS 顶层：使用 AXI4 master 读取五类数据缓冲，使用 AXI4-Lite 接收控制参数。
extern "C" void w4a8_linear_v1(
    const std::uint8_t* w_packed,
    const float* sw,
    const std::int8_t* xq,
    const float* sx,
    float* y,
    w4a8_b2::KernelMeta* meta,
    std::uint32_t t,
    std::uint32_t n,
    std::uint32_t k,
    std::uint64_t w_bytes,
    std::uint64_t sw_bytes,
    std::uint64_t x_bytes,
    std::uint64_t sx_bytes,
    std::uint64_t y_bytes,
    std::uint64_t meta_bytes,
    std::uint64_t job_id,
    std::uint32_t abi_version) {
    // depth 以“端口元素个数”为单位，覆盖当前 B2 联合仿真向量的最大缓冲。
    // 它只决定 cosim 包装器的固定拷贝窗口；板端运行时容量仍由地址和 *_bytes 校验决定。
#pragma HLS INTERFACE m_axi port = w_packed offset = slave bundle = gmem_w depth = 4096
#pragma HLS INTERFACE m_axi port = sw offset = slave bundle = gmem_sw depth = 64
#pragma HLS INTERFACE m_axi port = xq offset = slave bundle = gmem_x depth = 256
#pragma HLS INTERFACE m_axi port = sx offset = slave bundle = gmem_x depth = 1
#pragma HLS INTERFACE m_axi port = y offset = slave bundle = gmem_y depth = 64
#pragma HLS INTERFACE m_axi port = meta offset = slave bundle = gmem_meta depth = 1

#pragma HLS INTERFACE s_axilite port = w_packed bundle = control
#pragma HLS INTERFACE s_axilite port = sw bundle = control
#pragma HLS INTERFACE s_axilite port = xq bundle = control
#pragma HLS INTERFACE s_axilite port = sx bundle = control
#pragma HLS INTERFACE s_axilite port = y bundle = control
#pragma HLS INTERFACE s_axilite port = meta bundle = control
#pragma HLS INTERFACE s_axilite port = t bundle = control
#pragma HLS INTERFACE s_axilite port = n bundle = control
#pragma HLS INTERFACE s_axilite port = k bundle = control
#pragma HLS INTERFACE s_axilite port = w_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = sw_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = x_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = sx_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = y_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = meta_bytes bundle = control
#pragma HLS INTERFACE s_axilite port = job_id bundle = control
#pragma HLS INTERFACE s_axilite port = abi_version bundle = control

    // 显式固定握手控制协议，避免 Vitis kernel 流默认改成 ap_ctrl_chain。
#pragma HLS INTERFACE ap_ctrl_hs port = return
#pragma HLS INTERFACE s_axilite port = return bundle = control

    // meta 不可写时无法可靠返回任何错误，因此直接结束调用。
    if (meta == nullptr || meta_bytes < sizeof(w4a8_b2::KernelMeta)) {
        return;
    }

    const std::uint64_t previous_completed_count = meta->hw_completed_count;

    write_meta(
        meta,
        previous_completed_count,
        job_id,
        w4a8_b2::kStatusOk,
        0U,
        0ULL,
        false);

    // ABI 不匹配时不读取其他数据缓冲，也不改写输出。
    if (abi_version != w4a8_b2::kAbiVersion) {
        write_meta(
            meta,
            previous_completed_count,
            job_id,
            w4a8_b2::kStatusBadAbi,
            1U,
            0ULL,
            false);
        return;
    }

    // 首版容量覆盖 T<=8 及 Qwen2.5-0.5B 目标 MLP 的最大 N/K。
    if (t == 0U || t > w4a8_b2::kMaxT || n == 0U || n > w4a8_b2::kMaxN ||
        k == 0U || k > w4a8_b2::kMaxK) {
        write_meta(
            meta,
            previous_completed_count,
            job_id,
            w4a8_b2::kStatusBadDimension,
            1U,
            0ULL,
            false);
        return;
    }

    const std::uint32_t padded_k = round_up(k, w4a8_b2::kGroupSize);
    const std::uint32_t padded_n = round_up(n, w4a8_b2::kOutputTile);
    const std::uint32_t group_count = padded_k / w4a8_b2::kGroupSize;
    const std::uint64_t required_w_bytes =
        static_cast<std::uint64_t>(padded_n) * padded_k / 2ULL;
    const std::uint64_t required_sw_bytes =
        static_cast<std::uint64_t>(padded_n) * group_count * sizeof(float);
    const std::uint64_t required_x_bytes =
        static_cast<std::uint64_t>(t) * padded_k * sizeof(std::int8_t);
    const std::uint64_t required_sx_bytes =
        static_cast<std::uint64_t>(t) * sizeof(float);
    const std::uint64_t required_y_bytes =
        static_cast<std::uint64_t>(t) * padded_n * sizeof(float);

    // 长度检查使用至少关系，允许主机分配更大的复用 BO。
    if (w_bytes < required_w_bytes || sw_bytes < required_sw_bytes ||
        x_bytes < required_x_bytes || sx_bytes < required_sx_bytes ||
        y_bytes < required_y_bytes) {
        write_meta(
            meta,
            previous_completed_count,
            job_id,
            w4a8_b2::kStatusBadBufferLength,
            1U,
            required_w_bytes,
            false);
        return;
    }

    // 非 meta 数据指针在长度验证后统一检查，错误调用不改写 y。
    if (w_packed == nullptr || sw == nullptr || xq == nullptr || sx == nullptr ||
        y == nullptr) {
        write_meta(
            meta,
            previous_completed_count,
            job_id,
            w4a8_b2::kStatusNullPointer,
            1U,
            required_w_bytes,
            false);
        return;
    }

    // 保留码检查在正式输出前完成，避免错误输入留下半写结果。
    if (contains_invalid_w4(w_packed, n, k, group_count)) {
        write_meta(
            meta,
            previous_completed_count,
            job_id,
            w4a8_b2::kStatusInvalidW4Code,
            1U,
            required_w_bytes,
            false);
        return;
    }

    // 首版采用串行输出结构；B3 再加入 32 lane 并行和 AXI burst 优化。
    for (std::uint32_t token = 0; token < t; ++token) {
        for (std::uint32_t output = 0; output < padded_n; ++output) {
            const std::uint64_t output_index =
                static_cast<std::uint64_t>(token) * padded_n + output;

            if (output >= n) {
                y[output_index] = 0.0F;
                continue;
            }

            const std::uint32_t output_block = output / w4a8_b2::kOutputTile;
            const std::uint32_t output_lane = output % w4a8_b2::kOutputTile;
            float total = 0.0F;

            for (std::uint32_t group = 0; group < group_count; ++group) {
                const std::int32_t sum = w4a8_group_sum(
                    w_packed,
                    xq,
                    output_block,
                    output_lane,
                    group,
                    group_count,
                    token,
                    padded_k);
                const std::uint64_t scale_index =
                    (static_cast<std::uint64_t>(output_block) * group_count + group) *
                        w4a8_b2::kOutputTile +
                    output_lane;
                const float scaled_group =
                    (static_cast<float>(sum) * sw[scale_index]) * sx[token];

                total += scaled_group;
            }

            y[output_index] = total;
        }
    }

    // 只有全部输出写完后才递增硬件完成计数并报告成功。
    write_meta(
        meta,
        previous_completed_count,
        job_id,
        w4a8_b2::kStatusOk,
        1U,
        required_w_bytes,
        true);
}
