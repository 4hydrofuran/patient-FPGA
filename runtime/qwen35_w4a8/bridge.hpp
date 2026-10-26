#pragma once
#include "ggml.h"
#include "json.hpp"
#include "sp_linear_v1.h"
#include "request_profile.hpp"
#include <array>
#include <filesystem>
#include <map>
#include <vector>
namespace s1 {
using json=nlohmann::json;
struct Bridge;
struct Entry {Bridge*owner=nullptr;std::string id,name,op;int layer=0,n=0,k=0;uint64_t handle=0,calls=0,tokens=0;};
struct Cache {bool valid=false;uint64_t epoch=0,execution=0;int layer=-1,k=0,t=0,mask=0;const void*tensor=nullptr;std::array<size_t,4>strides{};std::vector<int8_t>q;std::vector<float>sx;};
struct Bridge {
    PerRequestStats request_stats;
    sp_linear_context*cpu=nullptr;std::map<std::string,Entry> entries;
    std::string scope,error;uint64_t epoch=0,execution=0,job=0,quantizations=0,cache_hits=0;
    double quant_ms=0,copy_ms=0;Cache cache;bool diagnostic_all_layers=false;
    std::vector<float>scratch,y;std::vector<int8_t>qx;std::vector<float>sx;
    std::filesystem::path diagnostic;json dumps=json::array();
    std::map<std::string,json> gguf_ranges;
    std::array<uint64_t,9> physical_t_calls{};
    Bridge(const std::filesystem::path&root,std::string scope_,std::string algorithm="TILED",int threads=4);
    ~Bridge();void reset();void begin_execution();json report(bool diagnostic=true)const;
    static ggml_tensor* graph(ggml_context*,ggml_tensor*,ggml_tensor*,void*);
    static void compute(ggml_tensor*,int,int,void*);
    void protect_unused_weight(ggml_tensor*,Entry&);
    void set_diagnostic(const std::string&);
};
}
