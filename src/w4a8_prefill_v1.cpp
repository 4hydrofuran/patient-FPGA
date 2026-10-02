// B03 W4A8核：T1保留X128调度；T>1跨token复用权重，可独立开启受控双缓冲。
// 公共数学/布局和私有ABI不变；所有W4预检查完成后才允许写输出。

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

// 职责：连续搬入一个完整权重 tile；输入：DDR 字节地址和 tile 起点；输出：2048 字节缓存；副作用：只读外存。
void load_weight_tile(const std::uint8_t* w_packed, std::uint64_t tile_base,
                      std::uint8_t weight_tile[2048]) {

    // 内联后保留调用点 tile 起点的 2048 字节对齐信息，便于 HLS 合并宽 AXI 访问。
#pragma HLS INLINE

    // 一个本地存储字包含同一输入位置的 16 字节，避免逐字节 read-modify-write。
#pragma HLS ARRAY_RESHAPE variable = weight_tile cyclic factor = 16 dim = 1

    // 连续读取 128 个输入位置，每个位置恰好对应 32 个 W4 lane。
    for (std::uint32_t row = 0; row < 128U; ++row) {

        // 每拍搬入一个 128-bit 权重向量，实际 burst 与 II 以报告为准。
#pragma HLS PIPELINE II = 1

        // 相邻 16 字节可以合并为一个 master beat，写满同一个本地宽字。
        for (std::uint32_t pair = 0; pair < 16U; ++pair) {

            // 固定展开 16 个连续字节，消除 scalar memcpy 写局部字节的瓶颈。
#pragma HLS UNROLL

            // 物理地址单调连续且 tile 起点为 2048 字节的整数倍。
            weight_tile[row * 16U + pair] = w_packed[tile_base + row * 16U + pair];
        }
    }
}

// 按完整 tile 连续搬运并检查 32 个半字节；尾部填充不参与保留码拒绝。
bool contains_invalid_w4(
    const std::uint8_t* w_packed,
    std::uint32_t n,
    std::uint32_t k,
    std::uint32_t group_count) {
    // 该缓存仅占 2048 字节，不随整个 N×K 矩阵扩大。
    std::uint8_t weight_tile[2048];

    // 同一 K 位置的 16 字节合成一个宽存储字，供 32 个半字节检查同时读取。
#pragma HLS ARRAY_RESHAPE variable = weight_tile cyclic factor = 16 dim = 1

    // 整个扫描结束后统一返回，保留非法输入时 y 完全不变的约定。
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
        for (std::uint32_t group = 0; group < group_count; ++group) {
            const std::uint32_t inputs_left = k - group * w4a8_b2::kGroupSize;
            const std::uint32_t valid_inputs =
                (inputs_left < w4a8_b2::kGroupSize) ? inputs_left
                                                    : w4a8_b2::kGroupSize;
            const std::uint64_t group_base =
                (static_cast<std::uint64_t>(output_block) * group_count + group) *
                w4a8_b2::kGroupSize * 16ULL;

            // 冻结缓冲容量包含完整 padding，因此读取整个 tile 不会跨出合法 BO。
            load_weight_tile(w_packed, group_base, weight_tile);

            // 固定 128 轮检查避免可变字节循环；有效 K 之外仅搬运而不判错。
            for (std::uint32_t remainder = 0; remainder < 128U; ++remainder) {

                // 每轮并行检查同一个 K 位置的 32 个输出 lane，目标 II=1。
#pragma HLS PIPELINE II = 1

                // 每个 lane 独占一个 mask 位，最终只需归约是否存在保留码。
                std::uint32_t invalid_mask = 0U;

                // 静态展开恰好 32 个 lane，不对运行时 N 做无限展开。
                for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                    // 半字节检查并行化，读取同一宽存储字的不同固定位置。
#pragma HLS UNROLL

                    // 偶数 lane 在低半字节，奇数 lane 在高半字节。
                    const std::uint8_t packed_byte = weight_tile[remainder * 16U + lane / 2U];

                    // 使用 nibble 而不是有符号转换来检测精确的保留码 0x8。
                    const std::uint8_t nibble = (packed_byte >> ((lane & 1U) * 4U)) & 0x0FU;

                    // N/K 填充区保持 B2 的忽略规则。
                    const bool bad_lane = lane < valid_lanes && remainder < valid_inputs && nibble == 8U;

                    // 各位不冲突，综合器可将该结果组合为 32 位检查向量。
                    invalid_mask |= static_cast<std::uint32_t>(bad_lane) << lane;
                }

                // 不提前写输出或返回，维持完整扫描后判错的行为。
                invalid = invalid || invalid_mask != 0U;
            }
        }
    }

    return invalid;
}

}  // namespace

