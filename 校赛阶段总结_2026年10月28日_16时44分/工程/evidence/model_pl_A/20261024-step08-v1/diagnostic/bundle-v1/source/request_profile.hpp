#pragma once
#include "json.hpp"
#include <array>
#include <chrono>
#include <cstdint>
#include <string>

namespace s1 {
using json=nlohmann::json;
inline uint64_t tick_ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
struct OpTiming {
    uint64_t calls=0,failures=0,inclusive=0,gather=0,quant=0,cache_copy=0,run=0,output_copy=0,cache_hits=0;
    uint64_t first_execution=0,last_execution=0;int n=0,k=0;
};
struct PhaseTiming {uint64_t decode_calls=0,decode_failures=0,decode_wall=0,graph_calls=0,graph_failures=0,graph_wall=0;};
struct PerRequestStats {
    bool enabled=false,detail=false,active=false,non_cpu=false;
    int phase=0;std::string session,request;uint64_t epoch=0;
    std::array<PhaseTiming,2> phases{};
    std::array<OpTiming,2*24*3*9> ops{};
    void begin(bool on,bool detailed,std::string sid,std::string rid,uint64_t ep){
        enabled=on;detail=detailed;active=true;non_cpu=false;phase=0;session=std::move(sid);request=std::move(rid);epoch=ep;phases={};ops={};
    }
    void add(int layer,int op,int t,int n,int k,uint64_t execution,const OpTiming&v){
        if(!enabled||layer<0||layer>=24||op<0||op>=3||t<0||t>8)return;
        auto&o=ops[((phase*24+layer)*3+op)*9+t];
        o.calls+=v.calls;o.failures+=v.failures;o.inclusive+=v.inclusive;o.gather+=v.gather;o.quant+=v.quant;
        o.cache_copy+=v.cache_copy;o.run+=v.run;o.output_copy+=v.output_copy;o.cache_hits+=v.cache_hits;
        o.n=n;o.k=k;if(!o.first_execution)o.first_execution=execution;o.last_execution=execution;
    }
    json report()const;
};
// Installed only around a synchronous llama_decode invocation, never graph construction.
extern thread_local PerRequestStats* active_profile;
struct DecodeScope {
    PerRequestStats&s;uint64_t begin=0;int phase;int rc=-1;
    DecodeScope(PerRequestStats&stats,int p):s(stats),phase(p){s.phase=p;if(s.enabled){begin=tick_ns();active_profile=&s;}}
    ~DecodeScope(){if(s.enabled){active_profile=nullptr;auto&p=s.phases[phase];p.decode_wall+=tick_ns()-begin;++p.decode_calls;if(rc)++p.decode_failures;}}
};
struct OperationScope {
    PerRequestStats&s;OpTiming value;int layer,op,t,n,k;uint64_t execution,begin=0;bool ok=false;
    OperationScope(PerRequestStats&stats,int l,int o,int tt,int nn,int kk,uint64_t ex):s(stats),layer(l),op(o),t(tt),n(nn),k(kk),execution(ex){if(s.enabled)begin=tick_ns();}
    ~OperationScope(){if(s.enabled){value.inclusive=tick_ns()-begin;value.calls=1;value.failures=ok?0:1;s.add(layer,op,t,n,k,execution,value);}}
};
}
