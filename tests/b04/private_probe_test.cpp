// B04：独立构造小端记录，验证尺寸、错误和陈旧完成记录；不调用被测核生成期望值。
#include "../../host/b04_private_probe.hpp"
#include <array>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
unsigned checks = 0;

// 失败打印精确用例，退出非零，保留运行日志。
void check(bool condition, const char* name) {
    ++checks;
    if (!condition) throw std::runtime_error(name);
}

// 写字节的实现与读取器独立，固定每个字段的规范偏移。
void write_le(std::array<std::uint8_t, 41>& bytes, unsigned offset,
              std::uint64_t value, unsigned width) {
    for (unsigned i = 0; i < width; ++i) bytes[offset + i] = std::uint8_t(value >> (i * 8U));
}

// 使用未对齐起点，覆盖 ARM 主机上不能直接结构强转的场景。
std::array<std::uint8_t, 41> record(std::uint32_t status = 0,
                                    std::uint64_t count = 8,
                                    std::uint64_t weight = 2048) {
    std::array<std::uint8_t, 41> bytes{};
    write_le(bytes, 1, 0x57344138U, 4);
    write_le(bytes, 5, 0xB3030002U, 4);
    write_le(bytes, 9, 123, 8);
    write_le(bytes, 17, status, 4);
    write_le(bytes, 21, 1, 4);
    write_le(bytes, 25, count, 8);
    write_le(bytes, 33, weight, 8);
    return bytes;
}

// 除对应故障字段外保持成功记录不变，证明每项校验能独立拒绝。
void reject_field(unsigned offset, std::uint64_t value, unsigned width,
                  b04::MetaIssue expected, const char* name) {
    auto bytes = record();
    write_le(bytes, offset + 1, value, width);
    const auto result = b04::inspect_completion(bytes.data() + 1, 40, 123, 7, 2048);
    check(!result.consume_y && result.public_status != SP_OK && result.issue == expected, name);
}
}  // namespace

// CPU 控制层验收与后续 XRT/PL 验收分开记录。
int main() {
    try {
        b04::BufferSizes sizes;
        check(b04::required_sizes(1, 1, 1, &sizes) == SP_OK && sizes.np == 32 && sizes.kp == 128
              && sizes.w == 2048 && sizes.sw == 128 && sizes.x == 128 && sizes.sx == 4 && sizes.y == 128, "minimum tail");
        check(b04::required_sizes(8, 4864, 4864, &sizes) == SP_OK && sizes.np == 4864 && sizes.kp == 4864
              && sizes.w == 11829248 && sizes.sw == 739328 && sizes.x == 38912 && sizes.y == 155648, "maximum");
        check(b04::required_sizes(8, 3584, 1024, &sizes) == SP_OK && sizes.w == 1835008 && sizes.sw == 114688
              && sizes.x == 8192 && sizes.y == 114688 && sizes.sx == 32 && sizes.meta == 40, "gate/up T8");
        check(b04::required_sizes(8, 1024, 3584, &sizes) == SP_OK && sizes.w == 1835008 && sizes.sw == 114688
              && sizes.x == 28672 && sizes.y == 32768, "down T8");
        check(b04::required_sizes(8, 33, 129, &sizes) == SP_OK && sizes.np == 64 && sizes.kp == 256
              && sizes.w == 8192 && sizes.sw == 512, "double tail");
        for (auto t : {0U, 9U, std::numeric_limits<std::uint32_t>::max()})
            check(b04::required_sizes(t, 1, 1, &sizes) == SP_BAD_ARGUMENT, "bad T");
        for (auto dimension : {0U, 4865U, std::numeric_limits<std::uint32_t>::max()}) {
            check(b04::required_sizes(1, dimension, 1, &sizes) == SP_BAD_ARGUMENT, "bad N");
            check(b04::required_sizes(1, 1, dimension, &sizes) == SP_BAD_ARGUMENT, "bad K");
        }
        check(b04::required_sizes(1, 1, 1, nullptr) == SP_BAD_ARGUMENT, "null size output");
        auto bytes = record();
        auto result = b04::inspect_completion(bytes.data() + 1, 40, 123, 7, 2048);
        check(result.public_status == SP_OK && result.consume_y && result.meta.completed_count == 8, "valid unaligned meta");
        check(b04::inspect_completion(bytes.data() + 1, 39, 123, 7, 2048).public_status == SP_BUFFER_TOO_SMALL, "short meta");
        check(b04::inspect_completion(nullptr, 40, 123, 7, 2048).public_status == SP_BAD_ARGUMENT, "null meta");
        check(b04::inspect_completion(bytes.data() + 1, 40, 0, 7, 2048).public_status == SP_BAD_ARGUMENT, "zero job expectation");
        check(b04::inspect_completion(bytes.data() + 1, 40, 123, 7, 0).public_status == SP_BAD_ARGUMENT, "zero weight expectation");
        reject_field(0, 0, 4, b04::MetaIssue::wrong_magic, "wrong magic");
        reject_field(4, 0xB3030001U, 4, b04::MetaIssue::wrong_build, "reuse build rejected");
        reject_field(8, 122, 8, b04::MetaIssue::wrong_job, "stale job");
        reject_field(20, 0, 4, b04::MetaIssue::not_done, "unfinished");
        reject_field(20, 2, 4, b04::MetaIssue::not_done, "invalid done value");
        reject_field(16, 6, 4, b04::MetaIssue::unknown_status, "unknown private status");
        reject_field(24, 7, 8, b04::MetaIssue::wrong_counter, "success counter not advanced");
        reject_field(24, 9, 8, b04::MetaIssue::wrong_counter, "success counter jumped");
        reject_field(32, 2049, 8, b04::MetaIssue::wrong_weight_bytes, "wrong algorithm bytes");
        const std::int32_t expected_status[] = {SP_OK, SP_CONTRACT_MISMATCH, SP_BAD_ARGUMENT,
                                             SP_BUFFER_TOO_SMALL, SP_BAD_ARGUMENT, SP_NUMERIC_ERROR};
        for (unsigned status = 1; status <= 5; ++status) {
            bytes = record(status, 7, status <= 2 ? 0 : 2048);
            result = b04::inspect_completion(bytes.data() + 1, 40, 123, 7, 2048);
            check(result.public_status == expected_status[status] && !result.consume_y
                  && result.issue == b04::MetaIssue::kernel_rejected, "completed error must not consume Y");
            write_le(bytes, 25, 8, 8);
            result = b04::inspect_completion(bytes.data() + 1, 40, 123, 7, 2048);
            check(result.issue == b04::MetaIssue::wrong_counter && !result.consume_y, "error counter advanced");
        }
        bytes = record(0, 0);
        result = b04::inspect_completion(bytes.data() + 1, 40, 123, std::numeric_limits<std::uint64_t>::max(), 2048);
        check(result.consume_y && result.public_status == SP_OK, "unsigned counter wrap follows frozen ABI");
        std::cout << "B04 PRIVATE PROBE PASS checks=" << checks << "\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "B04 PRIVATE PROBE FAIL: " << error.what() << "\n";
        return 1;
    }
}
