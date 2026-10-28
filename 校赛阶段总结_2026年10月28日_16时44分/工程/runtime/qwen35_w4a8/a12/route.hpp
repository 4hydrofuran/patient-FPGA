#pragma once
#include "ggml.h"
#include "sp_linear_v1.h"
#include "json.hpp"
#include <filesystem>
#include <map>
#include <string>
namespace a12 {
using json=nlohmann::json;
class Route {
    // Never dlclose a device library automatically. Explicit confirmed close only.
    void*library=nullptr;sp_linear_context*context=nullptr;
    decltype(&sp_linear_open_v1)open_fn=nullptr;
    decltype(&sp_linear_load_v1)load_fn=nullptr;
    decltype(&sp_linear_run_v1)run_fn=nullptr;
    decltype(&sp_linear_report_v1)report_fn=nullptr;
    decltype(&sp_linear_unload_v1)unload_fn=nullptr;
    decltype(&sp_linear_close_v1)close_fn=nullptr;
    std::map<uint64_t,bool> handles;
    std::map<const ggml_tensor*,std::vector<size_t>> pending;
    std::map<const ggml_tensor*,std::vector<size_t>> consuming;
    json policy,ledger=json::array();
    bool unsafe=false,closed=false,diagnostic=false;uint64_t trace_limit=4096;
public:
    bool enabled=false,real=false;std::string scope="none";
    void init();bool selects(int layer,const std::string&op)const;
    int load(uint32_t n,uint32_t k,const uint8_t*w,uint64_t wb,const float*sw,uint64_t sb,uint64_t*out);
    int run(uint64_t h,uint32_t t,const int8_t*x,uint64_t xb,const float*sx,uint64_t sb,
            float*y,uint64_t yb,uint64_t job,uint32_t timeout);
    json report()const;void close_checked();void set_trace(bool value);
    void returned(ggml_tensor*dst,int start,int t,int n,uint64_t job,const float*y,
                  int layer,const std::string&op,uint64_t epoch,uint64_t execution);
    void observe(ggml_tensor*consumer,bool after);void finish_execution();
    void park_if_unsafe()const;
};
}
