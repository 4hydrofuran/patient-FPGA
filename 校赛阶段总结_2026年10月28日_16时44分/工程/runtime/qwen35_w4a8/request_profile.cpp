#include "request_profile.hpp"
#include "ggml-backend.h"
#include <dlfcn.h>
#include <cstring>
#include <cstdlib>

namespace s1 {
thread_local PerRequestStats* active_profile=nullptr;
json PerRequestStats::report()const{
    json result={{"schema","N02_REQUEST_PROFILE_V1"},{"enabled",enabled},{"detail",detail},
        {"session_id",session},{"request_id",request},{"session_epoch",epoch},
        {"scope","CURRENT_REQUEST_NOT_LAST_OPERATION_OR_LIFETIME"},{"BOARD","NOT_TESTED"}};
    if(!enabled){result["phases"]=nullptr;return result;}
    result["phases"]=json::object();result["layers"]=detail?json::array():json(nullptr);bool valid=!non_cpu;
    for(int p=0;p<2;++p){OpTiming sum;json shapes=json::object();
        for(int l=0;l<24;++l)for(int op=0;op<3;++op)for(int t=0;t<9;++t){
            const auto&o=ops[((p*24+l)*3+op)*9+t];if(!o.calls)continue;
            sum.calls+=o.calls;sum.failures+=o.failures;sum.inclusive+=o.inclusive;sum.gather+=o.gather;sum.quant+=o.quant;
            sum.cache_copy+=o.cache_copy;sum.run+=o.run;sum.output_copy+=o.output_copy;sum.cache_hits+=o.cache_hits;
            shapes[std::to_string(t)]=shapes.value(std::to_string(t),uint64_t(0))+o.calls;
            if(detail)result["layers"].push_back({{"phase",p?"decode":"prefill"},{"layer",l},{"op",op==0?"gate":op==1?"up":"down"},
                {"N",o.n},{"K",o.k},{"T",t},{"calls",o.calls},{"failures",o.failures},{"first_execution",o.first_execution},
                {"last_execution",o.last_execution},{"wall_ms",o.inclusive/1e6},{"linear_service_ms",o.run/1e6},
                {"gather_ms",o.gather/1e6},{"activation_quant_ms",o.quant/1e6},{"activation_cache_copy_ms",o.cache_copy/1e6},
                {"output_copy_ms",o.output_copy/1e6},{"gate_up_cache_hits",o.cache_hits}});
        }
        const auto&x=phases[p];double other=(double(x.graph_wall)-sum.inclusive)/1e6;
        double host=(double(x.decode_wall)-x.graph_wall)/1e6;
        double overhead=(double(sum.inclusive)-sum.gather-sum.quant-sum.cache_copy-sum.run-sum.output_copy)/1e6;
        if(other<0||host<0||overhead<0||(x.decode_calls&&!x.graph_calls))valid=false;
        result["phases"][p?"decode":"prefill"]={{"llama_decode_wall_ms",x.decode_wall/1e6},{"decode_calls",x.decode_calls},{"decode_failures",x.decode_failures},
            {"cpu_graph_wall_ms",x.graph_wall/1e6},{"graph_calls",x.graph_calls},{"graph_failures",x.graph_failures},
            {"mlp_inclusive_wall_ms",sum.inclusive/1e6},{"mlp_calls",sum.calls},{"mlp_failures",sum.failures},
            {"linear_service_wall_ms",sum.run/1e6},{"activation_gather_ms",sum.gather/1e6},{"activation_quant_ms",sum.quant/1e6},
            {"activation_cache_copy_ms",sum.cache_copy/1e6},{"output_copy_ms",sum.output_copy/1e6},{"bridge_other_ms",overhead},
            {"non_mlp_cpu_graph_ms",other},{"host_graph_prepare_schedule_ms",host},{"physical_T_calls",shapes},
            {"gate_up_cache_hits",sum.cache_hits}};
    }
    result["accounting_valid"]=valid;
    result["non_mlp_scope"]="CPU backend graph wall minus nested MLP custom callbacks; includes other ops, backend planning, thread scheduling/barriers, not pure attention FLOPs";
    result["nesting"]="llama_decode = cpu_graph + host_prepare_schedule; cpu_graph = MLP_inclusive + non_MLP; MLP = linear_service + quant/gather/cache/output_copy + bridge_other; never sum parents with children";
    return result;
}
}

// Linux ELF interposition of the existing exported API, pinned source audited:
// ggml-backend.cpp delegates to iface.graph_compute; the CPU implementation
// returns only after ggml_graph_compute completes. No extra sync, node split,
// callback selection, graph mutation, fusion change or tensor read is introduced.
// Fail closed for timing if the caller is not the single synchronous CPU backend.
extern "C" enum ggml_status ggml_backend_graph_compute_async(ggml_backend_t backend,ggml_cgraph* graph){
    using Fn=enum ggml_status(*)(ggml_backend_t,ggml_cgraph*);
    static Fn original=reinterpret_cast<Fn>(dlsym(RTLD_NEXT,"ggml_backend_graph_compute_async"));
    if(!original)std::abort();
    auto*s=s1::active_profile;
    if(!s||!s->enabled)return original(backend,graph);
    if(std::strcmp(ggml_backend_name(backend),"CPU")!=0)s->non_cpu=true;
    auto begin=s1::tick_ns();auto rc=original(backend,graph);
    auto&p=s->phases[s->phase];p.graph_wall+=s1::tick_ns()-begin;++p.graph_calls;if(rc!=GGML_STATUS_SUCCESS)++p.graph_failures;
    return rc;
}
