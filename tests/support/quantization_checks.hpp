// 量化参考使用明确手算码作为期望值，绝不调用待测核或导出器生成期望。
#ifndef B01_QUANTIZATION_CHECKS_HPP
#define B01_QUANTIZATION_CHECKS_HPP
#include "../../reference/quantization.hpp"
#include <cfenv>
#include <limits>
#include <iostream>

inline unsigned run_quantization_checks() {
    unsigned checks = 0;
    auto verify = [&](bool result, const char* label) { if (!result) throw std::runtime_error(label); ++checks; };
    const float raw[] = {0.5F,1.5F,2.5F,3.5F,6.5F,-0.5F,-1.5F,-2.5F,-3.5F,-6.5F,7.0F,-7.0F};
    const int expected[] = {0,2,2,4,6,0,-2,-2,-4,-6,7,-7};
    for (unsigned i=0; i<12; ++i) verify(reference_b::round_code(raw[i],1.0F,7)==expected[i],"W4 ties-to-even");
    verify(reference_b::round_code(126.5F,1.0F,127)==126,"A8 even tie positive");
    verify(reference_b::round_code(-126.5F,1.0F,127)==-126,"A8 even tie negative");
    verify(reference_b::round_code(10000.0F,1.0F,7)==7,"W4 clipping");
    verify(reference_b::round_code(-10000.0F,1.0F,127)==-127,"A8 clipping");
    // 改变环境整数舍入模式时显式半值取偶数保持结果，完成后恢复。
    const int saved = std::fegetround();
    std::fesetround(FE_UPWARD);
    verify(reference_b::round_code(2.5F,1.0F,7)==2,"ambient rounding independence");
    std::fesetround(saved);
    std::vector<float> weights(129,0.0F);
    weights[128]=14.0F;
    std::vector<std::int8_t> codes;
    std::vector<float> scales;
    reference_b::quantize_weights(weights,1,129,codes,scales);
    verify(scales[0]==1.0F && scales[1]==2.0F && codes[0]==0 && codes[128]==7,"zero group and K tail absmax");
    std::vector<float> inputs={127.0F,-127.0F,1.5F};
    reference_b::quantize_inputs(inputs,1,3,codes,scales);
    verify(scales[0]==1.0F && codes[0]==127 && codes[1]==-127 && codes[2]==2 && codes[127]==0,"A8 row scale and padding");
    reference_b::quantize_inputs(std::vector<float>(3,0.0F),1,3,codes,scales);
    verify(scales[0]==1.0F && codes[0]==0,"zero A8 scale");
    const float bad[]={std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity(),-std::numeric_limits<float>::infinity()};
    for (float value:bad) {
        bool rejected=false;
        try { reference_b::quantize_weights(std::vector<float>(1,value),1,1,codes,scales); } catch(const std::invalid_argument&) { rejected=true; }
        verify(rejected,"nonfinite raw weight");
        rejected=false;
        try { reference_b::quantize_inputs(std::vector<float>(1,value),1,1,codes,scales); } catch(const std::invalid_argument&) { rejected=true; }
        verify(rejected,"nonfinite raw activation");
    }
    verify(128*7*127==113792,"INT32 group bound");
    std::cout << "PASS quantization checks=" << checks << " execution=HOST_REFERENCE\n";
    return checks;
}
#endif
