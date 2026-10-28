"""Derive strict greedy fact-draft verification from the sealed checkpoint worker."""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[3]
EV = ROOT / 'evidence/model_pl_A/20261027-realtime-miss-opt-v1'
BASE = ROOT / 'evidence/model_pl_A/20261024-ttft10-01-v1/source-04'
SOURCE = EV / 'source'
REVISION = 'v1'
ARM_A53 = False

PARSE = r'''
        const size_t original_prompt_tokens=tokens.size();
        const bool draft_requested=req.value("draft_strategy",std::string())=="FACT_COPY_GREEDY_VERIFY_V1";
        if(req.contains("draft_strategy")&&!draft_requested)throw std::runtime_error("unknown draft strategy");
        std::vector<llama_token> draft_tokens,draft_predictions;
        std::vector<float> draft_prompt_logits;
        bool draft_used=false,draft_accepted=false,draft_replayed=false;
        double draft_sample_ms=0,draft_verify_ms=0,draft_replay_ms=0;
        int draft_checks=0;std::string draft_skip;
        if(draft_requested){
            if(create||!forced.empty()||!diag.empty())throw std::runtime_error("draft cannot combine with checkpoint creation, forced tokens or diagnostics");
            const auto proposal=req.at("draft_text").get<std::string>();
            if(proposal.size()>1024)throw std::runtime_error("draft text bound");
            int n=llama_tokenize(vocab,proposal.data(),proposal.size(),nullptr,0,false,false);
            if(n<0){draft_tokens.resize(-n);n=llama_tokenize(vocab,proposal.data(),proposal.size(),draft_tokens.data(),draft_tokens.size(),false,false);}
            if(n<0)throw std::runtime_error("draft tokenization");draft_tokens.resize(n);
            if(draft_tokens.empty())draft_skip="EMPTY";
            else if(draft_tokens.size()>=size_t(limit)||limit>64)draft_skip="OUTPUT_BOUND";
            else {
                for(auto t:draft_tokens)if(t<0||t>=nv||llama_vocab_is_eog(vocab,t))throw std::runtime_error("draft token invalid");
                draft_used=true;draft_predictions.assign(draft_tokens.size()+1,-1);
                tokens.insert(tokens.end(),draft_tokens.begin(),draft_tokens.end());
            }
        }
'''

PREFILL = r'''
        auto run_prefill=[&](bool verifying){
          for(size_t pos=prefix;pos<tokens.size();pos+=chunk){
            int count=std::min<size_t>(chunk,tokens.size()-pos);auto batch=llama_batch_get_one(tokens.data()+pos,count);
            trace.active=req.value("a12_consumer_trace",false)||(pos==0&&!diag.empty()&&req.value("diagnostic_nodes",false));
            std::vector<int8_t>flags(count,lm=="all"?1:0);
            if(verifying){for(int i=0;i<count;++i)if(pos+i+1>=original_prompt_tokens)flags[i]=1;}
            if(pos+count==tokens.size())flags.back()=1;
            batch.logits=flags.data();bridge.begin_execution();
            {bridge.route.set_phase(0);s1::DecodeScope measured(bridge.request_stats,0);rc=llama_decode(ctx,batch);measured.rc=rc;}
            if(!trace.error.empty())throw std::runtime_error("Node diagnostic: "+trace.error);
            bridge.route.finish_execution();
            if(rc||cancelled||!bridge.error.empty()){failed=true;break;}
            for(int i=0;i<count;++i)if(flags[i]){
                ++requested;
                if(verifying&&pos+i+1>=original_prompt_tokens){
                    size_t at=pos+i+1-original_prompt_tokens;
                    const float* l=llama_get_logits_ith(ctx,i);if(!l)throw std::runtime_error("draft verification logits absent");
                    if(at==0)draft_prompt_logits.assign(l,l+nv);
                    auto begin=Clock::now();auto* s=llama_sampler_init_greedy();
                    draft_predictions.at(at)=llama_sampler_sample(s,ctx,i);llama_sampler_free(s);
                    draft_sample_ms+=ms(begin);++draft_checks;
                }
                if(!diag.empty()){auto name="logits-prefill-"+std::to_string(pos+i)+".f32";write_binary(std::filesystem::path(diag)/name,llama_get_logits_ith(ctx,i),nv*4);logits_records.push_back({{"position",pos+i},{"file",name}});}
            }
          }
        };
        run_prefill(draft_used);
'''

