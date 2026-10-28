#pragma once
#include "w4a8.hpp"
#include <algorithm>
#include <cmath>
#include <stdexcept>
#if defined(__x86_64__) && defined(__GNUC__)
#include <immintrin.h>
// Runtime-dispatched PC optimization; no compiler-wide ISA or FP reassociation.
// Packed bytes stay packed in storage. Four vectors represent 32 independent N lanes.
__attribute__((target("avx2"))) static void avx2_tile(
    const a04::Shape&a,const uint8_t*w,const float*sw,const int8_t*x,const float*sx,float*y,int32_t*sums){
    std::fill_n(y,a.t*32,0.f);
    const __m128i mask=_mm_set1_epi8(15),sign=_mm_set1_epi8(8);
    for(int g=0;g<a.g;++g){
        __m256i acc[8][4];for(int t=0;t<a.t;++t)for(int i=0;i<4;++i)acc[t][i]=_mm256_setzero_si256();
        for(int k=0;k<128;++k){
            const __m128i p=_mm_loadu_si128(reinterpret_cast<const __m128i*>(w+(g*128+k)*16));
            const __m128i lo=_mm_sub_epi8(_mm_xor_si128(_mm_and_si128(p,mask),sign),sign);
            const __m128i hi=_mm_sub_epi8(_mm_xor_si128(_mm_and_si128(_mm_srli_epi16(p,4),mask),sign),sign);
            const __m128i a0=_mm_unpacklo_epi8(lo,hi),a1=_mm_unpackhi_epi8(lo,hi);
            const __m256i lanes[4]={_mm256_cvtepi8_epi32(a0),_mm256_cvtepi8_epi32(_mm_srli_si128(a0,8)),_mm256_cvtepi8_epi32(a1),_mm256_cvtepi8_epi32(_mm_srli_si128(a1,8))};
            for(int t=0;t<a.t;++t){const __m256i v=_mm256_set1_epi32(x[t*a.kp+g*128+k]);
                for(int i=0;i<4;++i)acc[t][i]=_mm256_add_epi32(acc[t][i],_mm256_mullo_epi32(lanes[i],v));}
        }
        for(int t=0;t<a.t;++t){alignas(32) int32_t v[32];for(int i=0;i<4;++i)_mm256_store_si256(reinterpret_cast<__m256i*>(v+8*i),acc[t][i]);
            // The current group's v/acc remain required. Only the optional
            // diagnostic history store is omitted; FP32 order is unchanged.
            for(int l=0;l<32;++l){if(sums)sums[(t*32+l)*a.g+g]=v[l];const float weighted=float(v[l])*sw[g*32+l];const float restored=weighted*sx[t];const float total=y[t*32+l]+restored;
                if(!std::isfinite(weighted)||!std::isfinite(restored)||!std::isfinite(total))throw std::invalid_argument("SIMD restore overflow");y[t*32+l]=total;}}
    }
}
static bool have_avx2(){return __builtin_cpu_supports("avx2");}
#else
static bool have_avx2(){return false;}
#endif
static void cpu_tile(const a04::Shape&a,const uint8_t*w,const float*sw,const int8_t*x,const float*sx,float*y,int32_t*sums){
#if defined(__x86_64__) && defined(__GNUC__)
    if(have_avx2()){avx2_tile(a,w,sw,x,sx,y,sums);return;}
#endif
    // Keep the independent reference unchanged. A portable caller without
    // diagnostic storage still supplies bounded scratch to that reference.
    if(sums)a04::tiled(a,w,sw,x,sx,y,sums);
    else {int32_t scratch[8*32*38];a04::tiled(a,w,sw,x,sx,y,scratch);}
}