// 32 条独立整数累加通道共用一个 A8 元素，保持每组 INT32 结果精确一致。
void w4a8_tile_group_sums(const std::uint8_t weights[2048],
                          const std::int8_t activations[128],
                          std::int32_t sums[32]) {

    // 与顶层缓存使用一致的 16 字节存储字，避免 32-lane 访存端口竞争。
#pragma HLS ARRAY_RESHAPE variable = weights cyclic factor = 16 dim = 1

    // 32 个部分和各有独立累加寄存器，支持同一拍更新全部通道。
#pragma HLS ARRAY_PARTITION variable = sums complete dim = 1

    // 清零当前 group 的全部通道，不继承上一组的 INT32 状态。
    for (std::uint32_t lane = 0; lane < 32U; ++lane) {

        // 固定 32 个寄存器可以同时初始化。
#pragma HLS UNROLL

        // 每条 lane 在本组从零开始累加。
        sums[lane] = 0;
    }

    // 128 轮对应一个量化组，外层流水而内层 32-lane 并行。
    for (std::uint32_t remainder = 0; remainder < 128U; ++remainder) {

        // 目标每拍广播一个输入元素并执行 32 次整数乘加。
#pragma HLS PIPELINE II = 1

        // 同一个 A8 元素供本 tile 的全部输出复用。
        const std::int32_t activation = activations[remainder];

        // 每条 lane 只更新自己的累加器，不在不同 lane 之间做浮点归约。
        for (std::uint32_t lane = 0; lane < 32U; ++lane) {

            // 静态展开这 32 次乘加，使硬件结构而非仅源代码表现为并行。
#pragma HLS UNROLL

            // 一个字节服务偶数、奇数两个固定 lane。
            const std::uint8_t packed_byte = weights[remainder * 16U + lane / 2U];

            // 将对应 lane 的四位补码提取到低半字节。
            const std::uint8_t nibble = (packed_byte >> ((lane & 1U) * 4U)) & 0x0FU;

            // 每组最大整数幅度远小于 INT32 上限，无饱和或浮点近似。
            const std::int32_t weight = decode_w4(nibble);

            // 每个输出沿 K 的整数累加顺序与串行基线相同。
            sums[lane] += weight * activation;
        }
    }
}

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

