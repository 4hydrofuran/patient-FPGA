// 本文件沿用用户确认冻结的 B2 参数与元数据布局，供 B3 首轮 32-lane 核使用。
// 构建标识随 B3 改变；ABI 版本、结构字段、状态码和顶层参数保持兼容。

// 头文件保护保证 ABI 类型在每个编译单元只定义一次。
#ifndef W4A8_LINEAR_V1_HPP
#define W4A8_LINEAR_V1_HPP

#include <cstdint>

namespace w4a8_b2 {

// 首版只覆盖目标 MLP 形状，不覆盖大词表 LM head。
constexpr std::uint32_t kMaxT = 8;
constexpr std::uint32_t kMaxN = 4864;
constexpr std::uint32_t kMaxK = 4864;
constexpr std::uint32_t kGroupSize = 128;
constexpr std::uint32_t kOutputTile = 32;

// 该常量用于拒绝错误版本的主机调用。
constexpr std::uint32_t kAbiVersion = 1;

// "W4A8" 的小端整数表示，用于主机检查 meta 是否来自当前核。
constexpr std::uint32_t kAbiMagic = 0x57344138U;

// 访存消融使用独立私有构建标识；公共ABI与数值布局保持不变。
#if defined(B02_CACHE_X) && defined(B02_AXI_X128)
constexpr std::uint32_t kKernelBuildId = 0xB3020002U;
#elif defined(B02_CACHE_X)
constexpr std::uint32_t kKernelBuildId = 0xB3020001U;
#else
constexpr std::uint32_t kKernelBuildId = 0xB3010001U;
#endif

// 状态码明确区分参数错误、缓冲错误和非法 W4 码。
enum KernelStatus : std::uint32_t {
    kStatusOk = 0,
    kStatusBadAbi = 1,
    kStatusBadDimension = 2,
    kStatusBadBufferLength = 3,
    kStatusNullPointer = 4,
    kStatusInvalidW4Code = 5,
};

// meta 使用固定宽度字段，当前自然对齐布局总长为 40 字节。
struct KernelMeta {
    std::uint32_t abi_magic;
    std::uint32_t kernel_build_id;
    std::uint64_t job_id;
    std::uint32_t status;
    std::uint32_t done;
    std::uint64_t hw_completed_count;
    std::uint64_t algorithm_weight_bytes;
};

static_assert(sizeof(KernelMeta) == 40, "KernelMeta layout must remain 40 bytes");

}  // namespace w4a8_b2

// 一个连续的 2048 字节 tile 产生 32 个 INT32 部分和；主核和测试均观察这一实际数据通路。
void w4a8_tile_group_sums(const std::uint8_t weights[2048],
                          const std::int8_t activations[128],
                          std::int32_t sums[32]);

// 该辅助函数暴露一个 128 元素组的整数部分和，便于 testbench 做 bit-exact 检查。
std::int32_t w4a8_group_sum(
    const std::uint8_t* w_packed,
    const std::int8_t* xq,
    std::uint32_t output_block,
    std::uint32_t output_lane,
    std::uint32_t group,
    std::uint32_t group_count,
    std::uint32_t token,
    std::uint32_t padded_k);

// 顶层核严格消费已经量化并按 B0 布局打包的缓冲区。
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
    std::uint32_t abi_version);

#endif
