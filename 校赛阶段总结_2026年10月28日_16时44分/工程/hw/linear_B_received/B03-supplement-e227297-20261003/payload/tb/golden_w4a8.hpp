// B3 独立整数 golden：只读取未打包的行主序矩阵，不调用核的解码或寻址函数。
#ifndef B3_GOLDEN_W4A8_HPP
#define B3_GOLDEN_W4A8_HPP

// 固定宽度整数使向量文件与主机平台的 long 宽度无关。
#include <cstdint>

// 向量仅用于 PC testbench，不进入可综合核。
#include <vector>

// 保存每组精确整数和与按冻结顺序恢复的 FP32 输出。
struct GoldenResult {
    std::vector<std::int32_t> partials;
    std::vector<float> y;
};

// 输入权重和 scale 都采用独立行主序表示；padding 权重由数学零值定义。
inline GoldenResult golden_dense(std::uint32_t t, std::uint32_t n, std::uint32_t k,
                                 std::uint32_t padded_n, std::uint32_t padded_k,
                                 const std::vector<std::int8_t>& dense_w,
                                 const std::vector<float>& dense_sw,
                                 const std::vector<std::int8_t>& xq,
                                 const std::vector<float>& sx) {

    // 不引用 HLS 头中的布局辅助函数，以独立数学定义计算量化组数。
    const std::uint32_t groups = padded_k / 128U;

    // 部分和顺序为 token、输出行、group，便于逐项错误定位。
    GoldenResult result{std::vector<std::int32_t>(static_cast<std::size_t>(t) * padded_n * groups, 0),
                        std::vector<float>(static_cast<std::size_t>(t) * padded_n, 0.0F)};

    // 每个 token 使用自己的激活及激活 scale。
    for (std::uint32_t token = 0; token < t; ++token) {

        // 仅对有效输出行计算，N padding 的 golden 保持零。
        for (std::uint32_t row = 0; row < n; ++row) {

            // 按 group 原顺序累加，避免把不同 scale 的整数和混在一起。
            float total = 0.0F;

            // 128 输入组成一个独立整数点积。
            for (std::uint32_t group = 0; group < groups; ++group) {

                // 使用 INT64 研究累加确认结果在 INT32 范围内，不依赖核的累加实现。
                std::int64_t sum = 0;

                // 最后一组只遍历真实 K，其余 padding 的数学值为零。
                const std::uint32_t end = (group + 1U) * 128U < k ? (group + 1U) * 128U : k;

                // 直接使用行主序权重，完全不读取 packed 缓冲或半字节。
                for (std::uint32_t col = group * 128U; col < end; ++col) {

                    // 显式转为宽整数后相乘，以普通 C++ 精确数学生成期望值。
                    sum += static_cast<std::int64_t>(dense_w[static_cast<std::size_t>(row) * k + col]) *
                           static_cast<std::int64_t>(xq[static_cast<std::size_t>(token) * padded_k + col]);
                }

                // INT32 数值用于核实际数据通路的逐组检查。
                result.partials[(static_cast<std::size_t>(token) * padded_n + row) * groups + group] = static_cast<std::int32_t>(sum);

                // volatile 固定一次 FP32 舍入，禁止研究参考意外融合为另一种运算顺序。
                volatile float weight_scaled = static_cast<float>(sum) * dense_sw[static_cast<std::size_t>(row) * groups + group];

                // 激活 scale 在权重 scale 之后恢复，保持冻结的括号顺序。
                volatile float restored = weight_scaled * sx[token];

                // 当前输出按 group 顺序执行 FP32 加法。
                total += restored;
            }

            // 保留完整 padded 输出布局，供主机逐字节回放。
            result.y[static_cast<std::size_t>(token) * padded_n + row] = total;
        }
    }

    // 独立期望值与 HLS 函数没有共享数学循环。
    return result;
}

#endif
