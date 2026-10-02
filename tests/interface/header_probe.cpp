// 验证公共软件接口和私有核接口可以共存，二者不是同一个 ABI。
#define _Static_assert static_assert
#include "header_probe.c"
#include "../../src/w4a8_linear_v1.hpp"
#include <cstddef>

// 固定私有元数据长度和对齐，不推测寄存器地址。
static_assert(sizeof(w4a8_b2::KernelMeta) == 40, "private meta size");
static_assert(offsetof(w4a8_b2::KernelMeta, job_id) == 8, "job offset");
static_assert(offsetof(w4a8_b2::KernelMeta, hw_completed_count) == 24, "count offset");
static_assert(w4a8_b2::kAbiVersion == 1, "private ABI version");
#if defined(B02_CACHE_X) && defined(B02_AXI_X128)
static_assert(w4a8_b2::kKernelBuildId == 0xB3020002U, "B02 X128 build");
#elif defined(B02_CACHE_X)
static_assert(w4a8_b2::kKernelBuildId == 0xB3020001U, "B02 activation cache build");
#else
static_assert(w4a8_b2::kKernelBuildId == 0xB3010001U, "B01 ablation build");
#endif
