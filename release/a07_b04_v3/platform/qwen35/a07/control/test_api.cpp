// Test the real production six-function implementation against CONTROL-ONLY doubles.
#include "sp_linear_v1.h"
#include "control_xrt.hpp"
#include "json.hpp"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <thread>
using json=nlohmann::json;
static unsigned checks=0;
static void check(bool ok,const char*why){++checks;if(!ok)throw std::runtime_error(why);}
static json report(sp_linear_context*c){
    uint64_t n=0;check(sp_linear_report_v1(c,nullptr,0,&n)==0&&n>1,"report size query");
    std::vector<char>b(n,'!');uint64_t size=0;
    check(sp_linear_report_v1(c,b.data(),n-1,&size)==SP_BUFFER_TOO_SMALL&&size==n,"short report");
    check(std::all_of(b.begin(),b.end(),[](char v){return v=='!';}),"short report writes no partial JSON");
    check(sp_linear_report_v1(c,b.data(),n,&size)==0&&b.back()==0,"NUL included");
    auto j=json::parse(b.data());check(j["execution_kind"].is_null()&&!j["public_metrics_eligible"].get<bool>(),"mock cannot masquerade as FPGA or CPU math");
    for(auto key:{"hardware_done_count","cycles","measured_bus_bytes","kernel_ms","service_ms"})check(j[key].is_null(),"no synthetic hardware metrics");
    return j;
}
static void write_json(const char*path,const json&j){std::ofstream(path)<<j.dump(2);}
int main(int argc,char**argv)try{
    if(argc!=3)return 2;
    const std::string mode=argv[1];const char*cfg=argv[2];
    check(sp_linear_open_v1(nullptr,nullptr)==SP_BAD_ARGUMENT,"null open args");
    sp_linear_context*c=nullptr;
    if(mode=="gates"){
        json base;std::ifstream(cfg)>>base;json profile;std::ifstream("profile.json")>>profile;
        auto denied=base;denied["allow_device_access"]=false;write_json("denied.json",denied);
        check(sp_linear_open_v1("denied.json",&c)==SP_UNSUPPORTED&&!c,"disabled before discovery");
        denied=base;denied["fallback"]="cpu";write_json("denied.json",denied);
        check(sp_linear_open_v1("denied.json",&c)==SP_CONTRACT_MISMATCH&&!c,"fallback refused");
        auto p=profile;p["status"]="DEPLOYMENT_PENDING_BOARD";write_json("profile.json",p);
        check(sp_linear_open_v1(cfg,&c)==SP_UNSUPPORTED&&!c,"pending profile denied");
        p=profile;p["kernel_build_id"]=1u;write_json("profile.json",p);
        check(sp_linear_open_v1(cfg,&c)==SP_CONTRACT_MISMATCH&&!c,"wrong selected build");
        write_json("profile.json",profile);denied=base;denied["xclbin_sha256"]=std::string(64,'0');write_json("denied.json",denied);
        check(sp_linear_open_v1("denied.json",&c)==SP_CONTRACT_MISMATCH&&!c,"bad payload hash");
        check(control::device_opens==0,"all policy failures before device discovery");
    }else if(mode.rfind("open_",0)==0){
        control::fault=mode.substr(5);
        check(sp_linear_open_v1(cfg,&c)!=0&&!c,"open exception does not escape");
        check(control::live==0,"failed open releases quiescent allocations");
    }else{
        check(sp_linear_open_v1(cfg,&c)==0&&c,"open control transport");
        sp_linear_context*other=nullptr;check(sp_linear_open_v1(cfg,&other)==SP_BUSY&&!other,"exclusive process lock");
        std::vector<uint8_t>w(2048,0);w[0]=0x21;w[16]=0xef;std::vector<float>sw(32,1),y(32,-999);
        std::vector<int8_t>x(128,0);x[0]=3;x[1]=1;float sx=1;uint64_t handle=0;
        auto load=[&]{return sp_linear_load_v1(c,2,2,w.data(),w.size(),sw.data(),128,&handle);};
        const auto io_live=control::live;
        if(mode=="load_failure"){
            control::fault="to_3";check(load()==SP_DEVICE_ERROR&&handle==0,"load sync failure translated");
            check(control::live==io_live,"unsubmitted weights cleaned");control::fault.clear();
        }
        check(load()==0&&handle,"load resident weight");std::fill(w.begin(),w.end(),0);sw.clear();
        const auto resident=control::live,allocs=control::allocations;
        const auto to_w=control::count("to_5"),to_sw=control::count("to_3");
        auto run=[&](uint64_t id=1,uint32_t timeout=5000){return sp_linear_run_v1(c,handle,1,x.data(),128,&sx,4,y.data(),128,id,timeout);};
        if(mode=="normal"||mode=="load_failure"){
            check(run()==0,"control completion copied");check(control::observed_weight==0x21,"owned W survives caller modification");
            check(std::all_of(y.begin(),y.end(),[](float v){return v==0;}),"fixed transport sentinel copied, NOT numeric verification");
            check(run(2)==0,"repeated call");
            check(control::allocations==allocs&&control::live==resident,"no steady-state allocations");
            check(control::count("to_5")==to_w&&control::count("to_3")==to_sw,"no weight reupload");
            for(unsigned i=6;i<17;++i)check(control::widths[i]==((i<=8||i==16)?4u:8u),"set_arg scalar C width");
            auto r=report(c);check(r["host_verified_completions"]==2&&r["output_consumable"]==true,"host bookkeeping only");
            check(run(2)==SP_BAD_ARGUMENT,"duplicate job refused");r=report(c);
            check(r["output_consumable"]==false,"failed attempt cannot expose prior success");
            x[0]=-128;check(run(3)==SP_NUMERIC_ERROR,"reserved A8 refused before start");x[0]=3;
            check(sp_linear_run_v1(c,handle,1,x.data(),127,&sx,4,y.data(),128,3,10)==SP_BUFFER_TOO_SMALL,"short input refused");
            check(sp_linear_run_v1(c,9999,1,x.data(),128,&sx,4,y.data(),128,3,10)==SP_BAD_ARGUMENT,"bad weight handle");
            check(control::starts==2,"invalid requests never reach transport start");
        }else if(mode=="concurrency"){
            control::fault="blocked";int rc=-1;std::thread worker([&]{rc=run(1,10000);});
            auto deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
            while(!control::started&&std::chrono::steady_clock::now()<deadline)std::this_thread::yield();
            if(!control::started){control::release_run=true;worker.join();throw std::runtime_error("test thread did not start");}
            int run_rc=run(2),close_rc=sp_linear_close_v1(c),unload_rc=sp_linear_unload_v1(c,handle);
            uint64_t n=0;int report_rc=sp_linear_report_v1(c,nullptr,0,&n);
            control::release_run=true;worker.join();
            check(run_rc==SP_BUSY&&close_rc==SP_BUSY&&unload_rc==SP_BUSY&&report_rc==SP_BUSY,"concurrent APIs reject while running");
            check(rc==0&&control::live==resident,"in-flight objects retained");control::fault.clear();
        }else{
            control::fault=mode;const auto meta_syncs=control::count("from_11"),y_syncs=control::count("from_9");
            const int rc=run(1,mode=="timeout"?8:5000);
            int want=SP_DEVICE_ERROR;
            if(mode=="timeout")want=SP_TIMEOUT;
            if(mode=="stale"||mode=="bad_job"||mode=="bad_build")want=SP_CONTRACT_MISMATCH;
            if(mode=="private_error"||mode=="nan_y"||mode=="tail_y")want=SP_NUMERIC_ERROR;
            check(rc==want,"injected fault status");check(control::live==resident,"fault retains all DMA owners");
            check(std::all_of(y.begin(),y.end(),[](float v){return v==-999;}),"caller Y unchanged on every fault");
            if(mode=="stale"||mode.rfind("bad_",0)==0||mode=="private_error"){
                check(control::count("from_11")==meta_syncs+1,"meta synchronized first");
                check(control::count("from_9")==y_syncs,"invalid meta never synchronizes Y");
            }
            check(run(2)==SP_POISONED&&sp_linear_unload_v1(c,handle)==SP_POISONED&&sp_linear_close_v1(c)==SP_POISONED,"poisoned run/unload/close rejected");
            uint64_t another=0;check(sp_linear_load_v1(c,2,2,w.data(),2048,&sx,4,&another)==SP_POISONED,"poisoned load rejected");
            auto r=report(c);check(r["status"]=="POISONED"&&r["output_consumable"]==false,"poison report");
            check(control::live==resident,"report cannot free poisoned ownership");
            std::cout<<json{{"domain","PC_CONTROL_DOUBLE_NOT_FPGA"},{"case",mode},{"checks",checks},{"retained_stub_allocations",resident},{"BOARD","NOT_TESTED"}}.dump()<<'\n';
            return 0; // process owns only test vectors, never hardware resources.
        }
        check(sp_linear_unload_v1(c,handle)==0,"quiescent unload");check(control::live==io_live,"weight BOs released after run bindings removed");
        check(sp_linear_close_v1(c)==0&&control::live==0,"safe close frees all test allocations");
        check(sp_linear_close_v1(c)==SP_BAD_ARGUMENT,"stale closed context lookup is not dereferenced");
    }
    std::cout<<json{{"domain","PC_CONTROL_DOUBLE_NOT_FPGA"},{"case",mode},{"checks",checks},{"BOARD","NOT_TESTED"}}.dump()<<'\n';return 0;
}catch(const std::exception&e){std::cerr<<"CONTROL_TEST_FAIL: "<<e.what()<<'\n';return 1;}
