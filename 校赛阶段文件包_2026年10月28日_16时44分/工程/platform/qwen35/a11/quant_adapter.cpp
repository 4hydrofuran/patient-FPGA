// Quantization only. No projection, XRT, golden output or CPU fallback.
#include "w4a8.hpp"
#include <cstring>
extern "C" int a11_quant(unsigned n,unsigned k,unsigned t,const float* x,
                         unsigned long long xb,void* q,unsigned long long qb,
                         float* s,unsigned long long sb) noexcept {
    try {
        if(!x||!q||!s||!n||n>4864||!k||k>4864||!t||t>8)return 1;
        a04::Shape shape(n,k,t);
        if(xb!=t*k*4ULL||qb!=t*shape.kp||sb!=t*4ULL)return 1;
        a04::environment();
        thread_local std::vector<float> input,scales;
        thread_local std::vector<int8_t> quantized;
        input.assign(x,x+t*k);
        a04::activation(shape,input,quantized,scales);
        std::memcpy(q,quantized.data(),qb);std::memcpy(s,scales.data(),sb);
        return 0;
    } catch(...) {return 1;}
}