VERIFY = r'''
        if(draft_used&&!failed&&!cancelled){
            draft_verify_ms=prefill_ms;
            draft_accepted=draft_checks==int(draft_tokens.size()+1)&&llama_vocab_is_eog(vocab,draft_predictions.back());
            for(size_t i=0;i<draft_tokens.size();++i)draft_accepted=draft_accepted&&draft_predictions[i]==draft_tokens[i];
            if(!draft_accepted){
                // DeltaNet/conv/KV are never partially truncated. Discard all draft
                // state, restore only the independently verified neutral prefix,
                // then replay the original prompt and sample normally.
                auto begin=Clock::now();draft_replayed=true;
                bridge.route.finish_execution();llama_synchronize(ctx);
                llama_memory_clear(llama_get_memory(ctx),true);bridge.cache.valid=false;
                if(llama_memory_seq_pos_max(llama_get_memory(ctx),0)!=-1)throw std::runtime_error("draft rejection clear failed");
                if(checkpoint)restore_prefix(ctx,*checkpoint);
                tokens.resize(original_prompt_tokens);run_prefill(false);
                draft_replay_ms=ms(begin);
                if(!failed&&!cancelled){const float* l=llama_get_logits_ith(ctx,-1);loghash=fnv(l,nv*4);logits_sha=tt10::digest(l,nv*4);}
            }
        }
'''

