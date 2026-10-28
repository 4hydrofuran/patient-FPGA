// Independent A04 scalar vs new AVX2 integer lane kernel, real A04 activations.
#include "tiled_simd.hpp"
#include <cstring>
#include <fstream>
#include <iostream>
#include <vector>
template<class T>std::vector<T>read(const std::string&p){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f)throw std::runtime_error(p);auto size=f.tellg();if(size<0||size%sizeof(T))throw std::runtime_error("file size");std::vector<T>v(size/sizeof(T));f.seekg(0);f.read((char*)v.data(),size);if(!f)throw std::runtime_error("read");return v;}
int main(){try{a04::environment();std::string root="/mnt/c/Patientqwen/";int tests=0;
 for(auto model:{"H0_F16","S0_Q4"})for(auto phase:{"prefill","decode"})for(int l:{0,3,4,23})for(auto op:{"gate","up","down"}){
   char id[32];snprintf(id,sizeof(id),"l%02d_%s",l,op);int n=strcmp(op,"down")==0?1024:3584,k=strcmp(op,"down")==0?3584:1024,t=strcmp(phase,"decode")==0?1:8;a04::Shape s(n,k,t);
   auto w=read<uint8_t>(root+"models/sidecar_A/qwen35-v1/"+id+".w.bin");auto sw=read<float>(root+"models/sidecar_A/qwen35-v1/"+id+".sw.bin");
   std::string base=root+"eval/qwen35/a04/real-v1/"+model+"_"+phase+"_"+id+"/cpp/";auto x=read<int8_t>(base+"xq.bin");auto sx=read<float>(base+"sx.bin");auto y=read<float>(base+"y.bin");auto sums=read<int32_t>(base+"sums.bin");
   for(int tile=0;tile<n/32;++tile){float yy[8*32];int32_t ss[8*32*38];a04::Shape shape(32,k,t);cpu_tile(shape,w.data()+tile*s.g*128*16,sw.data()+tile*s.g*32,x.data(),sx.data(),yy,ss);
     for(int row=0;row<t;++row)if(memcmp(yy+row*32,y.data()+row*n+tile*32,128)||memcmp(ss+row*32*s.g,sums.data()+(row*n+tile*32)*s.g,32*s.g*4))throw std::runtime_error(std::string(id)+" integer/FP32 mismatch");}
   ++tests;
 }
 std::cout<<"{\"real_projection_cases\":"<<tests<<",\"integer_bit_exact\":true,\"fp32_bit_exact\":true,\"avx2\":"<<(have_avx2()?"true":"false")<<"}\n";return 0;
}catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}}