namespace {

// 职责：按需装载一个完整group；输出缓存只在返回后交给计算，最后group禁止预取越界。
void load_prefill_group(const std::uint8_t* w_packed, const float* sw,
                        std::uint64_t tile_group, bool enabled,
                        std::uint8_t weights[2048], float scales[32]) {

    // 保留独立装载任务，供DATAFLOW与当前group计算并行调度。
#pragma HLS INLINE off

    // 16字节存储字服务32条W4 lane；下游拥有的是完整缓存。
#pragma HLS ARRAY_RESHAPE variable=weights cyclic factor=16 dim=1

    // 没有下一group时不触碰外存，也不覆盖已经消费完的另一缓存。
    if (enabled) {

        // tile_group直接映射冻结的2048字节对齐布局。
        load_weight_tile(w_packed, tile_group * 2048ULL, weights);

        // 与权重配对的32个scale仅装载一次，供所有token复用。
        for (std::uint32_t lane=0; lane<32U; ++lane) {

            // scale连续读取，目标每拍一个FP32元素。
#pragma HLS PIPELINE II=1

            // 不改变公共scale的tile、group、lane顺序。
            scales[lane]=sw[tile_group * 32ULL + lane];
        }
    }
}

// 职责：一个已装载group依次服务T个token；每个输出只在自身group序列上累加。
void compute_prefill_group(const std::uint8_t weights[2048], const float scales[32],
                           const std::int8_t activations[8][4864],
                           const float token_scales[8], float totals[8][32],
                           std::uint32_t t, std::uint32_t group) {

    // 与装载任务分离，函数返回即表示当前缓存已无读者。
#pragma HLS INLINE off

    // 同一拍读取一个K位置的16字节，仍只有32条乘加通道。
#pragma HLS ARRAY_RESHAPE variable=weights cyclic factor=16 dim=1

    // 每个token轮流复用相同权重，而不是复制T套DSP。
    for (std::uint32_t token=0; token<t; ++token) {

        // 本组的部分和不跨token或group保留。
        std::int32_t sums[32];

        // 32个lane独占整数寄存器，保持实际32路MAC结构。
#pragma HLS ARRAY_PARTITION variable=sums complete dim=1

        // 当前token缓存中的128个激活参与原有bit-exact数据通路。
        w4a8_tile_group_sums(weights, &activations[token][group * 128U], sums);

        // 各lane沿group递增恢复，禁止改变浮点括号或融合乘加。
        for (std::uint32_t lane=0; lane<32U; ++lane) {

            // 复用有限数量的FP32运算单元，目标每拍启动一个lane。
#pragma HLS PIPELINE II=1

            // 先乘Sw，再乘该token的Sx，保持冻结语义。
            const float restored=(static_cast<float>(sums[lane]) * scales[lane]) * token_scales[token];

            // group间调用按顺序完成，同一个token的FP32加法次序不变。
            totals[token][lane]+=restored;
        }
    }
}

#ifdef B03_DOUBLE_BUFFER
// 职责：并行计算当前缓存与装载下一缓存；两个参数组的物理所有权必须分离。
void prefill_overlap(const std::uint8_t* w_packed, const float* sw,
                     std::uint64_t next_tile_group, bool has_next,
                     std::uint8_t next_weights[2048], float next_scales[32],
                     const std::uint8_t current_weights[2048], const float current_scales[32],
                     const std::int8_t activations[8][4864], const float token_scales[8],
                     float totals[8][32], std::uint32_t t, std::uint32_t group) {

    // 每个group的两个任务均结束后返回，外层才能交换缓存所有权。
#pragma HLS INLINE off

    // 加载与计算仅共享只读外部控制，分别使用next/current缓存。
#pragma HLS DATAFLOW

    // producer只写下一缓存，AXI等待不会使计算读取半成品。
    load_prefill_group(w_packed,sw,next_tile_group,has_next,next_weights,next_scales);

    // consumer只读当前缓存，完成后才能允许未来迭代覆盖。
    compute_prefill_group(current_weights,current_scales,activations,token_scales,totals,t,group);
}
#endif

// 职责：T>1时缓存全部A8输入，按输出tile→group→token调度，保留原有Y布局。
void compute_prefill(const std::uint8_t* w_packed, const float* sw,
                     const std::int8_t* xq, const float* sx, float* y,
                     std::uint32_t t, std::uint32_t n,
                     std::uint32_t padded_n, std::uint32_t padded_k,
                     std::uint32_t group_count) {

    // 独立prefill调度不把T1引入多token缓存准备路径。
#pragma HLS INLINE off

    // 最多38912字节；缓存容量来自冻结T/K上限，不能按整模型权重分配片上存储。
    std::int8_t activations[8][4864];

    // 同时仅读取一个token的一条激活，单端口BRAM足够。
#pragma HLS BIND_STORAGE variable=activations type=ram_1p impl=bram

    // 每个token的量化scale在任务开始读取一次。
    float token_scales[8];

    // 当前输出tile保存最多8×32个FP32累计值，跨group保留且跨tile清零。
    float totals[8][32];

    // 两个权重槽各自有独立存储，避免覆盖正在读取的槽。
    std::uint8_t weights_first[2048];

    // 本地16字节宽字使32lane解包无需争用字节端口。
#pragma HLS ARRAY_RESHAPE variable=weights_first cyclic factor=16 dim=1

    // scale与相同编号的权重槽始终一起交换。
    float scales_first[32];

#ifdef B03_DOUBLE_BUFFER
    // 第二槽只在双缓冲消融中存在，单纯复用构建不会支付其存储成本。
    std::uint8_t weights_second[2048];

    // 与第一槽保持相同宽度，但所有权相互独立。
#pragma HLS ARRAY_RESHAPE variable=weights_second cyclic factor=16 dim=1

    // 当前group和下一group的scale不能混用。
    float scales_second[32];
#endif

    // 每个有效token只从AXI读取一次完整A8行，供所有输出tile复用。
    for (std::uint32_t token=0; token<t; ++token) {

        // Sx不参与跨token共享，保持每条输入独立scale。
        token_scales[token]=sx[token];

        // 完整padding窗口在通过长度校验后可连续装载。
        for (std::uint32_t input=0; input<padded_k; ++input) {

            // A8装载保持顺序访问，目标每拍一个字节。
#pragma HLS PIPELINE II=1

            // 公共输入仍为[T,Kp]行主序，不要求调用方重排。
            activations[token][input]=xq[static_cast<std::uint64_t>(token) * padded_k + input];
        }
    }

    // 输出tile决定缓存生命周期，避免保存整个T×N输出矩阵。
    for (std::uint32_t block=0; block<padded_n/32U; ++block) {

        // 所有token在本tile从零开始累计，不能继承前次任务状态。
        for (std::uint32_t token=0; token<t; ++token) {

            // 每个token的32lane输出分别初始化。
            for (std::uint32_t lane=0; lane<32U; ++lane) {

                // 连续清零只需一个累计缓存写端口。
#pragma HLS PIPELINE II=1

                // 每个group随后依序累加到相应token/lane。
                totals[token][lane]=0.0F;
            }
        }

#ifdef B03_DOUBLE_BUFFER
        // 每个tile先完整装载group0；首个计算绝不读取未初始化缓存。
        load_prefill_group(w_packed,sw,static_cast<std::uint64_t>(block) * group_count,true,weights_first,scales_first);
#endif

        // 每个token的group序列严格递增；只交换不同token间独立运算的位置。
        for (std::uint32_t group=0; group<group_count; ++group) {

            // 冻结物理布局无需改变，只有权重读取次数变化。
            const std::uint64_t tile_group=static_cast<std::uint64_t>(block) * group_count + group;

#ifdef B03_DOUBLE_BUFFER
            // 最后group关闭预取；即使下一地址落在BO外也不会访问它。
            const bool has_next=group+1U<group_count;

            // 静态槽编号消除动态下标别名，进入调用时两槽职责明确。
            if ((group & 1U)==0U) {

                // 消费第一槽时只能向第二槽装载下一group。
                prefill_overlap(w_packed,sw,tile_group+1ULL,has_next,weights_second,scales_second,
                                weights_first,scales_first,activations,token_scales,totals,t,group);
            } else {

                // 前一调用已全部完成，因此第二槽已就绪、第一槽已释放。
                prefill_overlap(w_packed,sw,tile_group+1ULL,has_next,weights_first,scales_first,
                                weights_second,scales_second,activations,token_scales,totals,t,group);
            }
#else
            // 单纯权重复用构建保持串行装载，独立测量复用本身的收益。
            load_prefill_group(w_packed,sw,tile_group,true,weights_first,scales_first);

            // 一个权重group服务全部token后才装载下一个group。
            compute_prefill_group(weights_first,scales_first,activations,token_scales,totals,t,group);
#endif
        }

        // 只有当前tile的所有group结束后才写回；装载阶段不会覆盖累计值。
        for (std::uint32_t token=0; token<t; ++token) {

            // 公共输出保持[T,Np]，调用方无需改变模型接入方式。
            for (std::uint32_t lane=0; lane<32U; ++lane) {

                // 每拍写一个FP32输出；保留N尾部清零语义。
#pragma HLS PIPELINE II=1

                // 全部W4预检查已在顶层完成，错误输入不会留下部分输出。
                y[static_cast<std::uint64_t>(token) * padded_n + block * 32U + lane]=
                    block * 32U + lane<n ? totals[token][lane] : 0.0F;
            }
        }
    }
}

} // namespace

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
    // depth 以端口元素个数为单位，覆盖 B3 的代表性真实尺寸仿真窗口。
    // 它只决定 cosim 包装器的固定拷贝窗口；板端运行时容量仍由地址和 *_bytes 校验决定。
