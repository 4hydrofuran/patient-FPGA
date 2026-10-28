// Actual derived backend ABI, XRT CONTROL doubles and the legacy router permit DSO.
// No model inference, matrix math, bitstream, FPGA, recovery or release authority.
#include "sp_linear_v1.h"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <dlfcn.h>
#include <iostream>
#include <thread>
#include <vector>
using json=nlohmann::json;
extern "C" int32_t sp_a12_completion_report_v1(sp_linear_context*,char*,uint64_t,uint64_t*);
extern "C" int32_t sp_a12_plm_request_v1(sp_linear_context*,const char*);
extern "C" int32_t sp_a12_plm_request_end_v1(sp_linear_context*);
extern "C" int32_t sp_a12_plm_test_fault_v1(sp_linear_context*,const char*,uint64_t);
extern "C" int32_t sp_a12_plm_test_inventory_v1(char*,uint64_t);
static void need(bool ok){if(!ok)throw std::runtime_error("PLM control probe refused");}
static json inventory(){char b[1024];need(!sp_a12_plm_test_inventory_v1(b,sizeof b));return json::parse(b);}
static json report(sp_linear_context*c,bool full){
    auto fn=full?sp_linear_report_v1:sp_a12_completion_report_v1;uint64_t n=0;need(!fn(c,nullptr,0,&n)&&n&&n<=32768);
    std::vector<char>b(n);need(!fn(c,b.data(),n,&n));return json::parse(b.data());
}
static void emit(json j){j["domain"]="PC_XRT_CONTROL_ONLY_NOT_MODEL";j["BOARD"]="NOT_TESTED";std::cout<<j.dump()<<std::endl;}
int main(int argc,char**argv)try{
    if(argc!=4)return 2;
    void*lib=dlopen(argv[2],RTLD_NOW|RTLD_LOCAL);need(lib);auto router=reinterpret_cast<int(*)(bool)>(dlsym(lib,"plm_legacy_router_v1"));need(router);
    need(!router(false));if(std::string(argv[3])=="legacy_replay")need(!router(false));
    sp_linear_context*c=nullptr;need(!sp_linear_open_v1(argv[1],&c)&&c);
    std::vector<uint64_t>handles;std::vector<uint8_t>w(2048,0);std::vector<float>sw(32,1);
    for(int i=0;i<72;++i){uint64_t h=0;need(!sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&h));handles.push_back(h);}
    emit({{"event","ready"},{"report",report(c,true)},{"inventory",inventory()}});
    uint64_t job=0;char line[16384];
    while(std::cin.getline(line,sizeof line)){
        auto q=json::parse(line);auto op=q.at("op").get<std::string>();
        if(op=="close"){
            need(!router(true));for(auto h:handles)need(!sp_linear_unload_v1(c,h));need(!sp_linear_close_v1(c));
            emit({{"event","closed"},{"inventory",inventory()}});
            need(bool(std::cin.getline(line,sizeof line))&&json::parse(line).at("op")=="exit");return 0;
        }
        need(op=="run"&&q.at("plan").is_array()&&q.at("plan").size()<=21);
        auto digest=q.at("request_sha256").get<std::string>();need(!sp_a12_plm_request_v1(c,digest.c_str()));
        const auto fault=q.value("fault",std::string());
        if(fault=="premature_unload"){
            int rc=sp_linear_unload_v1(c,handles.front());
            emit({{"event","failed"},{"request_sha256",digest},{"rc",rc},{"caller_y_unchanged",true},
                {"report",report(c,false)},{"inventory",inventory()}});return rc==SP_POISONED?2:3;
        }
        if(fault=="revoke_claim"||fault=="nan_y"||fault=="start"||fault=="timeout"||fault=="pause_claim")need(!sp_a12_plm_test_fault_v1(c,fault.c_str(),job+5));
        const auto base=job;
        for(auto row:q.at("plan")){
            auto t=row.get<uint32_t>();need(t>=1&&t<=8);
            for(auto h:handles){
                const auto call_t=(fault=="cached_T"&&h==handles[1]&&t==8)?1u:t;
                std::vector<int8_t>x(call_t*128,0);std::vector<float>sx(call_t,1),y(call_t*32,-999);
                auto rc=sp_linear_run_v1(c,h,call_t,x.data(),x.size(),sx.data(),sx.size()*4,y.data(),y.size()*4,++job,fault=="timeout"?8:1000);
                if(rc){emit({{"event","failed"},{"request_sha256",digest},{"job",job},{"rc",rc},
                    {"caller_y_unchanged",std::all_of(y.begin(),y.end(),[](float v){return v==-999;})},
                    {"report",report(c,false)},{"inventory",inventory()}});return 2;}
                need(std::all_of(y.begin(),y.end(),[](float v){return v==0;}));
                if(fault=="slow")std::this_thread::sleep_for(std::chrono::milliseconds(5));
            }
        }
        need(!sp_a12_plm_request_end_v1(c));
        if(fault=="reuse_generation"){
            int rc=sp_a12_plm_request_v1(c,digest.c_str());emit({{"event","failed"},{"rc",rc},{"report",report(c,false)},
                {"inventory",inventory()},{"caller_y_unchanged",nullptr},{"request_sha256",digest}});return rc?2:3;
        }
        emit({{"event","result"},{"request_id",q.at("id")},
            {"request_sha256",digest},{"calls",job-base},{"last_job",job},{"report",report(c,false)},{"inventory",inventory()}});
    }
    throw std::runtime_error("PC probe EOF; no implicit close/replay");
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}
