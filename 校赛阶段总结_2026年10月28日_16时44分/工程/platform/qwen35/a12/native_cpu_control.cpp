// PC-only permit adapter. Every mathematical operation is forwarded unchanged
// to the pinned existing CPU library; no XRT, device or FPGA implementation.
#if !defined(__x86_64__) || !defined(SP_A12_PC_TEST)
#error "native_cpu_control is an x86_64 PC-test-only adapter"
#endif
#include "sp_linear_v1.h"
#include "prefix_cache.hpp"
#include <cmath>
#include <cstring>
#include <dlfcn.h>
#include <map>
#include <memory>
#include <mutex>
#include <sys/socket.h>
#include <unistd.h>
using json=nlohmann::json;
namespace {
constexpr const char* CONTRACT="83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6";
void need(bool value,const char* text){if(!value)throw std::runtime_error(text);}
struct API {
    decltype(&sp_linear_open_v1)open;
    decltype(&sp_linear_load_v1)load;
    decltype(&sp_linear_run_v1)run;
    decltype(&sp_linear_report_v1)report;
    decltype(&sp_linear_unload_v1)unload;
    decltype(&sp_linear_close_v1)close;
};
struct Control {
    int fd=-1;uint64_t router=0,backend=0;
    void permit(const char* phase,uint64_t job){
        if(fd<0){
            const char* value=std::getenv("SP_A12_CONTROL_FD");need(value,"PC parent control FD absent");
            size_t used=0;fd=std::stoi(value,&used);need(used==std::strlen(value)&&fd>=3,"PC control FD invalid");
        }
        struct ucred peer{};socklen_t size=sizeof(peer);
        need(!getsockopt(fd,SOL_SOCKET,SO_PEERCRED,&peer,&size)&&peer.pid==getppid(),"PC permit peer differs");
        auto& sequence=std::strncmp(phase,"router_",7)==0?router:backend;
        std::string request=json{{"pid",getpid()},{"sequence",++sequence},{"phase",phase},{"job",job}}.dump()+"\n";
        size_t sent=0;
        while(sent<request.size()){
            auto n=send(fd,request.data()+sent,request.size()-sent,MSG_NOSIGNAL);
            need(n>0,"PC permit send failed");sent+=size_t(n);
        }
        std::string reply;char c=0;
        while(reply.size()<4096){need(recv(fd,&c,1,0)==1,"PC permit manager disconnected");if(c=='\n')break;reply+=c;}
        need(c=='\n',"PC permit reply too large");auto r=json::parse(reply);
        need(r.at("sequence")==sequence&&r.at("allow").is_boolean()&&r.at("allow")==true,"PC permit denied");
    }
};
}
struct sp_linear_context {
    std::mutex mutex;void*library=nullptr;void*core=nullptr;API api{};Control control;
    uint64_t loads=0,attempted=0,started=0,verified=0,failed=0,last_job=0;
    bool poisoned=false,closing=false,last_consumable=false;
    std::map<uint64_t,uint32_t> padded_n;
    json core_report(){
        uint64_t bytes=0;auto*c=reinterpret_cast<sp_linear_context*>(core);
        need(api.report(c,nullptr,0,&bytes)==SP_OK&&bytes>1&&bytes<=65536,"PC CPU report size");
        std::vector<char> data(bytes);need(api.report(c,data.data(),bytes,&bytes)==SP_OK,"PC CPU report read");
        return json::parse(data.data());
    }
    json report(){
        auto r=core_report();
        need(r.at("execution_kind")=="CPU_REFERENCE"&&r.at("hardware_done_count").is_null()&&
             r.at("kernel_build_id").is_null(),"PC CPU identity changed");
        r["pc_adapter"]="A12_NATIVE_CPU_CONTROL_V1";r["pc_domain"]="PC_NATIVE_MATH_NOT_FPGA";
        r["pc_attempted_calls"]=attempted;r["pc_started_calls"]=started;r["pc_verified_completions"]=verified;
        r["pc_failed_calls"]=failed;r["pc_output_consumable"]=last_consumable;
        r["pc_counter_scope"]="ADAPTER_ATTEMPT/FORWARDED_CPU_API/VERIFIED_CPU_COMPLETION_NOT_DEVICE";
        r["pc_last_job"]=last_job;r["pc_permission_lanes"]={{"router",control.router},{"backend",control.backend}};
        r["pc_loads"]=loads;r["pc_poisoned"]=poisoned;r["pc_closing"]=closing;
        return r;
    }
    void begin_close(){if(!closing){control.permit("router_close",0);closing=true;}}
};
#define EXPORT extern "C" __attribute__((visibility("default")))
EXPORT int32_t sp_linear_open_v1(const char* path,sp_linear_context** out)try{
    if(!out||!path)return SP_BAD_ARGUMENT;
    *out=nullptr;
    if(std::filesystem::file_size(path)>65536)return SP_BAD_ARGUMENT;
    std::ifstream f(path);json cfg;f>>cfg;
    need(cfg.at("schema")=="A12_NATIVE_CPU_CONTROL_V1"&&cfg.at("execution_kind")=="CPU_REFERENCE"&&
         cfg.at("contract_sha256")==CONTRACT&&cfg.at("allow_device_access")==false,"PC adapter config rejected");
    std::string library=cfg.at("cpu_library"),config=cfg.at("cpu_config");
    need(tt10::file_digest(library)==cfg.at("cpu_library_sha256")&&
         tt10::file_digest(config)==cfg.at("cpu_config_sha256"),"PC pinned CPU artifact changed");
    std::ifstream cf(config);json base;cf>>base;
    need(base.at("execution_kind")=="CPU_REFERENCE"&&base.at("fallback")=="disabled","PC CPU config rejected");
    auto c=std::make_unique<sp_linear_context>();
    c->control.permit("router_open",0);c->control.permit("device_open",0);
    c->library=dlopen(library.c_str(),RTLD_NOW|RTLD_LOCAL);need(c->library,"PC CPU dlopen failed");
#define LOAD(name) c->api.name=reinterpret_cast<decltype(c->api.name)>(dlsym(c->library,"sp_linear_" #name "_v1"));need(c->api.name,"PC CPU symbol missing")
    LOAD(open);LOAD(load);LOAD(run);LOAD(report);LOAD(unload);LOAD(close);
#undef LOAD
    sp_linear_context* core=nullptr;need(c->api.open(config.c_str(),&core)==SP_OK&&core,"PC CPU open failed");c->core=core;
    auto r=c->report();need(r.at("cpu_run_count")==0&&r.at("weight_count")==0,"PC CPU not fresh");
    *out=c.release();return SP_OK;
}catch(...){return SP_DEVICE_ERROR;}

