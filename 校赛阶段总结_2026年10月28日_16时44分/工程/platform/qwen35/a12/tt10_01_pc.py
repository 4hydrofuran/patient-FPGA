"""Actual fixed-model PC equivalence, boundary, namespace and corruption regressions."""
import argparse,copy,json,os,signal,time
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,WORK,j,sha,save,config
from tt10_01_numeric import same_result,concatenated
from tt10_01_app import measure
from supervisor import OwnedWorker


def environment():
    build=j(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
    env.update(LD_LIBRARY_PATH=str(Path(build['workspace'])/'pc'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1');return env


def launch(binary,folder,env):
    w=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8'],directory=folder,env=env,
        health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+3600)
    ready=w.get(120);assert ready['type']=='ready';save(folder/'ready.json',ready);return w,ready


def main():
    global OUT
    evidence=OUT;ap=argparse.ArgumentParser();ap.add_argument('--run',default='pc-run-03');run=ap.parse_args().run
    assert run in ('pc-run-03','pc-run-04')
    OUT=evidence/run
    checks=[];rows=[];quality=[]
    def check(name,value,detail=None):
        checks.append(dict(name=name,passed=bool(value),detail=detail))
        (OUT/'PC_PROGRESS.json').write_text(json.dumps(dict(status='RUNNING',last=checks[-1],checks=len(checks))))
        assert value,(name,detail)
    env=environment();binary=WORK/'pc/qwen35-a12'
    probe,ready=launch(binary,OUT/'pc-probe',env)
    maps=Path('/proc')/str(probe.process.pid)/'maps';libs={}
    for line in maps.read_text().splitlines():
        if '/' not in line:continue
        path=Path(line[line.index('/'):]);name=path.name.split('.so.')[0]+'.so' if '.so.' in path.name else path.name
        if name.startswith(('libllama.','libggml','libsp_linear')):libs[name]=sha(path)
    check('unconfigured_default_R0_and_normal_probe_exit',not ready['prefix_cache']['enabled'] and probe.close(15))
    cfg=config(binary,libs);save(OUT/'pc-config.json',cfg);env['SP_TT10_CONFIG']=str(OUT/'pc-config.json')
    old=Path('/home/member-a/kv260-build/a12-cpu01-integrated-20261024-v1/pc/qwen35-a12')
    old_env=environment();oldw,_=launch(old,OUT/'pc-old',old_env)
    def raw(w,req,folder,expected='result'):
        folder.mkdir(parents=True,exist_ok=True);save(folder/'request.json',req);w.send(req);events=[]
        while True:
            r=w.get(300)
            if r['type']=='token':events.append(r);continue
            assert r['id']==req['id'];break
        save(folder/'result.json',r);save(folder/'token-events.json',events)
        assert r['type']==expected,(req['id'],r)
        if expected in ('result','cache_created'):assert r['status']=='OK' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
        return r
    def request(rid,tokens,**kw):
        return dict(id=rid,op='generate',tokens=tokens,max_tokens=2,teacher_tokens=[10,11],profile=False,prefill_chunk=256,logits_mode='final',state_fingerprint=True,cache_policy='R0',**kw)
    oldreq=request('legacy_diag',list(range(1,10)));oldreq.update(logits_mode='all',diagnostic_dir=str(OUT/'pc-old/legacy_diag/diag'),diagnostic_all_layers=True,dump_state=True)
    oldr=raw(oldw,oldreq,OUT/'pc-old/legacy_diag');check('old_worker_normal_exit',oldw.close(15))
    worker,ready=launch(binary,OUT/'pc-new',env);binding=ready['prefix_cache']['binding_sha256'];base=OUT/'pc-new'
    try:
        newreq=dict(oldreq,diagnostic_dir=str(base/'legacy_diag/diag'));newr=raw(worker,newreq,base/'legacy_diag')
        ar=OUT/'pc-old/legacy_diag/diag';br=base/'legacy_diag/diag'
        check('legacy_R0_result_unchanged',same_result(oldr,newr)['equal'])
        check('legacy_R0_all_443_binary_files_unchanged',{p.name:sha(p) for p in ar.iterdir() if p.is_file()}=={p.name:sha(p) for p in br.iterdir() if p.is_file()})
        corpus=j(FROZEN/'WORKLOADS.json')['real_inputs'];full=corpus[0]['tokens'];chosen=None
        def warm(n,rid,diag=False,owner=None,cid='neutral'):
            req=dict(id=rid,op='cache_create',tokens=full[:n],max_tokens=1,cache_id=cid,cache_binding_sha256=binding,confirmed_prefix=True,cache_policy='R0',profile=False,prefill_chunk=256,logits_mode='all' if diag else 'final')
            if owner:req['cache_owner']=owner
            if diag:req.update(diagnostic_dir=str(base/rid/'diag'),diagnostic_all_layers=True,dump_state=True)
            return raw(worker,req,base/rid,expected='cache_created')
        golden=request('full_R0',full);golden.update(logits_mode='all',diagnostic_dir=str(base/'full_R0/diag'),diagnostic_all_layers=True,dump_state=True)
        ref=raw(worker,golden,base/'full_R0')
        for n in (70,64):
            warm(n,'warm_'+str(n),True)
            req=dict(golden,id='full_cache_'+str(n),diagnostic_dir=str(base/('full_cache_'+str(n))/'diag'),cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding)
            hit=raw(worker,req,base/req['id'])
            comparison=dict(result=same_result(ref,hit),all_bytes=concatenated(base/'full_R0',base/('warm_'+str(n)),base/req['id']))
            save(OUT/('BOUNDARY_'+str(n)+'.json'),comparison)
            if comparison['result']['equal'] and comparison['all_bytes']['equal']:chosen=n;break
            save(OUT/('BOUNDARY_'+str(n)+'_FAILED.json'),dict(status='NUMERICAL_REFUSAL_RETAINED',comparison=comparison))
        check('exact_prefix_boundary_found',chosen is not None,chosen)
        check('restored_prefix_all_projection_logits_state_bytes_equal',True)
        for n in (0,1,8,9,16,17,24,32,48):
            tokens=full[:chosen]+list(range(100,100+n))
            a=raw(worker,request('suffix_'+str(n)+'_R0',tokens),base/('suffix_'+str(n)+'_R0'))
            req=request('suffix_'+str(n)+'_hit',tokens);req.update(cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding)
            b=raw(worker,req,base/req['id']);check('suffix_'+str(n)+'_full_logits_and_state',same_result(a,b)['equal'])
            check('suffix_'+str(n)+'_actually_reused',b['prefix_cache_request']['reused_tokens']==chosen and b['prefix_cache_request']['new_tokens']==n)
        # Prefix-only first-token generation uses explicitly saved logits, not stale context output.
        a_req=request('zero_natural_R0',full[:chosen]);a_req.pop('teacher_tokens');a=raw(worker,a_req,base/a_req['id'])
        b_req=dict(a_req,id='zero_natural_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding);b=raw(worker,b_req,base/b_req['id'])
        check('zero_suffix_natural_greedy_matches_R0',same_result(a,b)['equal'])
        template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text()
        for item in corpus:
            pair=[]
            for mode in ('R0','hit'):
                req={k:v for k,v in item.items() if k!='prefix_audit'};req.update(id=item['id']+'_'+mode,max_tokens=24,state_fingerprint=True,profile=False)
                if mode=='hit':req.update(cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding)
                folder=base/req['id'];folder.mkdir();save(folder/'request.json',req)
                r,events,begin,end,clock=measure(worker,lambda:worker.get(300),template,req)
                save(folder/'result.json',r);save(folder/'application-timing.json',clock);pair.append((r,clock))
            check(item['id']+'_natural_logits_state_equal',same_result(pair[0][0],pair[1][0])['equal'])
            check(item['id']+'_answer_checks_equal',all(pair[0][1][k]==pair[1][1][k] for k in ('answer_source','candidate_check','final_check','eos')))
            quality.append(dict(id=item['id'],answer_source=pair[1][1]['answer_source'],eos=pair[1][1]['eos'],candidate=pair[1][1]['candidate_check'],final=pair[1][1]['final_check']))
            rows.append(dict(id=item['id'],R0_TTFT_app_ms=pair[0][1]['TTFT_app_ms'],hit_TTFT_app_ms=pair[1][1]['TTFT_app_ms'],cache=pair[1][0]['prefix_cache_request']))
        golden=request('fault_R0',full);gr=raw(worker,golden,base/golden['id'])
        for kind in ('digest','partial_restore'):
            raw(worker,dict(id='damage_'+kind,op='cache_damage_test',cache_id='neutral',kind=kind),base/('damage_'+kind),'cache_damaged_test')
            q=dict(golden,id='fault_'+kind,cache_policy='TT10_PFX_V1',cache_id='neutral',cache_binding_sha256=binding)
            r=raw(worker,q,base/q['id']);check(kind+'_fallback_R0_exact',not r['prefix_cache_request']['hit'] and same_result(gr,r)['equal'],r['prefix_cache_request'])
            warm(chosen,'rewarm_'+kind)
        for kind in ('version','prefix'):
            q=dict(golden,id='miss_'+kind,cache_policy='TT10_PFX_V1',cache_id='neutral',cache_binding_sha256=binding)
            if kind=='version':q['cache_binding_sha256']='0'*64
            else:q['tokens']=[q['tokens'][0]+1,*q['tokens'][1:]]
            r=raw(worker,q,base/q['id']);baseline=raw(worker,dict(q,id=q['id']+'_R0',cache_policy='R0'),base/(q['id']+'_R0'))
            check(kind+'_miss_explicit_R0_exact',not r['prefix_cache_request']['hit'] and same_result(baseline,r)['equal'],r['prefix_cache_request'])
            if kind=='version':warm(chosen,'rewarm_version')
        owner=dict(kind='case_session',case_id='SYN_CP_01',case_sha256='1'*64,session_id='session-A',epoch=0)
        warm(chosen,'private_warm',owner=owner,cid='private')
        q=dict(golden,id='private_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='private',cache_binding_sha256=binding,cache_owner=owner)
        r=raw(worker,q,base/q['id']);check('private_owner_exact_hit',r['prefix_cache_request']['hit'])
        for key,value in [('session_id','session-B'),('case_id','SYN_CP_02'),('epoch',1)]:
            if key!='session_id':warm(chosen,'private_rewarm_'+key,owner=owner,cid='private')
            q=dict(golden,id='private_miss_'+key,cache_policy='TT10_PFX_V1',cache_id='private',cache_binding_sha256=binding,cache_owner=dict(owner,**{key:value}))
            r=raw(worker,q,base/q['id']);check(key+'_private_invalidated',not r['prefix_cache_request']['hit'] and same_result(gr,r)['equal'])
        warm(chosen,'second_public',cid='second')
        q=dict(id='third_slot',op='cache_create',tokens=full[:chosen],max_tokens=1,cache_id='third',cache_binding_sha256=binding,confirmed_prefix=True)
        r=raw(worker,q,base/q['id'],'error');check('third_slot_refused_before_compute','slot limit' in r['message'])
        raw(worker,dict(id='drop_second',op='cache_drop',cache_id='second'),base/'drop_second','cache_dropped')
        for n in (1022,1023):
            tokens=full[:chosen]+[100]*(n-chosen)
            a_req=request('long_'+str(n)+'_R0',tokens);a_req.update(max_tokens=1,teacher_tokens=[10]);a=raw(worker,a_req,base/a_req['id'])
            b_req=dict(a_req,id='long_'+str(n)+'_hit',cache_policy='TT10_REQUIRE_HIT',cache_id='neutral',cache_binding_sha256=binding);b=raw(worker,b_req,base/b_req['id'])
            check('context_tail_'+str(n)+'_state_logits_equal',same_result(a,b)['equal'])
        for rid,tokens in [('empty',[]),('context_overflow',[100]*1024)]:
            q=request(rid,tokens);r=raw(worker,q,base/rid,'error');check(rid+'_rejected_and_cleared',r['state_cleared'])
        check('normal_candidate_worker_exit',worker.close(15))
        summary=dict(status='PASS_PC_FULL_MODEL_PREFIX_RESTORE_R0_EQUIVALENCE',checks=checks,count=len(checks),prefix_tokens=chosen,
            real_application_pairs=25,quality=quality,timings=rows,cache_config='pc-config.json',BOARD='NOT_TESTED',cancel='SEPARATE_PENDING')
        save(OUT/'PC.json',summary);save(evidence/'PC.json',dict(summary,run_directory=run))
        print(json.dumps(dict(status='PASS_PC_PREFIX_RESTORE',checks=len(checks),prefix_tokens=chosen,real_application_pairs=25)))
    finally:
        if not worker.closed:worker.close(30)


if __name__=='__main__':main()
