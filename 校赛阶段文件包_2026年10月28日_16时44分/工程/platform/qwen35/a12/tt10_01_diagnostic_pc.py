"""Read-only source04 diagnostic reaudit, followed by a fresh application worker.

--reuse-diagnostics reads historical raw data only; it never resumes an old
worker. Each invocation requires a fresh --run directory, including offline runs.
"""
import argparse
import json
import shutil
from pathlib import Path
from tt10_01_common import ROOT,OUT,WORK,FROZEN,j,sha,save,config
from tt10_01_pc import environment,launch
from tt10_01_numeric import same_result,concatenated
from tt10_01_app import measure


def claim_run(name):
    if not name or not name.startswith('pc-diagnostic-04-') or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in name):
        raise ValueError('Use a fresh pc-diagnostic-04-* run name')
    base=OUT/name
    base.mkdir(exist_ok=False)  # Refuse before model launch; retain previous runs.
    return base


def audit_diagnostics(diag,base,check):
    old=OUT/'pc-run-04/pc-new'
    for worker in ('worker','worker-resume'):
        events=[json.loads(line) for line in (diag/worker/'events.jsonl').read_text().splitlines()]
        check('historical_'+worker+'_normal_exit',events[-1]['event']=='WORKER_EXITED_NORMALLY' and events[-1]['exit_code']==0)
    check('source04_legacy_R0_result',same_result(j(old/'legacy_diag/result.json'),j(diag/'legacy_diag/result.json'))['equal'])
    legacy_a={p.name:sha(p) for p in (old/'legacy_diag/diag').iterdir() if p.is_file()}
    legacy_b={p.name:sha(p) for p in (diag/'legacy_diag/diag').iterdir() if p.is_file()}
    save(base/'LEGACY_FILE_COMPARISON.json',dict(reference_files=len(legacy_a),actual_files=len(legacy_b),reference_sha256=legacy_a,actual_sha256=legacy_b))
    check('source04_legacy_443_binary_files_plus_manifest',len(legacy_a)==444 and 'manifest.json' in legacy_a and legacy_a==legacy_b)
    r=j(diag/'full_R0/result.json');h=j(diag/'full_hit/result.json')
    check('source04_chunk8_R0_unchanged',same_result(j(old/'full_R0/result.json'),r)['equal'])
    check('source04_chunk8_hit_R0_equal',same_result(r,h)['equal'])
    gate=concatenated(diag/'full_R0',diag/'warm_70',diag/'full_hit')
    # Historical schema predates explicit state SHA fields. Compare all its keys
    # and values; the extra raw state hashes are checked separately below.
    saved=j(diag/'NUMERICAL.json')
    legacy_keys=set(gate)-{'reference_state_sha256','restored_state_sha256'}
    check('saved_NUMERICAL_all_keys_and_values',set(saved)==legacy_keys and saved=={k:gate[k] for k in legacy_keys})
    check('source04_chunk8_all_projection_logits_state',gate['equal'] and gate['projection_streams']==144 and gate['full_logit_vectors']==108)
    # BOUNDARY_70 has counts/decisions, not stream hashes. Rehash saved source03
    # bytes without executing source03 or assigning its 89 checks to source04.
    reference=concatenated(old/'full_R0',old/'warm_70',old/'full_cache_70')
    boundary=j(OUT/'pc-run-04/BOUNDARY_70.json')['all_bytes']
    check('source03_saved_boundary_summary_matches_raw',set(boundary)<=set(reference) and boundary=={k:reference[k] for k in boundary} and reference['equal'])
    for field in ('reference_projection_sha256','restored_projection_sha256','reference_logits_sha256','restored_logits_sha256','reference_state_sha256','restored_state_sha256'):
        check('source04_matches_source03_'+field,gate[field]==reference[field])
    save(base/'NUMERICAL.json',gate);save(base/'SOURCE03_RAW_REFERENCE.json',reference)
    save(base/'OFFLINE_REAUDIT.json',dict(status='PASS_EXISTING_RAW_DIAGNOSTICS',diagnostic_directory=str(diag),source03_execution=False,
        checks=list(check.checks),source04_numeric_sha256=sha(base/'NUMERICAL.json'),source03_reference_sha256=sha(base/'SOURCE03_RAW_REFERENCE.json'),BOARD='NOT_TESTED'))
    return gate


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',required=True)
    ap.add_argument('--reuse-diagnostics',type=Path,required=True)
    ap.add_argument('--offline-only',action='store_true')
    args=ap.parse_args();base=claim_run(args.run)
    tools=base/'tools';tools.mkdir()
    for name in ('tt10_01_diagnostic_pc.py','tt10_01_numeric.py'):
        shutil.copyfile(Path(__file__).with_name(name),tools/name)
    save(tools/'IDENTITY.json',{p.name:sha(p) for p in tools.iterdir() if p.is_file()})
    diag=args.reuse_diagnostics.resolve()
    if not diag.is_relative_to(OUT.resolve()) or diag==base.resolve():
        raise ValueError('Diagnostic input must be separate existing evidence under OUT')
    def check(name,value):
        row=dict(name=name,passed=bool(value));check.checks.append(row)
        save(base/('check-%02d.json'%len(check.checks)),row)
        assert value,name
    check.checks=[]
    gate=audit_diagnostics(diag,base,check)
    if args.offline_only:
        print(json.dumps(dict(status='PASS_OFFLINE_SOURCE04_REAUDIT',run=args.run,checks=len(check.checks))))
        return
    binary=WORK/'pc04/qwen35-a12';env=environment()
    cfg=config(binary,j(OUT/'pc-run-04/pc-config.json')['identity']['libraries'])
    check('source04_existing_config_identity',j(diag/'config.json')==cfg)
    save(base/'config.json',cfg);env['SP_TT10_CONFIG']=str(base/'config.json')
    worker,ready=launch(binary,base/'worker',env)
    binding=ready['prefix_cache']['binding_sha256']
    try:
        libs={}
        for line in (Path('/proc')/str(worker.process.pid)/'maps').read_text().splitlines():
            if '/' not in line:continue
            p=Path(line[line.index('/'):]);name=p.name.split('.so.')[0]+'.so' if '.so.' in p.name else p.name
            if name.startswith(('libllama.','libggml','libsp_linear')):libs[name]=sha(p)
        save(base/'loaded-libraries.json',libs)
        check('actual_loaded_libraries_match_config',libs==cfg['identity']['libraries'])
        def raw(req):
            folder=base/req['id'];folder.mkdir();save(folder/'request.json',req);worker.send(req);events=[]
            while True:
                r=worker.get(300)
                if r['type']=='token':events.append(r);continue
                break
            save(folder/'result.json',r);save(folder/'token-events.json',events)
            assert r['id']==req['id'] and r['status']=='OK'
            assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
            return r
        warm=j(diag/'warm_70/request.json')
        for key in ('diagnostic_dir','dump_state','diagnostic_all_layers'):warm.pop(key,None)
        warm.update(id=args.run+'-warm',logits_mode='final',cache_binding_sha256=binding)
        w=raw(warm);check('new_worker_neutral_prefix_created',w['type']=='cache_created')
        item=j(FROZEN/'WORKLOADS.json')['real_inputs'][0];pairs=[]
        template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text(encoding='utf-8')
        for mode in ('R0','hit'):
            req={k:v for k,v in item.items() if k!='prefix_audit'}
            req.update(id=args.run+'-app-'+mode,max_tokens=24,profile=False,state_fingerprint=True)
            if mode=='hit':req.update(cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding)
            folder=base/req['id'];folder.mkdir();save(folder/'request.json',req)
            result,events,begin,end,clock=measure(worker,lambda:worker.get(300),template,req)
            save(folder/'result.json',result);save(folder/'token-events.json',events)
            save(folder/'application-timing.json',clock);pairs.append((result,clock))
        comparison=same_result(pairs[0][0],pairs[1][0]);save(base/'APPLICATION_COMPARISON.json',comparison)
        check('source04_ordinary_application_numeric_equal',comparison['equal'])
        check('source04_ordinary_application_MODEL_EOS_quality',all(c['answer_source']=='MODEL' and c['eos'] and c['candidate_check']['status']==c['final_check']['status']=='pass' for _,c in pairs))
        check('source04_ordinary_answer_checks_equal',all(pairs[0][1][k]==pairs[1][1][k] for k in ('answer_source','candidate_check','final_check','eos')))
        cache0=pairs[0][0]['prefix_cache_request'];cache1=pairs[1][0]['prefix_cache_request']
        check('source04_ordinary_exact_hit_less_prefill',not cache0['hit'] and cache0['new_tokens']==len(item['tokens']) and cache1['hit'] and cache1['reused_tokens']==70 and cache1['new_tokens']==len(item['tokens'])-70)
        zero=dict(id=args.run+'-zero-R0',op='generate',tokens=item['tokens'][:70],max_tokens=2,profile=False,logits_mode='final',state_fingerprint=True,cache_policy='R0')
        z0=raw(zero);z1=raw(dict(zero,id=args.run+'-zero-hit',cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding))
        save(base/'ZERO_SUFFIX_COMPARISON.json',same_result(z0,z1))
        check('source04_zero_suffix_saved_logits_and_state_equal',same_result(z0,z1)['equal'] and z1['prefix_cache_request']['new_tokens']==0 and z1['prefix_cache_request']['reused_tokens']==70)
        check('source04_normal_worker_exit',worker.close(15))
        report=dict(status='PASS_SOURCE04_DIAGNOSTIC_IO_AND_CHUNK8_NUMERICAL',checks=check.checks,count=len(check.checks),run_directory=args.run,
            diagnostic_input=str(diag),native_sha256=sha(binary),full_streams=gate['projection_streams'],full_logits=gate['full_logit_vectors'],ordinary_application_pairs=1,
            ordinary_input_id=item['id'],ordinary_timings=[dict(mode=mode,TTFT_app_ms=c['TTFT_app_ms'],complete_app_ms=c['complete_app_ms'],answer_source=c['answer_source'],eos=c['eos'],cache=r['prefix_cache_request']) for mode,(r,c) in zip(('R0','hit'),pairs)],
            zero_suffix_pairs=1,source03_model_rerun=False,source03_89_checks_reassigned=False,BOARD='NOT_TESTED',TTFT_board_s=None,TT10_01_complete=False,
            limitation='PC only; one ordinary application pair. DONTNEED advice does not prove board CMA recovery; board scene untouched. Historical V07/V08 quality rejections remain.')
        save(base/'PC_DIAGNOSTIC_04.json',report)
        if not (OUT/'PC_DIAGNOSTIC_04.json').exists():save(OUT/'PC_DIAGNOSTIC_04.json',report)
        print(json.dumps(dict(status='PASS_PC_DIAGNOSTIC04',run=args.run,checks=len(check.checks))))
    finally:
        if not worker.closed:worker.close(30)


if __name__=='__main__':main()