#pragma HLS INTERFACE m_axi port = w_packed offset = slave bundle = gmem_w depth = 2179072 max_read_burst_length = 128 max_widen_bitwidth = 128

    // scale 仍使用冻结的独立 master；连续 32 个 scale 可合并请求。
#pragma HLS INTERFACE m_axi port = sw offset = slave bundle = gmem_sw depth = 34048 max_read_burst_length = 32

    // X128 消融只限制同一 gmem_x 的最大物理宽度；地址、burst 与数据不变。
#ifdef B02_AXI_X128
#pragma HLS INTERFACE m_axi port = xq offset = slave bundle = gmem_x depth = 38912 max_read_burst_length = 128 max_widen_bitwidth = 128
#else
    // A8 输入按 group128 搬入缓存，与 sx 保持同一个冻结 bundle。
#pragma HLS INTERFACE m_axi port = xq offset = slave bundle = gmem_x depth = 38912 max_read_burst_length = 128
#endif

    // 仿真窗口包含最多 8 个 sx，但本轮性能目标仍是 T=1。
#pragma HLS INTERFACE m_axi port = sx offset = slave bundle = gmem_x depth = 8

    // 输出按 tile32 连续写回，depth 覆盖真实 up 层输出。
#pragma HLS INTERFACE m_axi port = y offset = slave bundle = gmem_y depth = 38912 max_write_burst_length = 32
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

    // 多token才进入B03调度；T1保持冻结X128数据路径，独立守住decode延迟。
    if (t>1U) {

        // 全部参数和W4已检查，prefill可安全复用权重并写出结果。
        compute_prefill(w_packed,sw,xq,sx,y,t,n,padded_n,padded_k,group_count);

        // 所有缓存任务已结束、输出已写完，才增加硬件完成计数。
        write_meta(meta,previous_completed_count,job_id,w4a8_b2::kStatusOk,1U,required_w_bytes,true);

        // 不重复执行后面的T1兼容路径。
        return;
    }

    // 固定大小的权重工作台为 2048 字节，独立于整个矩阵的容量。
    std::uint8_t weight_tile[2048];

    // 每个 K 位置的 16 字节合并，支持 32 个 W4 lane 同时读取。
