#include "route.hpp"
#include "supervisor_gate.hpp"
#include <dlfcn.h>
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
extern "C" unsigned char* SHA256(const unsigned char*,size_t,unsigned char*);
#include <iomanip>
#include <sstream>
#include <thread>
namespace a12 {
static void need(bool value,const char*message){if(!value)throw std::runtime_error(message);}
static std::string hash_bytes(const void*ptr,size_t bytes){
    unsigned char out[32];SHA256(static_cast<const unsigned char*>(ptr),bytes,out);
    std::ostringstream s;for(auto c:out)s<<std::hex<<std::setw(2)<<std::setfill('0')<<unsigned(c);return s.str();
}
static std::string file_hash(const std::string&name){
    std::ifstream f(name,std::ios::binary);need(bool(f),"A12 missing pinned artifact");
    std::vector<char>v((std::istreambuf_iterator<char>(f)),{});return hash_bytes(v.data(),v.size());
}
void Route::init(){
    const char*path=std::getenv("SP_A12_CONFIG");if(!path)return;
    std::ifstream f(path);f>>policy;
    need(policy.at("contract_sha256")=="83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6"&&
         policy.at("fallback")=="disabled"&&policy.at("fpga_required")==true,"A12 identity/fallback policy");
    scope=policy.at("scope");need(scope=="all"||scope=="l0"||scope=="l0_gate"||scope=="l0_up"||scope=="l0_down","A12 scope");
    real=policy.at("execution_kind")=="FPGA_REAL";
    need(real||policy.at("execution_kind")=="PC_MATH_DOUBLE","A12 execution kind");
#ifndef SP_A12_PC_TEST
    need(real,"PC math double unavailable in production ARM worker");
#else
    need(!real,"PC test worker refuses FPGA_REAL");
#endif
    if(real)permit("router_open",0);
    const std::string lib=policy.at("library"),config=policy.at("backend_config");
    need(file_hash(lib)==policy.at("library_sha256")&&file_hash(config)==policy.at("backend_config_sha256"),"A12 artifact hash mismatch");
    library=dlopen(lib.c_str(),RTLD_NOW|RTLD_LOCAL);need(library,"A12 dlopen failed");
#define A12_LOAD(name) name##_fn=reinterpret_cast<decltype(name##_fn)>(dlsym(library,"sp_linear_" #name "_v1"));need(name##_fn,"A12 missing ABI symbol")
    A12_LOAD(open);A12_LOAD(load);A12_LOAD(run);A12_LOAD(report);A12_LOAD(unload);A12_LOAD(close);
    compact_completion=policy.value("a12_compact_completion",false);
    if(compact_completion){completion_fn=reinterpret_cast<decltype(completion_fn)>(dlsym(library,"sp_a12_completion_report_v1"));need(completion_fn,"A12 private completion reader absent");}
#undef A12_LOAD
    need(open_fn(config.c_str(),&context)==SP_OK&&context,"A12 backend open failed");
    enabled=true;auto r=report();
    const std::string expected=real?"FPGA_REAL":"CPU_REFERENCE";
    need(r.at("execution_kind")==expected&&r.at("contract_sha256")==policy.at("contract_sha256"),"A12 backend identity differs");
    trace_limit=policy.value("trace_limit",uint64_t(4096));need(trace_limit>0&&trace_limit<=65536,"A12 trace bound");
}
bool Route::selects(int layer,const std::string&op)const{return enabled&&(scope=="all"||(layer==0&&(scope=="l0"||scope=="l0_"+op)));}
int Route::load(uint32_t n,uint32_t k,const uint8_t*w,uint64_t wb,const float*sw,uint64_t sb,uint64_t*out){
    int rc=load_fn(context,n,k,w,wb,sw,sb,out);if(rc==SP_OK)handles.emplace(*out,true);return rc;
}
int Route::run(uint64_t h,uint32_t t,const int8_t*x,uint64_t xb,const float*sx,uint64_t sb,float*y,uint64_t yb,uint64_t job,uint32_t timeout){
    need(!unsafe&&!closed,"A12 isolated context refuses new work");
    unsafe=real; // A thrown call/report cannot prove no DMA is in flight.
    try {
    auto call_start=std::chrono::steady_clock::now();
    int rc=run_fn(context,h,t,x,xb,sx,sb,y,yb,job,timeout);
    auto call_end=std::chrono::steady_clock::now();
    if(rc!=SP_OK){
        auto r=report();unsafe=real&&(r.value("status",std::string())!="READY"||rc==SP_TIMEOUT||rc==SP_POISONED||rc==SP_BUSY);
        park_if_unsafe();return rc;
    }
    auto report_start=std::chrono::steady_clock::now();
    auto r=compact_completion?completion():report();
    auto report_end=std::chrono::steady_clock::now();
    if(profile_on&&real){auto&m=metrics[profile_phase];++m.calls;
        m.run_ms+=std::chrono::duration<double,std::milli>(call_end-call_start).count();
        m.report_ms+=std::chrono::duration<double,std::milli>(report_end-report_start).count();
        for(auto k:{"a12_permission_wait_ms","service_ms","a11_input_copy_and_meta_seed_ms","a11_input_bo_sync_ms","a11_set_args_ms","a11_submit_to_confirmed_completion_ms","a11_meta_sync_ms","a11_meta_validate_ms","a11_output_bo_sync_and_map_ms","a11_output_validate_ms"})m.backend[k]+=r.at(k).get<double>();
    }
    if(real&&(!r.value("output_consumable",false)||r.at("job_id")!=job||r.at("kernel_build_id")!=0xB3030002u)){
        unsafe=true;park_if_unsafe();throw std::runtime_error("A12 completion identity differs");
    }
    unsafe=false;return rc;
    }catch(...){park_if_unsafe();throw;}
}
json Route::report()const{
    if(!enabled)return {{"execution_kind","CPU_REFERENCE"},{"scope","none"},{"trace",ledger}};
    uint64_t size=0;need(report_fn(context,nullptr,0,&size)==SP_OK&&size<=1048576,"A12 report query");
    std::vector<char>data(size);need(report_fn(context,data.data(),size,&size)==SP_OK,"A12 report read");
    auto r=json::parse(data.data());r["a12_route_scope"]=scope;r["a12_domain"]=real?"BOARD":"PC_MATH_DOUBLE";
    r["a12_hardware_global_count"]=nullptr;r["a12_trace"]=ledger;return r;
}
json Route::completion()const{
    uint64_t size=0;need(completion_fn(context,nullptr,0,&size)==SP_OK&&size<=65536,"A12 compact report query");
    std::vector<char>data(size);need(completion_fn(context,data.data(),size,&size)==SP_OK,"A12 compact report read");
    return json::parse(data.data());
}
json Route::performance()const{
    json r={{"enabled",profile_on},{"compact_completion",compact_completion},{"phases",json::object()}};
    for(int p=0;p<2;++p){const auto&m=metrics[p];r["phases"][p?"decode":"prefill"]={{"calls",m.calls},{"backend_call_wall_ms",m.run_ms},{"completion_report_wall_ms",m.report_ms},{"backend",m.backend}};}
    r["timing_scope"]="HOST_WALL_NOT_DEVICE_CYCLES; backend call includes permission; report is a sibling; backend fields are nested";return r;
}
void Route::close_checked(){
    if(!enabled||closed)return;park_if_unsafe();
    if(real)permit("router_close",0);
    for(auto&h:handles)if(h.second){int rc=unload_fn(context,h.first);if(rc!=SP_OK){unsafe=real;park_if_unsafe();throw std::runtime_error("A12 unload failed");}h.second=false;}
    if(close_fn(context)!=SP_OK){unsafe=real;park_if_unsafe();throw std::runtime_error("A12 close failed");}
    context=nullptr;closed=true;
}
void Route::set_trace(bool value){need(pending.empty()&&consuming.empty(),"A12 unverified consumer from previous request");diagnostic=value;ledger=json::array();}
void Route::returned(ggml_tensor*dst,int start,int t,int n,uint64_t job,const float*y,int layer,const std::string&op,uint64_t epoch,uint64_t execution){
    if(!diagnostic)return;need(ledger.size()<trace_limit,"A12 trace capacity exceeded");
    ledger.push_back({{"job_id",job},{"layer",layer},{"op",op},{"T",t},{"N",n},{"row_start",start},
       {"epoch",epoch},{"execution",execution},{"output_sha256",hash_bytes(y,size_t(t)*n*4)},
       {"execution_kind",real?"FPGA_REAL":"PC_MATH_DOUBLE"},{"consumer_verified",false}});
    auto completion=report();completion.erase("a12_trace");
    ledger.back()["backend_completion"]=completion;
    pending[dst].push_back(ledger.size()-1);
}
void Route::observe(ggml_tensor*consumer,bool after){
    if(!diagnostic)return;
    if(after){
        auto it=consuming.find(consumer);if(it==consuming.end())return;
        for(auto index:it->second){auto&r=ledger[index];r["consumer_verified"]=true;
            r["consumer_name"]=consumer->name;r["consumer_op"]=ggml_op_name(consumer->op);
            r["consumer_observation"]="INPUT_HASH_BEFORE_AND_EXECUTION_CONFIRMED_AFTER_ALLOWING_IN_PLACE";}
        consuming.erase(it);return;
    }
    for(auto*src:consumer->src){auto it=pending.find(src);if(it==pending.end())continue;
        for(auto index:it->second){auto&r=ledger[index];int t=r["T"],n=r["N"],start=r["row_start"];
            std::vector<float>actual(size_t(t)*n);
            for(int row=0;row<t;++row)std::memcpy(actual.data()+row*n,static_cast<const char*>(src->data)+(start+row)*src->nb[1],n*4);
            need(hash_bytes(actual.data(),actual.size()*4)==r["output_sha256"],"A12 graph consumer saw different or stale Y");
            consuming[consumer].push_back(index);
        }
        pending.erase(it);
    }
}
void Route::finish_execution(){need(!diagnostic||(pending.empty()&&consuming.empty()),"A12 output had no observed graph consumer");}
void Route::park_if_unsafe()const{
    if(!unsafe)return;
    std::cerr<<"A12_QUARANTINED_NO_CLOSE_NO_EXIT\n"<<std::flush;
    for(;;)std::this_thread::sleep_for(std::chrono::seconds(1));
}
}
