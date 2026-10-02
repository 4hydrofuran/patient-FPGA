// B01 标量量化参考：只用于电脑/测试端，不进入可综合核。
#ifndef B01_QUANTIZATION_HPP
#define B01_QUANTIZATION_HPP
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace reference_b {

// 显式半值取偶数，不依赖进程当前的整数舍入模式；夹紧在整数转换前完成。
inline std::int8_t round_code(float value, float scale, int limit) {
    if (!std::isfinite(value) || !std::isfinite(scale) || scale <= 0.0F) {
        throw std::invalid_argument("nonfinite value or nonpositive scale");
    }
    const float quotient = value / scale;
    if (quotient >= limit) return static_cast<std::int8_t>(limit);
    if (quotient <= -limit) return static_cast<std::int8_t>(-limit);
    const double lower = std::floor(static_cast<double>(quotient));
    const double fraction = static_cast<double>(quotient) - lower;
    const bool advance = fraction > 0.5 || (fraction == 0.5 && std::fmod(std::fabs(lower), 2.0) != 0.0);
    return static_cast<std::int8_t>(lower + (advance ? 1.0 : 0.0));
}

// 全零才使用scale=1；非零极小值使FP32 scale下溢时明确拒绝。
inline float group_scale(const float* values, std::size_t count, int limit) {
    float maximum = 0.0F;
    for (std::size_t i = 0; i < count; ++i) {
        if (!std::isfinite(values[i])) throw std::invalid_argument("nonfinite raw input");
        maximum = std::max(maximum, std::fabs(values[i]));
    }
    const float scale = maximum == 0.0F ? 1.0F : maximum / static_cast<float>(limit);
    if (!std::isfinite(scale) || scale <= 0.0F) throw std::invalid_argument("unrepresentable scale");
    return scale;
}

// 权重输入为有效N×K行主序，不读取padding，也不调用HLS地址或解包函数。
inline void quantize_weights(const std::vector<float>& raw, std::uint32_t n, std::uint32_t k,
                             std::vector<std::int8_t>& codes, std::vector<float>& scales) {
    if (n == 0 || k == 0 || raw.size() != static_cast<std::size_t>(n) * k) throw std::invalid_argument("raw weight shape");
    const std::uint32_t groups = (k + 127U) / 128U;
    codes.assign(raw.size(), 0);
    scales.assign(static_cast<std::size_t>(n) * groups, 1.0F);
    for (std::uint32_t row = 0; row < n; ++row) {
        for (std::uint32_t group = 0; group < groups; ++group) {
            const std::uint32_t first = group * 128U;
            const std::uint32_t count = std::min(128U, k - first);
            const float scale = group_scale(raw.data() + static_cast<std::size_t>(row) * k + first, count, 7);
            scales[static_cast<std::size_t>(row) * groups + group] = scale;
            for (std::uint32_t j = 0; j < count; ++j) {
                codes[static_cast<std::size_t>(row) * k + first + j] = round_code(raw[static_cast<std::size_t>(row) * k + first + j], scale, 7);
            }
        }
    }
}

// 激活按每条有效输入行量化，并显式生成零padding的[T,Kp]。
inline void quantize_inputs(const std::vector<float>& raw, std::uint32_t t, std::uint32_t k,
                            std::vector<std::int8_t>& codes, std::vector<float>& scales) {
    if (t == 0 || k == 0 || raw.size() != static_cast<std::size_t>(t) * k) throw std::invalid_argument("raw input shape");
    const std::uint32_t kp = (k + 127U) / 128U * 128U;
    codes.assign(static_cast<std::size_t>(t) * kp, 0);
    scales.assign(t, 1.0F);
    for (std::uint32_t token = 0; token < t; ++token) {
        scales[token] = group_scale(raw.data() + static_cast<std::size_t>(token) * k, k, 127);
        for (std::uint32_t j = 0; j < k; ++j) {
            codes[static_cast<std::size_t>(token) * kp + j] = round_code(raw[static_cast<std::size_t>(token) * k + j], scales[token], 127);
        }
    }
}
}
#endif
