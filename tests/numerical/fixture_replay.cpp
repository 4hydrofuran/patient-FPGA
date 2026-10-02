// B00 回放公共固定字节样例，并检查错误时输出和成功计数保持不变。
#include "../../src/w4a8_linear_v1.hpp"
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>

// 精确加载固定文件，短文件或额外内容均判定为失败。
template <typename T> std::vector<T> load(const char* path, std::size_t count) {
    std::ifstream input(path, std::ios::binary);
    std::vector<T> values(count);
    if (!input.read(reinterpret_cast<char*>(values.data()), count * sizeof(T)) || input.peek() != std::char_traits<char>::eof()) {
        throw std::runtime_error(path);
    }
    return values;
}

// 将失败转换为非零退出码，不继续消费输出。
void check(bool condition, const char* label) {
    if (!condition) throw std::runtime_error(label);
}

int main() {
    try {
        // 样例来自公共 fixture，期望值未由 HLS 核生成。
        auto weights = load<std::uint8_t>("fixtures/w_packed.bin", 2048);
        auto scales = load<float>("fixtures/sw.bin", 32);
        auto inputs = load<std::int8_t>("fixtures/xq.bin", 128);
        auto sx = load<float>("fixtures/sx.bin", 1);
        auto expected = load<float>("fixtures/expected_y.bin", 32);
        std::vector<float> output(32, -1234.5F);
        w4a8_b2::KernelMeta meta{};

        // 调用继承核，只验证固定样例，不代表公共 C 动态库已实现。
        auto run = [&](std::uint64_t job, std::uint64_t xbytes) {
            w4a8_linear_v1(weights.data(), scales.data(), inputs.data(), sx.data(), output.data(), &meta,
                           1, 2, 2, 2048, 128, xbytes, 4, 128, 40, job, 1);
        };
        run(100, 128);
        check(output == expected, "public fixture output");
        check(meta.status == 0 && meta.done == 1 && meta.job_id == 100 && meta.hw_completed_count == 1, "success metadata");
        const auto saved = output;

        // 有效区域出现 W4 保留码时，输出不得部分覆盖。
        weights[0] = (weights[0] & 0xf0U) | 8U;
        run(101, 128);
        check(meta.status == 5 && meta.job_id == 101 && meta.hw_completed_count == 1 && output == saved, "reserved weight error");

        // 短输入长度优先拒绝，同样保留输出和成功计数。
        run(102, 127);
        check(meta.status == 3 && meta.job_id == 102 && meta.hw_completed_count == 1 && output == saved, "short input error");
        std::cout << "B00 fixture PASS transactions=3 output_checks=32 source=public_hand_fixture execution=PC_NATIVE\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "B00 fixture FAIL " << error.what() << '\n';
        return 1;
    }
}
