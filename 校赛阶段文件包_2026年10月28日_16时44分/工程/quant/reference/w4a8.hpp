#pragma once
#include <cstdint>
#include <vector>
namespace a04 {
struct Shape {
    int n,k,t,np,kp,g;
    Shape(uint64_t n_,uint64_t k_,uint64_t t_=1);
};
void environment();
void pack(const Shape&,const std::vector<float>&,std::vector<uint8_t>&,std::vector<float>&);
void activation(const Shape&,const std::vector<float>&,std::vector<int8_t>&,std::vector<float>&);
void validate(const Shape&,const std::vector<uint8_t>&,const std::vector<float>&,
              const std::vector<int8_t>&,const std::vector<float>&);
void scalar(const Shape&,const uint8_t*,const float*,const int8_t*,const float*,float*,int32_t*);
void tiled(const Shape&,const uint8_t*,const float*,const int8_t*,const float*,float*,int32_t*);
}