#pragma HLS ARRAY_RESHAPE variable = weight_tile cyclic factor = 16 dim = 1

    // B02候选：每个token从AXI读取一次完整A8行，跨全部输出tile复用。
#ifdef B02_CACHE_X
    std::int8_t token_activations[w4a8_b2::kMaxK];
#pragma HLS BIND_STORAGE variable = token_activations type = ram_1p impl = bram
#else
    // B01消融构建保留每个tile-group重新从AXI搬入128字节的路径。
    std::int8_t activation_tile[128];
#endif

    // 一个输出 tile 的 scale 只保留当前 group 的 32 个 FP32 值。
    float scale_tile[32];

    // 整数部分和按组清零，32 条通道不能共享同一个存储端口。
    std::int32_t sums[32];

    // 每条整数通道独占寄存器，允许同拍执行 32 次乘加。
#pragma HLS ARRAY_PARTITION variable = sums complete dim = 1

    // 浮点累计只保留当前 32 个输出，组间恢复顺序仍与 B2 一致。
    float totals[32];

    // 每次主机调用仍处理完整矩阵；支持既有 T 范围但不做跨 token 权重复用。
    for (std::uint32_t token = 0; token < t; ++token) {

        // 同一 token 的 activation scale 只读取一次。
        const float token_scale = sx[token];

#ifdef B02_CACHE_X
        // padding也在合法X缓冲内：逐token连续读取Kp字节，再供所有输出tile复用。
        for (std::uint32_t input = 0; input < padded_k; ++input) {
#pragma HLS PIPELINE II = 1
            token_activations[input] = xq[static_cast<std::uint64_t>(token) * padded_k + input];
        }
#endif

        // 输出外循环改为以 32-lane tile 为单位，消除逐输出的步长访存。
        for (std::uint32_t output_block = 0; output_block < padded_n / 32U; ++output_block) {

            // 为该 tile 重置全部浮点累计值。
            for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                // 连续初始化可让存储器每拍接收一个零值。
#pragma HLS PIPELINE II = 1

                // 当前输出不继承上一 tile 的结果。
                totals[lane] = 0.0F;
            }

            // 按原顺序恢复不同 group 的 scale，不合并不同 scale 的 INT32 和。
            for (std::uint32_t group = 0; group < group_count; ++group) {

                // 权重和 scale 都以输出 tile、K group 的组合为外层布局。
                const std::uint64_t tile_group = static_cast<std::uint64_t>(output_block) * group_count + group;

                // 一个完整连续权重块搬入本地，本轮不与计算重叠。
                load_weight_tile(w_packed, tile_group * 2048ULL, weight_tile);

                // 消融路径保留B01原始AXI搬运；候选直接读取当前token缓存的group窗口。
#ifndef B02_CACHE_X
                for (std::uint32_t input = 0; input < 128U; ++input) {

                    // A8 按连续地址每拍搬一个元素，随后复用到 32 个输出 lane。
#pragma HLS PIPELINE II = 1

                    // 向量尾部已由主机 padding，因此完整 128 字节均可访问。
                    activation_tile[input] = xq[static_cast<std::uint64_t>(token) * padded_k + group * 128U + input];
                }
#endif

                // 当前量化组的 32 个权重 scale 连续搬入。
                for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                    // scale 使用原 32-bit master 连续读取，避免没有流水的 memcpy 小循环。
#pragma HLS PIPELINE II = 1

                    // 保持 tile、group、lane 的冻结 scale 索引。
                    scale_tile[lane] = sw[tile_group * 32ULL + lane];
                }

                // 使用实际 32-lane 数据通路得到本组的精确整数部分和。
#ifdef B02_CACHE_X
                w4a8_tile_group_sums(weight_tile, &token_activations[group * 128U], sums);
#else
                w4a8_tile_group_sums(weight_tile, activation_tile, sums);
#endif

                // 浮点恢复逐 lane 流水，避免一次实例化 32 套完整浮点乘加器。
                for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                    // 每拍启动一个输出 lane 的恢复，实际 II 以综合报告为准。
#pragma HLS PIPELINE II = 1

                    // 保持先乘 Sw 再乘 Sx 的括号顺序，未开启 unsafe math。
                    const float restored = (static_cast<float>(sums[lane]) * scale_tile[lane]) * token_scale;

                    // 沿 group 的 FP32 加法顺序维持串行基线的定义。
                    totals[lane] += restored;
                }
            }

            // N 尾部 lane 的最终输出固定为零，不暴露 padding 的计算结果。
            for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                // 本地连续访问仅需一个写端口。
#pragma HLS PIPELINE II = 1

                // 有效输出保持累计值，填充输出遵守冻结的清零规则。
                totals[lane] = output_block * 32U + lane < n ? totals[lane] : 0.0F;
            }

            // 全部权重检查已通过，才能以完整 tile 连续写回 FP32 输出。
            for (std::uint32_t lane = 0; lane < 32U; ++lane) {

                // 同一个 tile 的 32 个 FP32 输出连续写回，目标每拍启动一个写事务元素。
#pragma HLS PIPELINE II = 1

                // 所有保留码检查已结束，不会发生错误输入的部分输出。
                y[static_cast<std::uint64_t>(token) * padded_n + output_block * 32U + lane] = totals[lane];
            }
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
