// B04：B 侧独立检查冻结核的字节布局与完成记录；不实现 XRT 或公共调用库。
#ifndef B04_PRIVATE_PROBE_HPP
#define B04_PRIVATE_PROBE_HPP

// 公共错误码直接使用冻结头文件，避免另起一套编号。
#include "../contracts/sp_linear_v1.h"
#include <cstddef>
#include <cstdint>

namespace b04 {

// 标识对应已发布的 double XO；探针会另与真实核头、kernel.xml 和摘要交叉核验。
constexpr std::uint32_t kMagic = 0x57344138U;
constexpr std::uint32_t kBuildId = 0xB3030002U;
constexpr std::size_t kMetaBytes = 40;

// 字节数为逻辑最小容量，不等于 XRT 的物理分配、地址或内存组。
struct BufferSizes {
    std::uint32_t np = 0, kp = 0, groups = 0;
    std::uint64_t w = 0, sw = 0, x = 0, sx = 0, y = 0, meta = kMetaBytes;
};

// 先限制尺寸再计算，允许更大 BO，但不允许用溢出的数值绕过长度检查。
inline std::int32_t required_sizes(std::uint32_t t, std::uint32_t n,
                                   std::uint32_t k, BufferSizes* out) noexcept {
    if (!out || t == 0 || t > 8 || n == 0 || n > 4864 || k == 0 || k > 4864) {
        return SP_BAD_ARGUMENT;
    }
    BufferSizes sizes;
    sizes.np = ((n + 31U) / 32U) * 32U;
    sizes.kp = ((k + 127U) / 128U) * 128U;
    sizes.groups = sizes.kp / 128U;
    sizes.w = static_cast<std::uint64_t>(sizes.np) * sizes.kp / 2U;
    sizes.sw = static_cast<std::uint64_t>(sizes.np) * sizes.groups * 4U;
    sizes.x = static_cast<std::uint64_t>(t) * sizes.kp;
    sizes.sx = static_cast<std::uint64_t>(t) * 4U;
    sizes.y = static_cast<std::uint64_t>(t) * sizes.np * 4U;
    *out = sizes;
    return SP_OK;
}

// 软件结构保存已解码字段；绝不把未对齐的外部字节直接转换为结构指针。
struct DecodedMeta {
    std::uint32_t magic = 0, build_id = 0;
    std::uint64_t job_id = 0;
    std::uint32_t status = 0, done = 0;
    std::uint64_t completed_count = 0, algorithm_weight_bytes = 0;
};

// 原因属于验收工具，公共 ABI 仍只返回冻结 sp_linear_status。
enum class MetaIssue {
    none, invalid_expectation, null_meta, short_meta, wrong_magic, wrong_build,
    wrong_job, not_done, unknown_status, wrong_counter, wrong_weight_bytes, kernel_rejected
};

// consume_y 默认关闭，只有全部成功条件满足时打开。
struct MetaProbe {
    std::int32_t public_status = SP_DEVICE_ERROR;
    MetaIssue issue = MetaIssue::none;
    bool consume_y = false;
    DecodedMeta meta;
};

// 所有数据均为小端；逐字节读兼容未对齐缓冲与 ARM64 主机。
inline std::uint32_t read_u32(const std::uint8_t* data) noexcept {
    std::uint32_t value = 0;
    for (unsigned i = 0; i < 4; ++i) value |= std::uint32_t(data[i]) << (8U * i);
    return value;
}

// 固定 64 位读，避免依赖主机 long 的宽度和本机字节序。
inline std::uint64_t read_u64(const std::uint8_t* data) noexcept {
    std::uint64_t value = 0;
    for (unsigned i = 0; i < 8; ++i) value |= std::uint64_t(data[i]) << (8U * i);
    return value;
}

// 映射为 B 提供的适配规则；A 的调用层负责实际错误隔离和生命周期。
inline std::int32_t private_status_to_public(std::uint32_t status) noexcept {
    switch (status) {
    case 0: return SP_OK;
    case 1: return SP_CONTRACT_MISMATCH;
    case 2: return SP_BAD_ARGUMENT;
    case 3: return SP_BUFFER_TOO_SMALL;
    case 4: return SP_BAD_ARGUMENT;
    case 5: return SP_NUMERIC_ERROR;
    default: return SP_DEVICE_ERROR;
    }
}

// 本函数只验收已经同步到主机的字节，不证明硬件已停止；有限等待及 poisoned 由 A 管理。
inline MetaProbe inspect_completion(const std::uint8_t* data, std::size_t bytes,
                                    std::uint64_t expected_job,
                                    std::uint64_t previous_count,
                                    std::uint64_t expected_weight_bytes) noexcept {
    MetaProbe result;
    auto reject = [&](MetaIssue issue, std::int32_t status) {
        result.issue = issue;
        result.public_status = status;
        return result;
    };
    if (expected_job == 0) return reject(MetaIssue::invalid_expectation, SP_BAD_ARGUMENT);
    if (!data) return reject(MetaIssue::null_meta, SP_BAD_ARGUMENT);
    if (bytes < kMetaBytes) return reject(MetaIssue::short_meta, SP_BUFFER_TOO_SMALL);
    result.meta = {read_u32(data), read_u32(data + 4), read_u64(data + 8),
                   read_u32(data + 16), read_u32(data + 20),
                   read_u64(data + 24), read_u64(data + 32)};
    const auto& meta = result.meta;
    if (meta.magic != kMagic) return reject(MetaIssue::wrong_magic, SP_CONTRACT_MISMATCH);
    if (meta.build_id != kBuildId) return reject(MetaIssue::wrong_build, SP_CONTRACT_MISMATCH);
    if (meta.job_id != expected_job) return reject(MetaIssue::wrong_job, SP_DEVICE_ERROR);
    if (meta.done != 1) return reject(MetaIssue::not_done, SP_DEVICE_ERROR);
    if (meta.status > 5) return reject(MetaIssue::unknown_status, SP_DEVICE_ERROR);
    const bool success = meta.status == 0;
    // 无符号加法与冻结核一致：成功加一（模 2^64），错误保持原计数。
    const auto expected_count = previous_count + (success ? std::uint64_t(1) : 0);
    if (meta.completed_count != expected_count) return reject(MetaIssue::wrong_counter, SP_DEVICE_ERROR);
    // ABI/维度错误发生在尺寸计算前；其算法字节字段为零。
    const auto expected_bytes = (meta.status == 1 || meta.status == 2) ? 0 : expected_weight_bytes;
    if (success && expected_bytes == 0) return reject(MetaIssue::invalid_expectation, SP_BAD_ARGUMENT);
    if (meta.algorithm_weight_bytes != expected_bytes) return reject(MetaIssue::wrong_weight_bytes, SP_DEVICE_ERROR);
    result.public_status = private_status_to_public(meta.status);
    result.issue = success ? MetaIssue::none : MetaIssue::kernel_rejected;
    result.consume_y = success;
    return result;
}

// JSON/文本输出使用稳定的验收原因名称，便于 A 的适配测试核对。
inline const char* issue_name(MetaIssue issue) noexcept {
    switch (issue) {
    case MetaIssue::none: return "none";
    case MetaIssue::invalid_expectation: return "invalid_expectation";
    case MetaIssue::null_meta: return "null_meta";
    case MetaIssue::short_meta: return "short_meta";
    case MetaIssue::wrong_magic: return "wrong_magic";
    case MetaIssue::wrong_build: return "wrong_build";
    case MetaIssue::wrong_job: return "wrong_job";
    case MetaIssue::not_done: return "not_done";
    case MetaIssue::unknown_status: return "unknown_status";
    case MetaIssue::wrong_counter: return "wrong_counter";
    case MetaIssue::wrong_weight_bytes: return "wrong_weight_bytes";
    case MetaIssue::kernel_rejected: return "kernel_rejected";
    }
    return "unknown";
}

}  // namespace b04
#endif
