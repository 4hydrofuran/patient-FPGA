// 补交回放：从原始RTL输入独立展开矩阵，再用dense golden核对实际Y/meta；不链接待测核。
#include "../../tb/golden_w4a8.hpp"
#include <cmath>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

// 固定私有meta的40字节布局；这些常量来自冻结ABI而非HLS函数。
struct Meta {
    std::uint32_t magic, build;
    std::uint64_t job;
    std::uint32_t status, done;
    std::uint64_t completed, weight_bytes;
};
static_assert(sizeof(Meta) == 40, "private meta must be 40 bytes");

// 二进制读写都检查实际长度，缺文件不能当作数值通过。
std::vector<unsigned char> read(const std::filesystem::path& path) {
    std::ifstream input(path, std::ios::binary);
    if (!input) throw std::runtime_error("cannot open " + path.u8string());
    return std::vector<unsigned char>(std::istreambuf_iterator<char>(input), {});
}
void save(const std::filesystem::path& path, const void* data, std::size_t size) {
    std::ofstream output(path, std::ios::binary);
    output.write(static_cast<const char*>(data), static_cast<std::streamsize>(size));
    if (!output) throw std::runtime_error("cannot save " + path.u8string());
}
float fp32(const std::vector<unsigned char>& bytes, std::size_t offset) {
    if (offset + 4 > bytes.size()) throw std::runtime_error("FP32 input window too short");
    float result;
    std::memcpy(&result, bytes.data() + offset, 4);
    return result;
}

// 一个目录对应一笔真实事务；失败返回非零且保留该目录供定位。
int main(int argc, char** argv) {
    try {
        if (argc != 2) throw std::runtime_error("usage: replay_archived_rtl <transaction directory>");
        const std::uint16_t endian = 1;
        if (*reinterpret_cast<const unsigned char*>(&endian) != 1) throw std::runtime_error("little-endian host required");
        const std::filesystem::path folder = std::filesystem::u8path(argv[1]);
        std::uint64_t t, n, k, abi, wb, swb, xb, sxb, yb, mb, job;
        std::ifstream parameters(folder / "request.txt");
        if (!(parameters >> t >> n >> k >> abi >> wb >> swb >> xb >> sxb >> yb >> mb >> job))
            throw std::runtime_error("missing scalar request");
        const auto w = read(folder / "w.bin");
        const auto sw = read(folder / "sw.bin");
        const auto xbytes = read(folder / "x.bin");
        const auto sx = read(folder / "sx.bin");
        const auto before = read(folder / "y_before.bin");
        const auto observed = read(folder / "y_actual.bin");
        const auto meta_before = read(folder / "meta_before.bin");
        const auto meta_actual = read(folder / "meta_actual.bin");
        if (meta_before.size() != 40 || meta_actual.size() != 40 || before.size() != observed.size())
            throw std::runtime_error("wrong actual meta/Y length");
        Meta previous{}, actual{};
        std::memcpy(&previous, meta_before.data(), 40);
        std::memcpy(&actual, meta_actual.data(), 40);
        Meta expected{0x57344138U, 0xB3030002U, job, 0, 1, previous.completed, 0};
        std::uint64_t np = 0, kp = 0, groups = 0;

        // 按冻结错误优先级检查；失败事务只允许写meta，Y全窗口保持原值。
        if (mb < 40) expected = previous;
        else if (abi != 1) expected.status = 1;
        else if (!t || t > 8 || !n || n > 4864 || !k || k > 4864) expected.status = 2;
        else {
            np = (n + 31) / 32 * 32;
            kp = (k + 127) / 128 * 128;
            groups = kp / 128;
            expected.weight_bytes = np * kp / 2;
            if (wb < expected.weight_bytes || swb < np * groups * 4 || xb < t * kp || sxb < t * 4 || yb < t * np * 4)
                expected.status = 3;
            else {
                if (w.size() < expected.weight_bytes || sw.size() < np * groups * 4 || xbytes.size() < t * kp || sx.size() < t * 4)
                    throw std::runtime_error("raw input memory window too short");
                // 只检查有效N/K的保留码，padding中的-8保持原私有核语义。
                for (std::uint64_t row = 0; row < n; ++row)
                    for (std::uint64_t col = 0; col < k; ++col) {
                        const auto offset = ((row / 32 * groups + col / 128) * 128 + col % 128) * 16 + row % 32 / 2;
                        const unsigned nibble = (w.at(offset) >> ((row % 2) * 4)) & 15;
                        if (nibble == 8) expected.status = 5;
                    }
            }
        }
        auto expected_y = before;
        GoldenResult golden;
        if (mb >= 40 && expected.status == 0) {
            // 从合同定义直接展开未打包行主序矩阵，不调用HLS的解码或寻址辅助函数。
            std::vector<std::int8_t> dense_w(n * k), x(t * kp);
            std::vector<float> dense_sw(np * groups, 1.0F), token_scale(t);
            for (std::uint64_t row = 0; row < n; ++row) {
                for (std::uint64_t col = 0; col < k; ++col) {
                    const auto offset = ((row / 32 * groups + col / 128) * 128 + col % 128) * 16 + row % 32 / 2;
                    const int nibble = (w.at(offset) >> ((row % 2) * 4)) & 15;
                    dense_w[row * k + col] = static_cast<std::int8_t>(nibble < 8 ? nibble : nibble - 16);
                }
                for (std::uint64_t group = 0; group < groups; ++group)
                    dense_sw[row * groups + group] = fp32(sw, ((row / 32 * groups + group) * 32 + row % 32) * 4);
            }
            std::memcpy(x.data(), xbytes.data(), x.size());
            for (std::uint64_t token = 0; token < t; ++token) token_scale[token] = fp32(sx, token * 4);
            golden = golden_dense(t, n, k, np, kp, dense_w, dense_sw, x, token_scale);
            if (before.size() < golden.y.size() * 4) throw std::runtime_error("raw output window too short");
            std::memcpy(expected_y.data(), golden.y.data(), golden.y.size() * 4);
            ++expected.completed;
            // 原小例与目标/尾块分别使用原有容差，不把仿真输出拿来生成expected。
            std::ifstream tolerance_file(folder / "tolerance.txt");
            float atol = 0, rtol = 0;
            if (!(tolerance_file >> atol >> rtol)) throw std::runtime_error("missing original tolerance");
            for (std::size_t i = 0; i < golden.y.size(); ++i) {
                const float y = fp32(observed, i * 4), reference = golden.y[i];
                if (!std::isfinite(y) || !std::isfinite(reference) || std::fabs(y - reference) > atol + rtol * std::fabs(reference))
                    throw std::runtime_error("RTL Y mismatch at index " + std::to_string(i));
            }
            if (std::memcmp(observed.data() + golden.y.size() * 4, before.data() + golden.y.size() * 4,
                            before.size() - golden.y.size() * 4) != 0)
                throw std::runtime_error("RTL wrote outside output window");
        } else if (observed != before) throw std::runtime_error("error transaction modified Y");
        if (std::memcmp(&actual, &expected, 40) != 0) throw std::runtime_error("RTL meta mismatch");

        // 独立expected落盘；部分和仅为dense参考值，不声称观测RTL内部部分和。
        save(folder / "expected_y.bin", expected_y.data(), expected_y.size());
        save(folder / "expected_meta.bin", &expected, 40);
        save(folder / "expected_partials.bin", golden.partials.data(), golden.partials.size() * 4);
        std::cout << "PASS status=" << expected.status << " values=" << golden.y.size() << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << '\n';
        return 1;
    }
}
