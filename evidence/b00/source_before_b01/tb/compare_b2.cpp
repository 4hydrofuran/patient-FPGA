// 将同一批已保存合成向量交给原 B2 核，核对 B3 golden 与被冻结基线的数值兼容性。
// 该测试只用于普通 PC C++，使用本包 baseline/b2，不参与 B3 综合或 Cosim。

// 从本包保留的 B2 源码读取真实基线 ABI，避免依赖相邻开发工程。
#include "../baseline/b2/src/w4a8_linear_v1.hpp"

// 主机端按实际文件长度分配数据，不进入可综合设计。
#include <cmath>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

// 按精确元素数量读取原始向量，额外字节或文件缺失均判失败。
template <typename T>
std::vector<T> read_vector(const std::string& path, std::size_t elements) {

    // 固定业务长度避免错误文件被截断后仍然通过。
    std::vector<T> result(elements);

    // 二进制文件采用向量 manifest 标记的小端格式。
    std::ifstream input(path, std::ios::binary);

    // 读取完整数据并检查流状态，不依赖重建随机输入。
    input.read(reinterpret_cast<char*>(result.data()), static_cast<std::streamsize>(elements * sizeof(T)));

    // 拒绝短文件与尾部未知数据，保持测试来源明确。
    if (!input || input.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error("vector length/read: " + path);
    }

    // 返回的向量只来自实际保存的输入字节。
    return result;
}

// 运行全部合法向量的原 B2 核，检查输出、padding、版本与完成计数。
int main() {

    // case 的维度与 manifest 保持一致，故意不引用 B3 的随机生成或打包函数。
    struct Shape { const char* name; std::uint32_t t, n, k; };

    // 包括手算、边界、多 token 兼容与四种实际尺寸的合成向量。
    const Shape cases[] = {{"hand_sample",1,2,2},{"tile_random",1,32,128},{"nk_tail",1,33,129},
        {"three_groups",1,65,257},{"single",1,1,1},{"zeros",1,33,129},{"extremes",1,32,128},
        {"t4_compat",4,33,129},{"t8_compat",8,1,1},{"nonbinary_scale",1,32,128},
        {"padding_reserved",1,1,1},{"mlp_up_synthetic",1,4864,896},{"mlp_down_synthetic",1,896,4864},
        {"projection_synthetic",1,896,896},{"small_projection_synthetic",1,128,896}};

    // 失败时携带具体文件或用例，返回非零而不继续打印总 PASS。
    try {

        // 每个用例使用完全相同的 packed BO 字节调用原 B2。
        for (const Shape& shape : cases) {

            // 使用冻结公式定义业务容量，不采用 B3 仿真预留窗口。
            const std::uint32_t np = (shape.n + 31U) / 32U * 32U;
            const std::uint32_t kp = (shape.k + 127U) / 128U * 128U;
            const std::uint32_t groups = kp / 128U;
            const std::string prefix = std::string("vectors/generated/") + shape.name;

            // expected 文件来自独立 dense golden，B2 与 B3 都不生成对方的期望值。
            auto w = read_vector<std::uint8_t>(prefix + ".w_packed.bin", static_cast<std::size_t>(np) * kp / 2U);
            auto sw = read_vector<float>(prefix + ".sw.bin", static_cast<std::size_t>(np) * groups);
            auto x = read_vector<std::int8_t>(prefix + ".xq.bin", static_cast<std::size_t>(shape.t) * kp);
            auto sx = read_vector<float>(prefix + ".sx.bin", shape.t);
            const auto expected = read_vector<float>(prefix + ".expected_y.bin", static_cast<std::size_t>(shape.t) * np);

            // 额外一个哨兵检测原 B2 是否写出业务窗口。
            std::vector<float> y(expected.size() + 1U, -1234.5F);
            w4a8_b2::KernelMeta meta{};

            // 调用的是从未修改的 B2 源码，参数仍采用同一个 ABI。
            w4a8_linear_v1(w.data(), sw.data(), x.data(), sx.data(), y.data(), &meta,
                shape.t, shape.n, shape.k, w.size(), sw.size() * 4U, x.size(), sx.size() * 4U,
                expected.size() * 4U, sizeof(meta), 55ULL, 1U);

            // 原 B2 必须返回其自身构建值，证明此处没有误链接 B3。
            if (meta.status != 0U || meta.done != 1U || meta.kernel_build_id != 0xB2000001U ||
                meta.job_id != 55ULL || meta.hw_completed_count != 1ULL || y.back() != -1234.5F) {
                throw std::runtime_error(std::string("B2 metadata/guard: ") + shape.name);
            }

            // 采用与 B3 相同的冻结 FP32 绝对阈值，不放宽测试来获得兼容结论。
            for (std::size_t i = 0; i < expected.size(); ++i) {
                if (!std::isfinite(y[i]) || std::fabs(y[i] - expected[i]) > 1.0e-6F) {
                    throw std::runtime_error(std::string("B2 output: ") + shape.name + " index=" + std::to_string(i));
                }
            }

            // 明确逐条记录原 B2 消费同一文件的结果。
            std::cout << "PASS B2 compatibility case=" << shape.name << '\n';
        }

        // 该结果是数值兼容性，不用作优化 CPU 性能基线或 FPGA 加速比。
        std::cout << "B2/B3 shared-input compatibility PASS cases=15\n";

        // 所有保存的合法输入均通过后才返回成功。
        return 0;
    } catch (const std::exception& error) {

        // 输入字节已保存在 vectors/generated，可直接复查首个错误。
        std::cerr << "B2 compatibility FAIL: " << error.what() << '\n';

        // 非零退出使脚本和验收者不会误读为通过。
        return 1;
    }
}
