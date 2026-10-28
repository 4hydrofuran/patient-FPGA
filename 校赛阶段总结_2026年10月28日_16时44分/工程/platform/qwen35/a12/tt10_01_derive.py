"""Derive a private checkpoint worker from CPU01/02 without changing math/PL sources."""
import difflib
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1'
BASE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/source'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')


HELPERS=r'''
// The pinned state API serializes memory only, despite its public comment.
// Last-position full logits and fresh-greedy sampling semantics are explicit.
static std::string sequence_digest(llama_context*ctx){
    llama_synchronize(ctx);size_t n=llama_state_seq_get_size(ctx,0);
    if(!n||n>tt10::PrefixStore::SCRATCH_BYTES)throw std::runtime_error("checkpoint sequence scratch limit");
    std::vector<uint8_t> s(n);if(llama_state_seq_get_data(ctx,s.data(),n,0)!=n)throw std::runtime_error("checkpoint sequence read");
    return tt10::digest(s.data(),s.size());
}
static tt10::Snapshot capture_prefix(llama_context*ctx,const std::vector<llama_token>&tokens,const json&owner,int nv){
    llama_synchronize(ctx);size_t n=llama_state_get_size(ctx);
    if(!n||n+size_t(nv)*4+tokens.size()*4+2048>tt10::PrefixStore::SLOT_BYTES)throw std::runtime_error("checkpoint state/logits size limit");
    tt10::Snapshot s;s.state.resize(n);
    if(llama_state_get_data(ctx,s.state.data(),n)!=n)throw std::runtime_error("checkpoint full state read");
    const auto* logits=llama_get_logits_ith(ctx,-1);if(!logits)throw std::runtime_error("checkpoint logits absent");
    s.logits.assign(logits,logits+nv);for(float v:s.logits)if(!std::isfinite(v))throw std::runtime_error("checkpoint nonfinite logits");
    s.tokens=tokens;s.owner=owner;s.position=llama_memory_seq_pos_max(llama_get_memory(ctx),0);
    s.sequence_sha=sequence_digest(ctx);return s;
}
static void restore_prefix(llama_context*ctx,const tt10::Snapshot&s){
    llama_synchronize(ctx);
    if(llama_state_set_data(ctx,s.state.data(),s.state.size())!=s.state.size())throw std::runtime_error("checkpoint full state restore failed");
    if(llama_memory_seq_pos_max(llama_get_memory(ctx),0)!=s.position||sequence_digest(ctx)!=s.sequence_sha)throw std::runtime_error("checkpoint independent sequence verification failed");
}
static llama_token saved_logits_sample(llama_sampler*sampler,const std::vector<float>&logits){
    // Same public apply/accept sequence as pinned llama_sampler_sample's CPU fallback.
    std::vector<llama_token_data> candidates;candidates.reserve(logits.size());
    for(size_t i=0;i<logits.size();++i)candidates.push_back({llama_token(i),logits[i],0.0f});
    llama_token_data_array data{candidates.data(),candidates.size(),-1,false};llama_sampler_apply(sampler,&data);
    if(data.selected<0||size_t(data.selected)>=data.size)throw std::runtime_error("saved-logits sampler selection");
    auto token=data.data[data.selected].id;llama_sampler_accept(sampler,token);return token;
}
'''


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--tag',default='01');tag=ap.parse_args().tag
    assert tag in ('01','02','03')
    source=OUT/('source' if tag=='01' else 'source-'+tag);shutil.copytree(BASE,source)
    shutil.copyfile(ROOT/'runtime/qwen35_w4a8/a12/tt10_01/prefix_cache.hpp',source/'prefix_cache.hpp')
    path=source/'main.cpp';before=path.read_text(encoding='utf-8');text=before
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,old[:120]
        text=text.replace(old,new,1)
    replace('#include "bridge.hpp"','#include "bridge.hpp"\n#include "prefix_cache.hpp"')
    replace('int main(int argc,char**argv)',HELPERS+'\nint main(int argc,char**argv)')
    replace('    emit({{"type","ready"}', '''    auto cache=tt10::PrefixStore::load(argv[1],argv[0],bridge.route.real?"FPGA_REAL":bridge.route.enabled?"PC_MATH_DOUBLE":"CPU_REFERENCE",threads,kernel_threads,context,physical);
    emit({{"prefix_cache",cache.report()},{"type","ready"}''')
    replace('if(op=="reset"){cancelled=0;', 'if(op=="reset"){cache.clear();cancelled=0;')
    replace('        if(req.value("cache_policy",std::string("R0"))!="R0")throw std::runtime_error("Unverified R1/R2 is disabled; explicit R0 replay required");',r'''
        if(op=="cache_status"){emit({{"type","cache_status"},{"id",id},{"prefix_cache",cache.report()}});continue;}
        if(op=="cache_drop"){cache.drop(req.at("cache_id"));emit({{"type","cache_dropped"},{"id",id},{"prefix_cache",cache.report()}});continue;}
#ifdef SP_A12_PC_TEST
        if(op=="cache_damage_test"){cache.damage(req.at("cache_id"),req.at("kind"));emit({{"type","cache_damaged_test"},{"id",id}});continue;}
#endif
        const auto policy=req.value("cache_policy",std::string("R0"));const bool create=op=="cache_create";
        if(policy!="R0"&&policy!="TT10_PFX_V1"&&policy!="TT10_REQUIRE_HIT")throw std::runtime_error("Unverified R1/R2 disabled; select explicit R0 or TT10 prefix policy");
        if(create&&policy!="R0")throw std::runtime_error("checkpoint preparation must start from R0");
'''.strip())
    replace('if(op!="generate")throw std::runtime_error("operation");','if(op!="generate"&&!create)throw std::runtime_error("operation");')
    replace('        auto cpu_before=bridge.report(false);','''        if(create){if(limit!=1||!forced.empty())throw std::runtime_error("checkpoint creation cannot generate an answer");cache.reserve_create(req,tokens);}
        auto cpu_before=bridge.report(false);''')
    replace('        start=Clock::now();int rc=0;bool failed=false;size_t requested=0;json logits_records=json::array();',r'''
        json cache_result={{"policy",policy},{"hit",false},{"reason",policy=="R0"?"EXPLICIT_R0":"NOT_FOUND"},{"reused_tokens",0},{"new_tokens",tokens.size()},{"restore_ms",0.0},{"lookup_ms",0.0},{"restore_error",nullptr}};
        const tt10::Snapshot* checkpoint=nullptr;size_t prefix=0;
        if(!create&&policy!="R0"){
            auto lookup_start=Clock::now();std::string reason;checkpoint=cache.lookup(req,tokens,reason);cache_result["lookup_ms"]=ms(lookup_start);cache_result["reason"]=reason;
            if(checkpoint){auto restore_start=Clock::now();try{
                bridge.route.finish_execution();restore_prefix(ctx,*checkpoint);prefix=checkpoint->tokens.size();
                cache_result["hit"]=true;cache_result["reused_tokens"]=prefix;cache_result["new_tokens"]=tokens.size()-prefix;
                cache_result["snapshot_bytes"]=checkpoint->bytes();
            }catch(const std::exception&e){cache_result["reason"]="RESTORE_FAILED_R0";cache_result["restore_error"]=e.what();cache.drop(req.at("cache_id"));checkpoint=nullptr;
                llama_memory_clear(llama_get_memory(ctx),true);if(llama_memory_seq_pos_max(llama_get_memory(ctx),0)!=-1)throw std::runtime_error("restore failure cleanup not proven");}
            cache_result["restore_ms"]=ms(restore_start);}
            if(!checkpoint&&policy=="TT10_REQUIRE_HIT")throw std::runtime_error("required prefix hit failed: "+cache_result["reason"].get<std::string>());
        }else if(!create){cache.owner_changed(tt10::PrefixStore::owner_of(req));}
        start=Clock::now();int rc=0;bool failed=false;size_t requested=0;json logits_records=json::array();
        if(checkpoint&&prefix==tokens.size()&&!diag.empty()){
            auto name="logits-prefill-"+std::to_string(prefix-1)+".f32";write_binary(std::filesystem::path(diag)/name,checkpoint->logits.data(),nv*4);logits_records.push_back({{"position",prefix-1},{"file",name}});++requested;
        }
'''.strip())
    replace('for(size_t pos=0;pos<tokens.size();pos+=chunk)', 'for(size_t pos=prefix;pos<tokens.size();pos+=chunk)')
    replace('        auto*sampler=llama_sampler_init_greedy();',r'''
        if(create){
            if(failed||cancelled)throw std::runtime_error("checkpoint preparation failed or cancelled; not committed");
            auto capture_start=Clock::now();bridge.route.finish_execution();auto snapshot=capture_prefix(ctx,tokens,tt10::PrefixStore::owner_of(req),nv);
            cache.commit(req.at("cache_id"),std::move(snapshot));double capture_ms=ms(capture_start);
            auto route=bridge.report(report_diagnostic);llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;node_hook(nullptr,nullptr);
            bridge.request_stats.active=false;
            emit({{"type","cache_created"},{"id",id},{"status","OK"},{"prefill_ms",prefill_ms},{"capture_ms",capture_ms},{"prefix_tokens",tokens.size()},{"peak_rss_kib",rss()},{"bridge",route},{"prefix_cache",cache.report()},{"state_cleared_before_response",true},{"state_position_after_clear",llama_memory_seq_pos_max(llama_get_memory(ctx),0)}});continue;
        }
        auto*sampler=llama_sampler_init_greedy();'''.strip())
    replace('const float*l=llama_get_logits_ith(ctx,-1);loghash=fnv(l,nv*4);', 'const float*l=checkpoint&&prefix==tokens.size()?checkpoint->logits.data():llama_get_logits_ith(ctx,-1);loghash=fnv(l,nv*4);')
    replace('uint64_t loghash=0;', 'uint64_t loghash=0;std::string logits_sha;')
    replace('loghash=fnv(l,nv*4);','loghash=fnv(l,nv*4);logits_sha=tt10::digest(l,nv*4);')
    replace('{"last_prompt_logits_fnv64",loghash}', '{"last_prompt_logits_fnv64",loghash},{"last_prompt_logits_sha256",logits_sha}')
    replace('state_fingerprint={{"bytes",size},{"fnv64",fnv(state.data(),state.size())}};', 'state_fingerprint={{"bytes",size},{"fnv64",fnv(state.data(),state.size())},{"sha256",tt10::digest(state.data(),state.size())}};')
    replace('forced.empty()?llama_sampler_sample(sampler,ctx,-1):forced[i]', 'forced.empty()?(i==0&&checkpoint&&prefix==tokens.size()?saved_logits_sample(sampler,checkpoint->logits):llama_sampler_sample(sampler,ctx,-1)):forced[i]')
    replace('        llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;\n        node_hook(nullptr,nullptr);', '        llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;\n        if(status!="OK")cache.clear_private();\n        node_hook(nullptr,nullptr);')
    replace('emit({{"type","result"}', 'emit({{"prefix_cache_request",cache_result},{"prefix_cache",cache.report()},{"type","result"}')
    replace('}catch(const std::exception&e){node_hook(nullptr,nullptr);trace.active=false;', '}catch(const std::exception&e){cache.clear_private();node_hook(nullptr,nullptr);trace.active=false;')
    path.write_text(text,encoding='utf-8',newline='\n')
    manifest_anchor='''            auto capture_start=Clock::now();bridge.route.finish_execution();'''
    replace(manifest_anchor,'''            if(!diag.empty()){json manifest={{"projections",bridge.dumps},{"logits",logits_records},{"teacher_tokens",forced},{"prompt_tokens",tokens},{"prefill_chunk",chunk},{"scope",bridge.scope}};std::ofstream f(std::filesystem::path(diag)/"manifest.json");f<<manifest.dump(2);}
'''+manifest_anchor)
    if tag=='03':
        replace('            cache.commit(req.at("cache_id"),std::move(snapshot));double capture_ms=ms(capture_start);', '''            if(cancelled)throw std::runtime_error("checkpoint capture cancelled; not committed");
            cache.commit(req.at("cache_id"),std::move(snapshot));double capture_ms=ms(capture_start);
            if(cancelled){cache.drop(req.at("cache_id"));throw std::runtime_error("checkpoint commit cancelled; discarded");}''')
    path.write_text(text,encoding='utf-8',newline='\n')
    (OUT/('worker-prefix-'+tag+'.patch')).write_text(''.join(difflib.unified_diff(before.splitlines(True),text.splitlines(True),fromfile='cpu02/source/main.cpp',tofile='tt10-01/source/main.cpp')),encoding='utf-8')
    save(OUT/('DERIVATION-'+tag+'.json'),dict(status='PRIVATE_NATIVE_PREFIX_CHECKPOINT_IMPLEMENTATION',base=str(BASE.relative_to(ROOT)),
        changed=['main.cpp'],added=['prefix_cache.hpp'],sources={p.name:sha(p) for p in source.iterdir() if p.is_file()},
        math_sources_unchanged=all(sha(p)==sha(BASE/p.name) for p in source.iterdir() if p.is_file() and p.name not in ('main.cpp','prefix_cache.hpp')),
        original_state_API_omits_logits=True,logits_saved_separately=True,PL_ownership_and_jobs_never_restored=True,cache_slots=2,max_slot_bytes=67108864))
    for rel in ['docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md']:
        p=OUT/'before'/rel
        if not p.exists():p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/rel,p)
    if not (OUT/'PROTECTED_BEFORE.json').exists():
        save(OUT/'PROTECTED_BEFORE.json',{rel:sha(ROOT/rel) for rel in ['runtime/qwen35_w4a8/sp-hook.cpp','config/qwen35/selection.json','contracts/qwen35/contracts.lock',
             'evidence/model_pl_A/20261024-ttft10-00-v1/SEAL.json','evidence/model_pl_A/20261024-cpu-opt-02-v1/SEAL.json']})
    print('TT10_01_DERIVED_NO_MATH_OR_PL_SAFETY_CHANGES')


if __name__=='__main__':main()
