#include "host_contract.hpp"
#include <cmath>
#include <limits>

namespace a07 {
int layout(uint32_t n,uint32_t k,uint32_t t,Layout&o) noexcept {
    o={};
    if(!n||n>SP_LINEAR_MAX_NK||!k||k>SP_LINEAR_MAX_NK||!t||t>SP_LINEAR_MAX_T)return SP_BAD_ARGUMENT;
    o.n=n;o.k=k;o.t=t;o.np=(n+31)/32*32;o.kp=(k+127)/128*128;o.g=o.kp/128;
    o.w=uint64_t(o.np)*o.kp/2;o.sw=uint64_t(o.np)*o.g*4;
    o.x=uint64_t(t)*o.kp;o.sx=uint64_t(t)*4;o.y=uint64_t(t)*o.np*4;
    return SP_OK;
}
static bool valid(const Layout&a) noexcept {
    Layout b;return layout(a.n,a.k,a.t,b)==SP_OK && a.np==b.np&&a.kp==b.kp&&a.g==b.g&&
        a.w==b.w&&a.sw==b.sw&&a.x==b.x&&a.sx==b.sx&&a.y==b.y;
}
static bool aligned(const float*p) noexcept {return reinterpret_cast<uintptr_t>(p)%alignof(float)==0;}
int weights(const Layout&a,const uint8_t*w,uint64_t wb,const float*sw,uint64_t sb) noexcept {
    if(!valid(a)||!w||!sw||!aligned(sw))return SP_BAD_ARGUMENT;
    if(wb<a.w||sb<a.sw)return SP_BUFFER_TOO_SMALL;
    // Validate packed bytes once, before ownership is transferred to resident BOs.
    for(uint32_t tile=0;tile<a.np/32;++tile)for(uint32_t g=0;g<a.g;++g){
        for(uint32_t lane=0;lane<32;++lane){
            float s=sw[(uint64_t(tile)*a.g+g)*32+lane];
            if(!std::isfinite(s)||s<=0||(tile*32+lane>=a.n&&s!=1.f))return SP_NUMERIC_ERROR;
        }
        for(uint32_t k=0;k<128;++k)for(uint32_t pair=0;pair<16;++pair){
            auto packed=w[((uint64_t(tile)*a.g+g)*128+k)*16+pair];
            for(uint32_t h=0;h<2;++h){unsigned code=(packed>>(4*h))&15;
                if(code==8 || ((tile*32+pair*2+h>=a.n||g*128+k>=a.k)&&code!=0))return SP_NUMERIC_ERROR;
            }
        }
    }
    return SP_OK;
}
int inputs(const Layout&a,const int8_t*x,uint64_t xb,const float*sx,uint64_t sb,const float*y,uint64_t yb) noexcept {
    if(!valid(a)||!x||!sx||!y||!aligned(sx)||!aligned(y))return SP_BAD_ARGUMENT;
    if(xb<a.x||sb<a.sx||yb<a.y)return SP_BUFFER_TOO_SMALL;
    for(uint32_t t=0;t<a.t;++t){
        if(!std::isfinite(sx[t])||sx[t]<=0)return SP_NUMERIC_ERROR;
        for(uint32_t k=0;k<a.kp;++k){auto v=x[uint64_t(t)*a.kp+k];
            if(v==-128||(k>=a.k&&v!=0))return SP_NUMERIC_ERROR;
        }
    }
    return SP_OK;
}
int output(const Layout&a,const float*y,uint64_t yb) noexcept {
    if(!valid(a)||!y||!aligned(y))return SP_BAD_ARGUMENT;
    if(yb<a.y)return SP_BUFFER_TOO_SMALL;
    for(uint32_t t=0;t<a.t;++t)for(uint32_t n=0;n<a.np;++n){float v=y[uint64_t(t)*a.np+n];
        if(!std::isfinite(v)||(n>=a.n&&v!=0.f))return SP_NUMERIC_ERROR;
    }
    return SP_OK;
}
int private_status(uint32_t s) noexcept {
    constexpr int statuses[]={SP_OK,SP_CONTRACT_MISMATCH,SP_BAD_ARGUMENT,SP_BUFFER_TOO_SMALL,SP_BAD_ARGUMENT,SP_NUMERIC_ERROR};
    return s<6?statuses[s]:SP_DEVICE_ERROR;
}
uint64_t read_le(const uint8_t*p,size_t n) noexcept {
    uint64_t v=0;for(size_t i=0;i<n&&i<8;++i)v|=uint64_t(p[i])<<(i*8);return v;
}
void write_le(uint8_t*p,uint64_t v,size_t n) noexcept {for(size_t i=0;i<n&&i<8;++i)p[i]=uint8_t(v>>(8*i));}
int validate_meta(const uint8_t*p,uint64_t bytes,uint32_t build,uint64_t job,uint64_t seed,uint64_t w) noexcept {
    if(!p||bytes<meta_bytes)return SP_BUFFER_TOO_SMALL;
    if(!job||!build)return SP_BAD_ARGUMENT;
    if(read_le(p,4)!=magic||read_le(p+4,4)!=build||read_le(p+8,8)!=job)return SP_CONTRACT_MISMATCH;
    const auto status=uint32_t(read_le(p+16,4));
    if(status>5)return SP_DEVICE_ERROR;
    // Validate even error completions; done=1 does not imply success.
    // The private uint64 counter wraps modulo 2^64, and is unchanged on error.
    const uint64_t count=status==0?seed+uint64_t(1):seed;
    const uint64_t algorithm_bytes=(status==1||status==2)?0:w;
    if(read_le(p+20,4)!=1||read_le(p+24,8)!=count||read_le(p+32,8)!=algorithm_bytes)return SP_DEVICE_ERROR;
    return private_status(status);
}
bool fits_budget(uint64_t b,uint64_t used,uint64_t req) noexcept {return b&&used<=b&&req<=b-used;}
bool in_window(uint64_t base,uint64_t span,uint64_t address,uint64_t bytes) noexcept {
    return span&&bytes&&span<=UINT64_MAX-base&&address>=base&&address-base<span&&bytes<=span-(address-base);
}
int Lifecycle::idle() const noexcept {return phase_==Phase::READY?SP_OK:phase_==Phase::RUNNING?SP_BUSY:SP_POISONED;}
int Lifecycle::begin(uint64_t j,uint32_t timeout) noexcept {
    if(int rc=idle())return rc;
    if(!j||j<=job_||!timeout)return SP_BAD_ARGUMENT;
    job_=j;phase_=Phase::RUNNING;return SP_OK;
}
int Lifecycle::completed_and_validated() noexcept {
    if(phase_==Phase::POISONED)return SP_POISONED;
    if(phase_!=Phase::RUNNING)return SP_BAD_ARGUMENT;
    phase_=Phase::READY;return SP_OK;
}
}
