#include "w4a8.hpp"
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <sys/resource.h>
namespace fs=std::filesystem;
using Clock=std::chrono::steady_clock;
template<class T> std::vector<T> load(const fs::path&p,size_t count){
    if(fs::file_size(p)!=count*sizeof(T))throw std::invalid_argument("exact file length: "+p.string());
    std::vector<T> x(count);std::ifstream f(p,std::ios::binary);f.read(reinterpret_cast<char*>(x.data()),x.size()*sizeof(T));if(!f)throw std::runtime_error("read");return x;
}
template<class T> void save(const fs::path&p,const std::vector<T>&v){
    if(fs::exists(p))throw std::runtime_error("output exists");std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));if(!f)throw std::runtime_error("write");
}
static uint64_t number(const char*s){size_t n=0;std::string v(s);if(v.empty()||v[0]=='-')throw std::invalid_argument("unsigned integer required");auto x=std::stoull(v,&n);if(n!=v.size())throw std::invalid_argument("integer trailing data");return x;}
static double elapsed(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}
int main(int argc,char**argv){try{
    a04::environment();if(argc<2)throw std::invalid_argument("mode required");std::string mode=argv[1];
    if(mode=="pack"||mode=="pack-bf16"){
        if(argc!=(mode=="pack"?6:7))throw std::invalid_argument("pack N K input [offset] new_output");
        a04::Shape a(number(argv[2]),number(argv[3]));std::vector<float>v;
        if(mode=="pack")v=load<float>(argv[4],size_t(a.n)*a.k);
        else {uint64_t off=number(argv[5]),count=uint64_t(a.n)*a.k;const auto bytes=fs::file_size(argv[4]);
            if(off>bytes||2*count>bytes-off)throw std::invalid_argument("source range");
            std::vector<uint16_t> raw(count);std::ifstream f(argv[4],std::ios::binary);f.seekg(off);f.read(reinterpret_cast<char*>(raw.data()),count*2);if(!f)throw std::runtime_error("BF16 read");
            v.resize(count);for(size_t i=0;i<count;++i){uint32_t bits=uint32_t(raw[i])<<16;std::memcpy(&v[i],&bits,4);}}
        std::vector<uint8_t>w;std::vector<float>s;const auto begin=Clock::now();a04::pack(a,v,w,s);const double pack_ms=elapsed(begin);
        fs::path out=argv[argc-1];if(!fs::create_directory(out))throw std::runtime_error("new output required");save(out/"w.bin",w);save(out/"sw.bin",s);
        std::cout<<"{\"mode\":\""<<mode<<"\",\"pack_ms\":"<<pack_ms<<",\"threads\":1}\n";return 0;
    }
    if((mode!="run"&&mode!="run-q")||argc!=(mode=="run"?9:10))throw std::invalid_argument("run N K T W Sw X [Sx] new_output");
    a04::Shape a(number(argv[2]),number(argv[3]),number(argv[4]));const auto load_begin=Clock::now();
    auto w=load<uint8_t>(argv[5],size_t(a.np)*a.kp/2);auto sw=load<float>(argv[6],size_t(a.np)*a.g);
    std::vector<int8_t>x;std::vector<float>sx;double quant_ms=0;
    if(mode=="run"){auto input=load<float>(argv[7],size_t(a.t)*a.k);const auto b=Clock::now();a04::activation(a,input,x,sx);quant_ms=elapsed(b);}
    else {x=load<int8_t>(argv[7],size_t(a.t)*a.kp);sx=load<float>(argv[8],a.t);}
    auto val=Clock::now();a04::validate(a,w,sw,x,sx);const double validate_ms=elapsed(val),load_ms=elapsed(load_begin);
    std::vector<float>ys(a.t*a.np),yo(a.t*a.np);std::vector<int32_t>si(a.t*a.np*a.g),oi(si.size());
    auto b=Clock::now();a04::scalar(a,w.data(),sw.data(),x.data(),sx.data(),ys.data(),si.data());double scalar_ms=elapsed(b);
    b=Clock::now();a04::tiled(a,w.data(),sw.data(),x.data(),sx.data(),yo.data(),oi.data());double tiled_ms=elapsed(b);
    if(si!=oi||std::memcmp(ys.data(),yo.data(),ys.size()*4))throw std::runtime_error("scalar/tiled mismatch");
    fs::path out=argv[argc-1];if(!fs::create_directory(out))throw std::runtime_error("new output required");
    save(out/"y.bin",yo);save(out/"sums.bin",oi);save(out/"xq.bin",x);save(out/"sx.bin",sx);
    rusage r{};getrusage(RUSAGE_SELF,&r);
    std::cout<<"{\"status\":\"PASS_CPP_SCALAR_TILED\",\"load_validate_quant_ms\":"<<load_ms<<",\"validate_ms\":"<<validate_ms
        <<",\"quant_ms\":"<<quant_ms<<",\"scalar_ms\":"<<scalar_ms<<",\"tiled_ms\":"<<tiled_ms
        <<",\"optimized_including_activation_quant_ms\":"<<tiled_ms+quant_ms<<",\"repack_ms\":0,\"threads\":1,\"peak_rss_kib\":"<<r.ru_maxrss<<"}\n";
    return 0;
}catch(const std::exception&e){std::cerr<<"A04_REJECT: "<<e.what()<<"\n";return 2;}}
