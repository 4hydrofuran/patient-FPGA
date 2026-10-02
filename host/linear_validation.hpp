// B01 主机数值校验适配层；不是SP_LINEAR动态库实现，不改变私有核错误码。
#ifndef B01_LINEAR_VALIDATION_HPP
#define B01_LINEAR_VALIDATION_HPP
#include "../contracts/sp_linear_v1.h"
#include <cmath>
#include <cstdint>

namespace host_b {

// 普通用户态数组与字节长度，仅供启动硬件前校验，不能用作DMA地址。
struct Request {
    std::uint32_t t, n, k;
    const std::uint8_t* w;
    const float* sw;
    const std::int8_t* x;
    const float* sx;
    float* y;
    std::uint64_t wb, swb, xb, sxb, yb, job;
};

// 先检查维度、长度和指针，再读取内容；错误返回前不读写Y。
inline std::int32_t validate(const Request& r) {
    if (r.t == 0 || r.t > 8 || r.n == 0 || r.n > 4864 || r.k == 0 || r.k > 4864 || r.job == 0) return SP_BAD_ARGUMENT;
    const std::uint32_t np = (r.n + 31U) / 32U * 32U;
    const std::uint32_t kp = (r.k + 127U) / 128U * 128U;
    const std::uint32_t groups = kp / 128U;
    if (r.wb < static_cast<std::uint64_t>(np) * kp / 2U || r.swb < static_cast<std::uint64_t>(np) * groups * 4U ||
        r.xb < static_cast<std::uint64_t>(r.t) * kp || r.sxb < r.t * 4U || r.yb < static_cast<std::uint64_t>(r.t) * np * 4U) return SP_BUFFER_TOO_SMALL;
    if (!r.w || !r.sw || !r.x || !r.sx || !r.y) return SP_BAD_ARGUMENT;
    for (std::uint32_t token = 0; token < r.t; ++token) {
        if (!std::isfinite(r.sx[token]) || r.sx[token] <= 0.0F) return SP_NUMERIC_ERROR;
        for (std::uint32_t col = 0; col < kp; ++col) {
            const std::int8_t value = r.x[static_cast<std::size_t>(token) * kp + col];
            if (value == -128 || (col >= r.k && value != 0)) return SP_NUMERIC_ERROR;
        }
    }
    for (std::uint32_t row = 0; row < np; ++row) {
        for (std::uint32_t group = 0; group < groups; ++group) {
            const std::size_t scale_index = (static_cast<std::size_t>(row / 32U) * groups + group) * 32U + row % 32U;
            const float scale = r.sw[scale_index];
            if (!std::isfinite(scale) || scale <= 0.0F || (row >= r.n && scale != 1.0F)) return SP_NUMERIC_ERROR;
            for (std::uint32_t j = 0; j < 128U; ++j) {
                const std::size_t index = ((static_cast<std::size_t>(row / 32U) * groups + group) * 128U + j) * 16U + (row % 32U) / 2U;
                const std::uint8_t code = (r.w[index] >> ((row & 1U) * 4U)) & 15U;
                if (row < r.n && group * 128U + j < r.k) {
                    if (code == 8U) return SP_NUMERIC_ERROR;
                } else if (code != 0) return SP_NUMERIC_ERROR;
            }
        }
    }
    return SP_OK;
}
}
#endif