EXPORT int32_t sp_linear_load_v1(sp_linear_context*c,uint32_t n,uint32_t k,const uint8_t*w,
    uint64_t wb,const float*scales,uint64_t sb,uint64_t*out)try{
    if(!c||!out)return SP_BAD_ARGUMENT;
    *out=0;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    if(c->poisoned||c->closing)return SP_POISONED;
    if(c->loads>=72)return SP_BAD_ARGUMENT;
    c->control.permit("weight_load",c->loads+1);
    int32_t rc=c->api.load(reinterpret_cast<sp_linear_context*>(c->core),n,k,w,wb,scales,sb,out);
    if(rc!=SP_OK){c->poisoned=true;return rc;}
    ++c->loads;c->padded_n.emplace(*out,(n+31)/32*32);return SP_OK;
}catch(...){if(c)c->poisoned=true;return SP_DEVICE_ERROR;}

EXPORT int32_t sp_linear_run_v1(sp_linear_context*c,uint64_t h,uint32_t t,const int8_t*x,uint64_t xb,
    const float*sx,uint64_t sb,float*y,uint64_t yb,uint64_t job,uint32_t timeout)try{
    if(!c)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    c->last_consumable=false;
    if(!y||!t||t>8||!timeout||!job)return SP_BAD_ARGUMENT;
    if(c->poisoned||c->closing)return SP_POISONED;
    if(!c->padded_n.count(h)||job<=c->last_job||c->attempted>=5000)return SP_BAD_ARGUMENT;
    ++c->attempted;
    c->control.permit("submit",job);++c->started;
    int32_t rc=c->api.run(reinterpret_cast<sp_linear_context*>(c->core),h,t,x,xb,sx,sb,y,yb,job,timeout);
    if(rc!=SP_OK){++c->failed;c->poisoned=true;return rc;}
    auto r=c->core_report();
    need(r.at("execution_kind")=="CPU_REFERENCE"&&r.at("status")=="READY"&&r.at("cpu_quiescent")==true&&
         r.at("cpu_run_count")==c->verified+1&&r.at("job_id")==job&&r.at("last_status_code")==SP_OK,
         "PC actual CPU completion differs");
    const size_t values=size_t(t)*c->padded_n.at(h);need(yb>=values*4,"PC output length differs");
    for(size_t i=0;i<values;++i)need(std::isfinite(y[i]),"PC nonfinite output");
    ++c->verified;c->last_job=job;c->last_consumable=true;return SP_OK;
}catch(...){if(c){c->poisoned=true;c->last_consumable=false;++c->failed;}return SP_DEVICE_ERROR;}

EXPORT int32_t sp_linear_report_v1(sp_linear_context*c,char*dst,uint64_t capacity,uint64_t*needed)try{
    if(!c||!needed||(!dst&&capacity))return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    auto text=c->report().dump();*needed=text.size()+1;if(!dst)return SP_OK;
    if(capacity<*needed)return SP_BUFFER_TOO_SMALL;
    std::memcpy(dst,text.c_str(),*needed);return SP_OK;
}catch(...){return SP_DEVICE_ERROR;}

EXPORT int32_t sp_linear_unload_v1(sp_linear_context*c,uint64_t h)try{
    if(!c)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    if(c->poisoned)return SP_POISONED;
    c->begin_close();
    auto rc=c->api.unload(reinterpret_cast<sp_linear_context*>(c->core),h);if(rc==SP_OK)c->padded_n.erase(h);return rc;
}catch(...){if(c)c->poisoned=true;return SP_DEVICE_ERROR;}

EXPORT int32_t sp_linear_close_v1(sp_linear_context*c)try{
    if(!c)return SP_BAD_ARGUMENT;
    std::unique_lock<std::mutex> lock(c->mutex,std::try_to_lock);if(!lock)return SP_BUSY;
    if(c->poisoned)return SP_POISONED;
    c->begin_close();
    if(!c->padded_n.empty())return SP_BUSY;
    int32_t rc=c->api.close(reinterpret_cast<sp_linear_context*>(c->core));if(rc!=SP_OK)return rc;
    void* lib=c->library;lock.unlock();delete c;dlclose(lib);return SP_OK;
}catch(...){if(c)c->poisoned=true;return SP_DEVICE_ERROR;}
