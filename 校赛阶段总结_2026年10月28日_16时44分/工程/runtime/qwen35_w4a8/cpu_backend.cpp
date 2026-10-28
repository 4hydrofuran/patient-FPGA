#include "sp_linear_v1.h"
#include "w4a8.hpp"
#include "json.hpp"
#include <chrono>
#include <cmath>
#include <cstring>
#include <fstream>
#include <map>
#include <mutex>
#include <memory>
#include <stdexcept>
#include <atomic>
#include "tiled_simd.hpp"
using json=nlohmann::json;using Clock=std::chrono::steady_clock;
// Literal checked in open against the frozen configuration; never a hardware ID.
struct Weight {a04::Shape s;std::vector<uint8_t>w;std::vector<float>sw;Weight(uint32_t n,uint32_t k):s(n,k){}};
struct sp_linear_context {
    std::mutex mutex;std::map<uint64_t,std::unique_ptr<Weight>> weights;
    uint64_t next=1,job=0,load_count=0,run_count=0,bytes=0;bool poisoned=false,scalar=false;int threads=1;
    std::vector<float> output;std::vector<int32_t> sums;json last;
    double compute_ms_total=0,service_ms_total=0;
    // Private CPU diagnostic option, not a SP_LINEAR ABI/protocol revision.
    bool retain_partial_sums=false,partial_sums_valid=false;
    uint32_t partial_t=0,partial_np=0,partial_g=0;
    uint64_t partial_job=0;
};
static bool needs_sum_storage(const sp_linear_context*c){return c->retain_partial_sums||c->scalar;}
static const char* contract="83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6";
static int32_t except_code(){try{throw;}catch(const std::bad_alloc&){return SP_DEVICE_ERROR;}catch(const std::invalid_argument&){return SP_NUMERIC_ERROR;}catch(...){return SP_DEVICE_ERROR;}}
static json report(sp_linear_context*c){
    json j={{"api_version",1},{"contract_sha256",contract},{"backend_id","A_CPU_W4A8_V1"},{"device_id",nullptr},
      {"xclbin_sha256",nullptr},{"kernel_build_id",nullptr},{"job_id",c->job},{"execution_kind","CPU_REFERENCE"},
      {"status",c->poisoned?"POISONED":"READY"},{"hardware_done_count",nullptr},{"weight_resident",!c->weights.empty()},
      {"quant_ms",nullptr},{"input_sync_ms",nullptr},{"kernel_ms",nullptr},{"output_sync_ms",nullptr},
      {"service_ms",nullptr},{"algorithm_weight_bytes",nullptr},{"measured_bus_bytes",nullptr},{"cycles",nullptr},
      {"cpu_quiescent",true},{"cpu_threads",c->threads},{"cpu_algorithm",c->scalar?"SCALAR":"TILED"},{"cpu_integer_isa",!c->scalar&&have_avx2()?"AVX2_RUNTIME_DISPATCH":"PORTABLE"},
      {"cpu_parallel_mode",c->scalar?"SCALAR_DIRECT":c->threads==1?"SERIAL_TILE_LOOP":"OPENMP_STATIC_TILE_LOOP"},
      {"weight_load_count",c->load_count},{"cpu_run_count",c->run_count},{"weight_count",c->weights.size()},
      {"owned_weight_bytes",c->bytes},{"workspace_capacity_bytes",c->output.capacity()*4+c->sums.capacity()*4},
      {"partial_sums_capacity_bytes",c->sums.capacity()*4},{"partial_sums_capture_enabled",c->retain_partial_sums},
      {"partial_sums_storage_mode",c->retain_partial_sums?"DIAGNOSTIC":needs_sum_storage(c)?"REFERENCE_REQUIRED_SCRATCH":"OMITTED"},
      {"cpu_compute_ms_process_total",c->compute_ms_total},{"cpu_service_ms_process_total",c->service_ms_total},
      {"legacy_timing_scope",{{"cpu_compute_ms","LAST_COMPLETED_RUN"},{"service_ms","LAST_COMPLETED_RUN_BEFORE_OUTPUT_COPY"},{"cpu_run_count","PROCESS_LIFETIME"}}}};
    if(!c->last.is_null())j.update(c->last);
    if(c->retain_partial_sums){
        json sample=nullptr;
        if(c->partial_sums_valid){sample=json::array();for(size_t i=0;i<std::min<size_t>(256,c->sums.size());++i)sample.push_back(c->sums[i]);}
        j["partial_sums_diagnostic"]={{"valid",c->partial_sums_valid},{"job_id",c->partial_job},
            {"layout","[T,Np,G]"},{"shape",{c->partial_t,c->partial_np,c->partial_g}},
            {"total_values",c->partial_sums_valid?c->sums.size():0},{"sample_offset",0},
            {"sample_limit",256},{"values",sample}};
    }
    return j;
}
extern "C" int32_t sp_linear_open_v1(const char* path,sp_linear_context**out){
    if(!out)return SP_BAD_ARGUMENT;*out=nullptr;if(!path)return SP_BAD_ARGUMENT;
    try{std::ifstream f(path);if(!f)return SP_BAD_ARGUMENT;json cfg;f>>cfg;
        if(cfg.value("api_version",0)!=1||cfg.value("contract_sha256",std::string())!=contract)return SP_CONTRACT_MISMATCH;
        if(cfg.value("execution_kind",std::string())!="CPU_REFERENCE"||cfg.value("fallback",std::string())!="disabled")return SP_UNSUPPORTED;
        auto alg=cfg.value("algorithm",std::string("TILED"));if(alg!="TILED"&&alg!="SCALAR")return SP_UNSUPPORTED;
        int threads=cfg.value("threads",1);if(threads<1||threads>16)return SP_BAD_ARGUMENT;
        if(cfg.contains("retain_partial_sums")&&!cfg["retain_partial_sums"].is_boolean())return SP_BAD_ARGUMENT;
        a04::environment();auto c=std::make_unique<sp_linear_context>();c->scalar=alg=="SCALAR";c->threads=c->scalar?1:threads;
        c->retain_partial_sums=cfg.value("retain_partial_sums",false);*out=c.release();return SP_OK;
    }catch(...){return except_code();}
}
extern "C" int32_t sp_linear_load_v1(sp_linear_context*c,uint32_t n,uint32_t k,const uint8_t*w,uint64_t wb,const float*sw,uint64_t sb,uint64_t*out)try{
    if(!c||!w||!sw||!out)return SP_BAD_ARGUMENT;*out=0;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;if(c->poisoned)return SP_POISONED;
    if(!n||n>4864||!k||k>4864)return SP_BAD_ARGUMENT;
    try{auto v=std::make_unique<Weight>(n,k);auto&a=v->s;
        if(wb<uint64_t(a.np)*a.kp/2||sb<uint64_t(a.np)*a.g*4)return SP_BUFFER_TOO_SMALL;
        if(wb!=uint64_t(a.np)*a.kp/2||sb!=uint64_t(a.np)*a.g*4)return SP_BAD_ARGUMENT;
        if(c->bytes+wb+sb>256ULL*1024*1024)return SP_BAD_ARGUMENT;
        v->w.assign(w,w+wb);v->sw.assign(sw,sw+sb/4);
        a04::validate(a,v->w,v->sw,std::vector<int8_t>(a.kp,0),std::vector<float>(1,1));
        c->output.reserve(std::max(c->output.capacity(),size_t(8*a.np)));
        if(needs_sum_storage(c))c->sums.reserve(std::max(c->sums.capacity(),size_t(8*a.np*a.g)));
        auto handle=c->next++;c->weights.emplace(handle,std::move(v));c->bytes+=wb+sb;++c->load_count;*out=handle;return SP_OK;
    }catch(...){return except_code();}
}catch(...){return except_code();}
extern "C" int32_t sp_linear_run_v1(sp_linear_context*c,uint64_t h,uint32_t t,const int8_t*x,uint64_t xb,const float*sx,uint64_t sb,float*y,uint64_t yb,uint64_t job,uint32_t timeout)try{
    if(!c||!x||!sx||!y||!h||!job||!timeout||!t||t>8)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;if(c->poisoned)return SP_POISONED;
    const auto found=c->weights.find(h);if(found==c->weights.end()||job<=c->job)return SP_BAD_ARGUMENT;
    try{auto service_begin=Clock::now();auto&v=*found->second;auto a=a04::Shape(v.s.n,v.s.k,t);
        if(xb<uint64_t(t)*a.kp||sb<uint64_t(t)*4||yb<uint64_t(t)*a.np*4)return SP_BUFFER_TOO_SMALL;
        if(xb!=uint64_t(t)*a.kp||sb!=uint64_t(t)*4)return SP_BAD_ARGUMENT;
        for(uint32_t row=0;row<t;++row){if(!std::isfinite(sx[row])||sx[row]<=0)return SP_NUMERIC_ERROR;
            for(int k=0;k<a.kp;++k)if(x[row*a.kp+k]==-128||(k>=a.k&&x[row*a.kp+k]!=0))return SP_NUMERIC_ERROR;}
        c->output.resize(t*a.np);if(needs_sum_storage(c))c->sums.resize(t*a.np*a.g);
        c->partial_sums_valid=false;c->job=job;auto begin=Clock::now();
        if(c->scalar)a04::scalar(a,v.w.data(),v.sw.data(),x,sx,c->output.data(),c->sums.data());
        else {
            std::atomic<bool> bad{false};
            // One tile implementation/ISA for every non-SCALAR thread count.
            // The serial loop deliberately stays outside an OpenMP region.
            auto run_tile=[&](int tile){
                try{float local_y[8*32];int32_t local_sum[8*32*38];a04::Shape sub(32,a.k,t);
                    // Portable tile still needs its original reference scratch;
                    // ISA selection itself remains inside the unchanged dispatcher.
                    cpu_tile(sub,v.w.data()+size_t(tile)*a.g*128*16,v.sw.data()+tile*a.g*32,x,sx,local_y,
                             c->retain_partial_sums||!have_avx2()?local_sum:nullptr);
                    for(uint32_t row=0;row<t;++row){
                        std::memcpy(c->output.data()+row*a.np+tile*32,local_y+row*32,32*4);
                        if(c->retain_partial_sums)std::memcpy(c->sums.data()+(row*a.np+tile*32)*a.g,local_sum+row*32*a.g,32*a.g*4);}
                }catch(...){bad=true;}
            };
            if(c->threads==1){
                for(int tile=0;tile<a.np/32;++tile)run_tile(tile);
            }else{
                #pragma omp parallel for num_threads(c->threads) schedule(static)
                for(int tile=0;tile<a.np/32;++tile)run_tile(tile);
            }
            if(bad)throw std::invalid_argument("parallel numerical failure");
        }
        double elapsed=std::chrono::duration<double,std::milli>(Clock::now()-begin).count();++c->run_count;
        double service=std::chrono::duration<double,std::milli>(Clock::now()-service_begin).count();
        c->compute_ms_total+=elapsed;c->service_ms_total+=service;
        c->last={{"service_ms",service},{"cpu_compute_ms",elapsed},{"algorithm_weight_bytes",v.w.size()+v.sw.size()*4},{"last_status_code",SP_OK}};
        if(service>timeout){c->poisoned=true;c->last["last_status_code"]=SP_TIMEOUT;return SP_TIMEOUT;}
        if(c->retain_partial_sums){c->partial_sums_valid=true;c->partial_t=t;c->partial_np=a.np;c->partial_g=a.g;c->partial_job=job;}
        std::memcpy(y,c->output.data(),size_t(t)*a.np*4);return SP_OK;
    }catch(...){c->last={{"last_status_code",SP_NUMERIC_ERROR}};return except_code();}
}catch(...){return except_code();}
extern "C" int32_t sp_linear_report_v1(sp_linear_context*c,char*dst,uint64_t cap,uint64_t*needed)try{
    if(!c||!needed||(!dst&&cap))return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    try{auto s=report(c).dump();*needed=s.size()+1;if(!dst)return SP_OK;if(cap<*needed)return SP_BUFFER_TOO_SMALL;std::memcpy(dst,s.c_str(),*needed);return SP_OK;}catch(...){return except_code();}
}catch(...){return except_code();}
extern "C" int32_t sp_linear_unload_v1(sp_linear_context*c,uint64_t h)try{
    if(!c||!h)return SP_BAD_ARGUMENT;std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    auto p=c->weights.find(h);if(p==c->weights.end())return SP_BAD_ARGUMENT;
    c->bytes-=p->second->w.size()+p->second->sw.size()*4;c->weights.erase(p);return SP_OK;
}catch(...){return except_code();}
extern "C" int32_t sp_linear_close_v1(sp_linear_context*c)try{
    if(!c)return SP_BAD_ARGUMENT;std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    // All CPU work is synchronous; even a reported timeout has verified quiescence.
    lock.unlock();delete c;return SP_OK;
}catch(...){return except_code();}