ACCEPT = r'''
        if(draft_accepted&&!failed&&!cancelled){
            // Emit only tokens individually selected by the real target model.
            // The fact draft is never returned merely because the checker likes it.
            for(size_t i=0;i<draft_tokens.size();++i){
                auto tok=draft_predictions[i];char buffer[256];int n=llama_token_to_piece(vocab,tok,buffer,sizeof(buffer),0,true);
                if(n<0){failed=true;rc=-99;break;}
                out.push_back(tok);text.append(buffer,n);
                emit({{"type","token"},{"id",id},{"index",i},{"token",tok}});
            }
            eos=!failed;ttft_ms=ms(start);
        }
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derive():
    shutil.copytree(BASE, SOURCE)
    path = SOURCE / 'main.cpp'
    before = path.read_text(encoding='utf-8')
    text = before
    def change(old, new):
        nonlocal text
        assert text.count(old) == 1, old[:120]
        text = text.replace(old, new, 1)
    change('emit({{"prefix_cache",cache.report()},{"type","ready"}',
           'emit({{"realtime_draft","FACT_COPY_GREEDY_VERIFY_V1"},{"prefix_cache",cache.report()},{"type","ready"}')
    change('        const bool report_diagnostic=req.value("diagnostic_report",false)||!diag.empty();',
           PARSE + '\n        const bool report_diagnostic=req.value("diagnostic_report",false)||!diag.empty();')
    start = text.index('        for(size_t pos=prefix;pos<tokens.size();pos+=chunk)')
    end = text.index('        trace.active=req.value("a12_consumer_trace",false);', start)
    text = text[:start] + PREFILL + text[end:]
    change('const float*l=checkpoint&&prefix==tokens.size()?checkpoint->logits.data():llama_get_logits_ith(ctx,-1);',
           'const float*l=draft_used?draft_prompt_logits.data():(checkpoint&&prefix==tokens.size()?checkpoint->logits.data():llama_get_logits_ith(ctx,-1));')
    change('decode_ms=0,sample_ms=0;', 'decode_ms=0,sample_ms=draft_sample_ms;')
    change('        auto*sampler=llama_sampler_init_greedy();std::vector<llama_token>out;std::string text;bool eos=false;',
           VERIFY + '\n        auto*sampler=llama_sampler_init_greedy();std::vector<llama_token>out;std::string text;bool eos=false;\n' + ACCEPT)
    change('for(int i=0;!failed&&!cancelled&&i<limit;++i)', 'for(int i=0;!draft_accepted&&!failed&&!cancelled&&i<limit;++i)')
    change('{"prompt_tokens",tokens.size()},{"output_tokens",out}', '{"prompt_tokens",original_prompt_tokens},{"output_tokens",out}')
    change('        emit({{"prefix_cache_request",cache_result}', '''
        json speculative={{"strategy",draft_requested?"FACT_COPY_GREEDY_VERIFY_V1":"SERIAL_GREEDY"},
            {"requested",draft_requested},{"used",draft_used},{"accepted",draft_accepted},
            {"proposed_tokens",draft_tokens},{"target_greedy_tokens",draft_predictions},{"argmax_checks",draft_checks},
            {"target_eos_verified",draft_accepted},{"fallback_full_prompt_replayed",draft_replayed},
            {"skip_reason",draft_skip},{"verify_ms",draft_verify_ms},{"replay_ms",draft_replay_ms},
            {"draft_sampler_ms",draft_sample_ms},{"answer_cache_used",false},{"forced_output",false},
            {"original_prompt_tokens",original_prompt_tokens},{"first_pass_tokens",original_prompt_tokens+(draft_used?draft_tokens.size():0)}};
        cache_result["new_tokens"]=original_prompt_tokens-prefix;
        cache_result["speculative_extra_tokens"]=draft_used?draft_tokens.size():0;
        emit({{"speculative_decoding",speculative},{"prefix_cache_request",cache_result}''')
    path.write_text(text, encoding='utf-8')
    (EV / 'native-change.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True), text.splitlines(True), fromfile='sealed/source-04/main.cpp', tofile='realtime-draft/main.cpp')), encoding='utf-8')
    rows = []
    for p in sorted(SOURCE.iterdir()):
        if p.is_file():
            if p.name != 'main.cpp':
                assert digest(p) == digest(BASE / p.name), p
            rows.append(dict(name=p.name, sha256=digest(p), base_sha256=digest(BASE / p.name)))
    (EV / ('SOURCE-' + REVISION + '.json')).write_text(json.dumps(dict(base=str(BASE.relative_to(ROOT)), files=rows,
        only_changed='main.cpp', math_HLS_ABI_libraries_unchanged=True, BOARD='NOT_TESTED'), indent=2) + '\n', encoding='utf-8')


def build(domain):
    old = Path('/home/member-a/kv260-build/a12-tt10-01-20261024-v1')
    base_build = old / ('pc04' if domain == 'PC' else 'arm04')
    if not (base_build / 'CMakeCache.txt').is_file():
        raise FileNotFoundError(base_build)
    cfg = {}
    for line in (base_build / 'CMakeCache.txt').read_text().splitlines():
        if '=' in line and ':' in line.split('=', 1)[0]:
            key, value = line.split('=', 1)
            cfg[key.split(':', 1)[0]] = value
    tag=REVISION+('-a53' if domain=='ARM' and ARM_A53 else '')
    target = Path('/home/member-a/kv260-build/a12-realtime-draft-20261027-v1') / (domain.lower() + '-' + tag)
    args = ['cmake', '-S', str(old / 'cmake'), '-B', str(target)]
    for key in ('BASE_BUILD', 'LLAMA_BUILD', 'LLAMA_SOURCE', 'ROOT', 'ASSET_ROOT', 'CMAKE_TOOLCHAIN_FILE'):
        if cfg.get(key):
            args.append('-D' + key + '=' + cfg[key])
    args.extend(['-DA12_SOURCE=' + str(SOURCE), '-DCMAKE_BUILD_TYPE=Release'])
    build_env=dict(os.environ)
    if domain=='ARM' and ARM_A53:
        flags=cfg['CMAKE_CXX_FLAGS']
        assert '-mcpu=cortex-a53' in flags and '-march=native' not in flags
        args.append('-DCMAKE_CXX_FLAGS='+flags)
        # OEToolchainConfig.cmake FORCE-copies ENV{CXXFLAGS} over a -D value.
        # Match the accepted A53 flags in this subprocess environment as well.
        build_env['CXXFLAGS']=flags
        build_env['CFLAGS']=flags
    subprocess.run(args, check=True,env=build_env)
    if domain=='ARM' and ARM_A53:
        actual=(target/'CMakeFiles/qwen35-a12.dir/flags.make').read_text()
        assert '-mcpu=cortex-a53' in actual and '-march=native' not in actual
    subprocess.run(['cmake', '--build', str(target), '--parallel', '2'], check=True,env=build_env)
    result = dict(domain=domain, binary=str(target / 'qwen35-a12'), sha256=digest(target / 'qwen35-a12'),
                  base_binary=str(base_build / 'qwen35-a12'), configured=args, BOARD='NOT_TESTED')
    (EV / ('BUILD-' + domain + '-' + tag + '.json')).write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--derive', action='store_true')
    parser.add_argument('--build', choices=('PC', 'ARM'))
    parser.add_argument('--revision', default='v2', choices=('v2', 'v3', 'v4'))
    parser.add_argument('--arm-a53',action='store_true')
    args = parser.parse_args()
    REVISION = args.revision
    ARM_A53 = args.arm_a53
    SOURCE = EV / ('source-' + REVISION)
    if args.derive:
        derive()
    if args.build:
        build(args.build)
