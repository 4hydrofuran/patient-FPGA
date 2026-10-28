"""Derive timing-only sources and an optional private compact completion reader.

The received B kernel, public ABI, mathematics and frozen sources stay unchanged.
"""
import json
import shutil
from common import ROOT, sha, save
from step10_common import OUT


if __name__ == '__main__':
    prior = ROOT / 'evidence/model_pl_A/20261023-step07-single-v1/source-v1'
    src = OUT / 'source-v1'
    shutil.copytree(prior, src)
    changes = {}

    def patch(name, pairs):
        p = src / name
        before = sha(p)
        s = p.read_text(encoding='utf-8')
        for old, new in pairs:
            assert s.count(old) == 1, (name, old)
            s = s.replace(old, new)
        p.write_text(s, encoding='utf-8', newline='\n')
        changes[name] = dict(before=before, after=sha(p))

    patch('backend.cpp', [
        ('    a12::permit("submit",job);\n    auto start=Clock::now();',
         '    auto permission_start=Clock::now();\n    a12::permit("submit",job);\n    auto start=Clock::now();'),
        ('c->last={{"a12_observed_ert_state",observed_ert}',
         'c->last={{"a12_permission_wait_ms",ms(permission_start,start)},{"a12_observed_ert_state",observed_ert}'),
        ('extern "C" int32_t sp_linear_unload_v1', '''// Private A12 read-only extension: identical last validated completion, no BO inventory.
extern "C" int32_t sp_a12_completion_report_v1(sp_linear_context*c,char*dst,uint64_t capacity,uint64_t*required)try{
    if(!required||(!dst&&capacity))return SP_BAD_ARGUMENT;
    auto lock=locked(c);
    json j=c->last.is_null()?json::object():c->last;
    j["job_id"]=c->life.job();j["kernel_build_id"]=c->build;
    j["status"]=c->life.phase()==a07::Phase::POISONED?"POISONED":"READY";
    j["host_verified_completions"]=c->runs;
    auto s=j.dump();*required=s.size()+1;if(!dst)return SP_OK;
    if(capacity<*required)return SP_BUFFER_TOO_SMALL;
    std::memcpy(dst,s.c_str(),*required);return SP_OK;
}catch(...){return error();}
extern "C" int32_t sp_linear_unload_v1''')])
    patch('sp_abi.map', [('  local: *;', '          sp_a12_completion_report_v1;\n  local: *;')])
    patch('route.hpp', [
        ('    json policy,ledger=json::array();', '''    decltype(&sp_linear_report_v1)completion_fn=nullptr;
    bool compact_completion=false,profile_on=false;int profile_phase=0;
    struct Metrics {uint64_t calls=0;double run_ms=0,report_ms=0;std::map<std::string,double> backend;};
    std::array<Metrics,2> metrics{};
    json policy,ledger=json::array();'''),
        ('#include <map>', '#include <map>\n#include <array>'),
        ('    void park_if_unsafe()const;', '''    void park_if_unsafe()const;
    void begin_profile(bool on){profile_on=on;profile_phase=0;metrics={};}
    void set_phase(int p){profile_phase=p;}
    json performance()const;
    json completion()const;''')])
    patch('route.cpp', [
        ('    A12_LOAD(open);A12_LOAD(load);A12_LOAD(run);A12_LOAD(report);A12_LOAD(unload);A12_LOAD(close);',
         '''    A12_LOAD(open);A12_LOAD(load);A12_LOAD(run);A12_LOAD(report);A12_LOAD(unload);A12_LOAD(close);
    compact_completion=policy.value("a12_compact_completion",false);
    if(compact_completion){completion_fn=reinterpret_cast<decltype(completion_fn)>(dlsym(library,"sp_a12_completion_report_v1"));need(completion_fn,"A12 private completion reader absent");}'''),
        ('    int rc=run_fn(context,h,t,x,xb,sx,sb,y,yb,job,timeout);',
         '    auto call_start=std::chrono::steady_clock::now();\n    int rc=run_fn(context,h,t,x,xb,sx,sb,y,yb,job,timeout);\n    auto call_end=std::chrono::steady_clock::now();'),
        ('    auto r=report();\n    if(real&&', '''    auto report_start=std::chrono::steady_clock::now();
    auto r=compact_completion?completion():report();
    auto report_end=std::chrono::steady_clock::now();
    if(profile_on){auto&m=metrics[profile_phase];++m.calls;
        m.run_ms+=std::chrono::duration<double,std::milli>(call_end-call_start).count();
        m.report_ms+=std::chrono::duration<double,std::milli>(report_end-report_start).count();
        for(auto k:{"a12_permission_wait_ms","service_ms","a11_input_copy_and_meta_seed_ms","a11_input_bo_sync_ms","a11_set_args_ms","a11_submit_to_confirmed_completion_ms","a11_meta_sync_ms","a11_meta_validate_ms","a11_output_bo_sync_and_map_ms","a11_output_validate_ms"})m.backend[k]+=r.at(k).get<double>();
    }
    if(real&&'''),
        ('void Route::close_checked(){', '''json Route::completion()const{
    uint64_t size=0;need(completion_fn(context,nullptr,0,&size)==SP_OK&&size<=65536,"A12 compact report query");
    std::vector<char>data(size);need(completion_fn(context,data.data(),size,&size)==SP_OK,"A12 compact report read");
    return json::parse(data.data());
}
json Route::performance()const{
    json r={{"enabled",profile_on},{"compact_completion",compact_completion},{"phases",json::object()}};
    for(int p=0;p<2;++p){const auto&m=metrics[p];r["phases"][p?"decode":"prefill"]={{"calls",m.calls},{"backend_call_wall_ms",m.run_ms},{"completion_report_wall_ms",m.report_ms},{"backend",m.backend}};}
    r["timing_scope"]="HOST_WALL_NOT_DEVICE_CYCLES; backend call includes permission; report is a sibling; backend fields are nested";return r;
}
void Route::close_checked(){''')])
    patch('request_profile.hpp', [
        ('    std::array<PhaseTiming,2> phases{};', '''    struct NodeBucket {uint64_t calls=0,fused_extra=0,microseconds=0;};
    std::array<std::array<NodeBucket,7>,2> node_buckets{};
    std::array<PhaseTiming,2> phases{};'''),
        ('phases={};ops={};', 'phases={};ops={};node_buckets={};'),
        ('    json report()const;', '''    json report()const;
    json node_report()const;
    static void node_observed(const ggml_tensor*,int,uint64_t,void*);'''),
        ('#include "json.hpp"', '#include "json.hpp"\n#include "ggml.h"')])
    p = src / 'request_profile.cpp'
    with p.open('a', encoding='utf-8', newline='\n') as f:
        f.write('''
namespace s1 {
void PerRequestStats::node_observed(const ggml_tensor*t,int fused,uint64_t us,void*u){
    auto&s=*static_cast<PerRequestStats*>(u);if(!s.enabled)return;
    const char*n=t->name;int c=6;
    if(t->op==GGML_OP_CUSTOM&&(std::strstr(n,"ffn_gate")||std::strstr(n,"ffn_up")||std::strstr(n,"ffn_down")))c=0;
    else if(std::strstr(n,"result_output")||(t->op==GGML_OP_MUL_MAT&&t->src[0]&&std::strcmp(t->src[0]->name,"output.weight")==0))c=1;
    else if(t->op==GGML_OP_GATED_DELTA_NET||t->op==GGML_OP_SSM_SCAN)c=3;
    else if(t->op==GGML_OP_SSM_CONV)c=4;
    else if(t->op==GGML_OP_CPY&&(std::strstr(n,"state")||std::strstr(n,"cache")||std::strstr(n,"ssm")))c=5;
    else if(t->op==GGML_OP_FLASH_ATTN_EXT||std::strstr(n,"attn"))c=2;
    else if(std::strstr(n,"ssm"))c=3;
    auto&v=s.node_buckets[s.phase][c];++v.calls;v.fused_extra+=fused;v.microseconds+=us;
}
json PerRequestStats::node_report()const{
    json r={{"enabled",enabled},{"phases",json::object()},
      {"scope","thread0 elapsed including existing node barrier; fusion unchanged; fused group attributed to first node; nested MLP must not be added twice"},
      {"linear_attention_state_split","FUSED_GATED_DELTA_NET_STATE_UPDATE_NOT_SEPARATELY_TIMED"}};
    const char*names[]={"mlp_custom","output_head","attention_named_projections_and_full_attention","linear_attention_and_fused_state","linear_convolution","explicit_state_copy","other_norm_activation_residual"};
    for(int p=0;p<2;++p)for(int c=0;c<7;++c){auto&v=node_buckets[p][c];r["phases"][p?"decode":"prefill"][names[c]]={{"calls",v.calls},{"fused_extra_nodes",v.fused_extra},{"wall_ms",v.microseconds/1000.0}};}
    return r;
}
}
''')
    changes['request_profile.cpp'] = dict(before=sha(prior / 'request_profile.cpp'), after=sha(p))
    patch('main.cpp', [
        ('#include <sys/resource.h>', '#include <sys/resource.h>\n#include <dlfcn.h>'),
        ('    NodeTrace trace;trace.bridge=&bridge;', '''    using SetNodeHook=void(*)(void(*)(const ggml_tensor*,int,uint64_t,void*),void*);
    auto node_hook=reinterpret_cast<SetNodeHook>(dlsym(RTLD_DEFAULT,"sp_a12_set_node_profile_v1"));
    if(!node_hook)throw std::runtime_error("A12 fixed CPU node timer unavailable");
    NodeTrace trace;trace.bridge=&bridge;'''),
        ('        if(op=="reset")', '''        bridge.route.begin_profile(req.value("profile",false));
        node_hook(req.value("profile",false)?s1::PerRequestStats::node_observed:nullptr,&bridge.request_stats);
        if(op=="reset")'''),
        ('{s1::DecodeScope measured(bridge.request_stats,0);', '{bridge.route.set_phase(0);s1::DecodeScope measured(bridge.request_stats,0);'),
        ('{s1::DecodeScope measured(bridge.request_stats,1);', '{bridge.route.set_phase(1);s1::DecodeScope measured(bridge.request_stats,1);'),
        ('auto tok=forced.empty()?llama_sampler_sample(sampler,ctx,-1):forced[i];', 'auto sample_start=Clock::now();auto tok=forced.empty()?llama_sampler_sample(sampler,ctx,-1):forced[i];sample_ms+=ms(sample_start);'),
        ('double prefill_ms=ms(start),ttft_ms=0,decode_ms=0;', 'double prefill_ms=ms(start),ttft_ms=0,decode_ms=0,sample_ms=0;'),
        ('        auto request_profile=bridge.request_stats.report();bridge.request_stats.active=false;', '''        node_hook(nullptr,nullptr);
        auto request_profile=bridge.request_stats.report();request_profile["node_profile"]=bridge.request_stats.node_report();
        request_profile["pl_profile"]=bridge.route.performance();request_profile["sample_ms"]=sample_ms;
        bridge.request_stats.active=false;'''),
        ('}catch(const std::exception&e){trace.active=false;', '}catch(const std::exception&e){node_hook(nullptr,nullptr);trace.active=false;')])
    save(OUT / 'SOURCE_DERIVATION.json', dict(status='DERIVED_PRIVATE_TIMING_AND_OPTIONAL_COMPACT_REPORT',
        changes=changes, unchanged={p.name: sha(p) for p in src.iterdir() if p.is_file() and p.name not in changes},
        public_ABI_changed=False, B_core_changed=False, mathematics_changed=False,
        compact_reader='EXACT_SAME_LAST_VALIDATED_COMPLETION_WITHOUT_IMMUTABLE_BO_INVENTORY'))
    print(json.dumps({'status': 'TASK10_ISOLATED_SOURCES_READY', 'changed': list(changes)}))
