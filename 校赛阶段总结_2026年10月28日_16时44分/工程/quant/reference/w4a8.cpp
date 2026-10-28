#include "w4a8.hpp"
#include <algorithm>
#include <cfenv>
#include <cmath>
#include <limits>
#include <stdexcept>
namespace a04 {
static void require(bool v,const char *m){if(!v)throw std::invalid_argument(m);}
Shape::Shape(uint64_t n_,uint64_t k_,uint64_t t_) {
    require(n_>=1&&n_<=4864&&k_>=1&&k_<=4864&&t_>=1&&t_<=8,"shape rejected before sizing");
    n=int(n_);k=int(k_);t=int(t_);np=(n+31)/32*32;kp=(k+127)/128*128;g=kp/128;
}
void environment(){
    require(sizeof(float)==4&&std::numeric_limits<float>::is_iec559,"IEEE binary32 required");
    uint16_t word=1;require(*reinterpret_cast<uint8_t*>(&word)==1,"little endian required");
    require(std::fesetround(FE_TONEAREST)==0&&std::fegetround()==FE_TONEAREST,"rounding environment");
    volatile float tiny=std::numeric_limits<float>::denorm_min();
    volatile float one=1.0f;volatile float retained=tiny*one;
    require(retained==tiny&&retained>0,"FTZ/DAZ not supported by this reference");
}
static float scale(float mx,float div){
    const float s=mx==0?1.0f:mx/div;
    require(std::isfinite(s)&&s>0,"scale underflow/nonfinite");return s;
}
static int code(float v,float s,int limit){
    require(std::isfinite(v),"nonfinite input");
    const float normalized=v/s;
    require(std::isfinite(normalized),"normalization overflow");
    const float nearest=std::nearbyint(normalized);
    return int(std::max(float(-limit),std::min(float(limit),nearest)));
}
void pack(const Shape &a,const std::vector<float>&v,std::vector<uint8_t>&w,std::vector<float>&sw){
    require(v.size()==size_t(a.n)*a.k,"weight length");
    w.assign(size_t(a.np)*a.kp/2,0);sw.assign(size_t(a.np)*a.g,1);
    for(int row=0;row<a.n;++row)for(int group=0;group<a.g;++group){
        const int end=std::min(a.k,(group+1)*128);float maximum=0;
        for(int j=group*128;j<end;++j){const float x=v[row*a.k+j];require(std::isfinite(x),"nonfinite weight");maximum=std::max(maximum,std::abs(x));}
        const float s=scale(maximum,7);sw[(row/32*a.g+group)*32+row%32]=s;
        for(int j=group*128;j<end;++j){
            const int q=code(v[row*a.k+j],s,7);
            const size_t offset=((row/32*a.g+group)*128+j%128)*16+(row%32)/2;
            w[offset]|=uint8_t((q&15)<<(4*(row%2)));
        }
    }
}
void activation(const Shape&a,const std::vector<float>&v,std::vector<int8_t>&q,std::vector<float>&sx){
    require(v.size()==size_t(a.t)*a.k,"activation length");q.assign(size_t(a.t)*a.kp,0);sx.resize(a.t);
    for(int t=0;t<a.t;++t){float maximum=0;
        for(int k=0;k<a.k;++k){float x=v[t*a.k+k];require(std::isfinite(x),"nonfinite activation");maximum=std::max(maximum,std::abs(x));}
        sx[t]=scale(maximum,127);
        for(int k=0;k<a.k;++k)q[t*a.kp+k]=int8_t(code(v[t*a.k+k],sx[t],127));
    }
}
static int nibble(uint8_t b,int high){int v=(b>>(4*high))&15;return v>=8?v-16:v;}
void validate(const Shape&a,const std::vector<uint8_t>&w,const std::vector<float>&sw,const std::vector<int8_t>&x,const std::vector<float>&sx){
    require(w.size()==size_t(a.np)*a.kp/2&&sw.size()==size_t(a.np)*a.g&&x.size()==size_t(a.t)*a.kp&&sx.size()==size_t(a.t),"buffer length");
    for(float v:sw)require(std::isfinite(v)&&v>0,"bad Sw");
    for(float v:sx)require(std::isfinite(v)&&v>0,"bad Sx");
    for(int t=0;t<a.t;++t)for(int k=0;k<a.kp;++k)require(x[t*a.kp+k]!=-128&&(k<a.k||x[t*a.kp+k]==0),"reserved A8/tail");
    for(int n=0;n<a.np;++n)for(int k=0;k<a.kp;++k){
        const auto off=((n/32*a.g+k/128)*128+k%128)*16+(n%32)/2;
        const int q=nibble(w[off],n%2);
        require(q!=-8&&((n<a.n&&k<a.k)||q==0),"reserved W4/tail");
    }
    for(int n=a.n;n<a.np;++n)for(int g=0;g<a.g;++g)require(sw[(n/32*a.g+g)*32+n%32]==1,"padding scale");
}
// Deliberately simple row-first independent C++ reference. All stores are FP32;
// compile with -fno-fast-math -ffp-contract=off, not a reassociated dot product.
void scalar(const Shape&a,const uint8_t*w,const float*sw,const int8_t*x,const float*sx,float*y,int32_t*sums){
    std::fill(y,y+a.t*a.np,0);
    for(int t=0;t<a.t;++t)for(int n=0;n<a.np;++n)for(int g=0;g<a.g;++g){
        int32_t acc=0;
        for(int k=0;k<128;++k){const auto off=((n/32*a.g+g)*128+k)*16+(n%32)/2;acc+=nibble(w[off],n%2)*int(x[t*a.kp+g*128+k]);}
        sums[(t*a.np+n)*a.g+g]=acc;
        const float weighted=float(acc)*sw[(n/32*a.g+g)*32+n%32];
        const float restored=weighted*sx[t];const float total=y[t*a.np+n]+restored;
        require(std::isfinite(weighted)&&std::isfinite(restored)&&std::isfinite(total),"FP32 restore overflow");
        y[t*a.np+n]=total;
    }
}
// Contiguous packed reads + 32 independent integer lanes, reused over T. No
// full-model repacking, heap allocation, or FP32 group reassociation in run.
void tiled(const Shape&a,const uint8_t*w,const float*sw,const int8_t*x,const float*sx,float*y,int32_t*sums){
    std::fill(y,y+a.t*a.np,0);
    for(int tile=0;tile<a.np/32;++tile)for(int g=0;g<a.g;++g){
        alignas(64) int32_t acc[8][32]{};
        for(int k=0;k<128;++k){
            alignas(64) int32_t lane[32];const auto *p=w+((tile*a.g+g)*128+k)*16;
            for(int pair=0;pair<16;++pair){lane[2*pair]=nibble(p[pair],0);lane[2*pair+1]=nibble(p[pair],1);}
            for(int t=0;t<a.t;++t){const int32_t xv=x[t*a.kp+g*128+k];for(int l=0;l<32;++l)acc[t][l]+=lane[l]*xv;}
        }
        for(int t=0;t<a.t;++t)for(int l=0;l<32;++l){
            const int n=tile*32+l;sums[(t*a.np+n)*a.g+g]=acc[t][l];
            const float weighted=float(acc[t][l])*sw[(tile*a.g+g)*32+l];
            const float restored=weighted*sx[t];const float total=y[t*a.np+n]+restored;
            require(std::isfinite(weighted)&&std::isfinite(restored)&&std::isfinite(total),"FP32 restore overflow");y[t*a.np+n]=total;
        }
    }
}
}
