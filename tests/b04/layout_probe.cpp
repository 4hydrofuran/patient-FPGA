// B04：直接编译冻结核头，输出真实结构偏移，与独立主机检查器和 XO 元数据交叉核对。
#include "../../src/w4a8_linear_v1.hpp"
#include "../../host/b04_private_probe.hpp"
#include <cstddef>
#include <iostream>
#include <type_traits>

// 编译失败即阻断布局资料，不能用手写 JSON 掩盖真实 ABI 改动。
using Meta = w4a8_b2::KernelMeta;
static_assert(std::is_standard_layout<Meta>::value, "meta must be standard layout");
static_assert(sizeof(Meta) == b04::kMetaBytes, "meta size mismatch");
static_assert(w4a8_b2::kKernelBuildId == b04::kBuildId, "compile selected double flags");
static_assert(w4a8_b2::kAbiMagic == b04::kMagic, "magic mismatch");
static_assert(offsetof(Meta, abi_magic) == 0 && offsetof(Meta, kernel_build_id) == 4, "identity offsets");
static_assert(offsetof(Meta, job_id) == 8 && offsetof(Meta, status) == 16, "job/status offsets");
static_assert(offsetof(Meta, done) == 20 && offsetof(Meta, hw_completed_count) == 24, "completion offsets");
static_assert(offsetof(Meta, algorithm_weight_bytes) == 32, "weight byte offset");

// 只输出可核验布局，没有板端执行或运行时状态声明。
int main() {
    std::cout << "{\"meta_bytes\":" << sizeof(Meta)
              << ",\"magic\":" << w4a8_b2::kAbiMagic
              << ",\"build_id\":" << w4a8_b2::kKernelBuildId
              << ",\"offsets\":{\"abi_magic\":0,\"kernel_build_id\":4,\"job_id\":8,"
                 "\"status\":16,\"done\":20,\"hw_completed_count\":24,\"algorithm_weight_bytes\":32}}\n";
}
