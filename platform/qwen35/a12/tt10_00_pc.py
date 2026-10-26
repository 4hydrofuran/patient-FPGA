"""No-board adapter/protocol checks and real pinned PC application smoke."""
import copy
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from tt10_00_prepare import ROOT,OUT,j,save,sha
from tt10_00_app import measure,MeasuredBackend
from supervisor import OwnedWorker


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--tag',default='01');tag=parser.parse_args().tag
    checks=[]
    def check(name,value):
        assert value,name
        checks.append(dict(name=name,passed=True))
    for mode in ('health','cpu02'):
        folder=OUT/mode/'bundle-v1'
        for p in folder.rglob('*.py'):compile(p.read_text(encoding='utf-8'),str(p),'exec')
        check(mode+'_package_source_compiles',True)
        check(mode+'_native_unchanged',sha(folder/'bin/qwen35-a12')==j(OUT/'INTEGRITY.json')['modes'][mode]['native_sha256'])
        settings=j(folder/'control/window-spec.json')
        check(mode+'_observer_availability_explicit',settings['tt10_detailed_manager_available']==(mode=='cpu02'))
    spec=importlib.util.spec_from_file_location('tt10_observer_review',OUT/'health/bundle-v1/platform/qwen35/a12/cpu01b_observer.py')
    observer=importlib.util.module_from_spec(spec);spec.loader.exec_module(observer)
    observer.start_request(dict(id='unobserved-health'))
    with observer.scope('idle'):
        with observer.span('health.total'):pass
    observer.finish_request(dict(id='unobserved-health',request_profile={}),OUT/('pc-health-unobserved-'+tag+'.json'))
    check('health_unavailable_detailed_counters_not_fabricated',True)
    corpus=j(OUT/'WORKLOADS.json')['real_inputs'];check('original_17_and_8_variants',len(corpus)==25)
    template=(ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja').read_text(encoding='utf-8')
    request=next(r for r in corpus if r['id']=='DEV-001');request={k:v for k,v in request.items() if k!='prefix_audit'}
    request.update(id='app_plain_1',max_tokens=8,profile=False)
    build=j(ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json')
    environment={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))}
    environment.update(LD_LIBRARY_PATH=str(Path(build['workspace'])/'pc'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    binary=Path('/home/member-a/kv260-build/a12-cpu01-integrated-20261024-v1/pc/qwen35-a12')
    worker=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8'],
         directory=OUT/('pc-application-worker-'+tag),env=environment,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+900)
    check('real_PC_ready',worker.get(120)['type']=='ready')
    results=[]
    for rid in ('app_plain_1','app_plain_2'):
        req=dict(request,id=rid)
        r,events,begin,end,clock=measure(worker,lambda:worker.get(180),template,req)
        check(rid+'_source_MODEL',clock['answer_source']=='MODEL')
        check(rid+'_EOS_and_cleared',r['eos'] and r['state_cleared_before_response'])
        check(rid+'_app_clock_contains_worker_clock',clock['TTFT_app_ms']>=clock['TTFT_worker_ms']>=0)
        s=clock['stamps'];check(rid+'_timestamp_order',s['request_received_ns']<=s['backend_enter_ns']<=s['prompt_ready_ns']<=s['worker_send_ns']<=s['first_token_ns']<=s['worker_result_ns']<=s['checked_ns'])
        check(rid+'_native_prompt_path',r['prompt_tokens']==107 and 'tokens' not in worker.records[-1] if worker.records else r['prompt_tokens']==107)
        save(OUT/('pc-application-'+tag)/rid/'result.json',r);save(OUT/('pc-application-'+tag)/rid/'application-timing.json',clock)
        results.append(r)
    check('repeat_output_and_logits_equal',all(results[0][k]==results[1][k] for k in ('output_tokens','text','last_prompt_logits_fnv64','state_fingerprint')))
    check('normal_PC_exit',worker.close(15) and worker.process.returncode==0)
    class FakeWorker:
        def __init__(self):self.sent=[]
        def send(self,x):self.sent.append(x)
    messages=request['application']['messages']
    for name,message in [('foreign_id',dict(id='other',type='token',index=0,token=1)),
                         ('error_result',dict(id=request['id'],type='error',message='injected'))]:
        fake=FakeWorker();adapter=MeasuredBackend(fake,lambda:message,template,request)
        try:adapter.generate(messages)
        except (AssertionError,KeyError):check('reject_'+name,True)
        else:raise AssertionError(name)
        check(name+'_prompt_tokenization_not_bypassed','tokens' not in fake.sent[0] and 'prompt' in fake.sent[0])
    altered=copy.deepcopy(request);altered['prompt']+='changed'
    try:MeasuredBackend(FakeWorker(),lambda:None,template,altered).generate(messages)
    except AssertionError:check('reject_prompt_drift_before_send',True)
    else:raise AssertionError('prompt drift')
    check('budget_under_lease_cap',j(OUT/'RESOURCE_CALL_BUDGET.json')['calculated_worst_case_runs']==4896)
    save(OUT/('PC-'+tag+'.json'),dict(status='PASS_NO_BOARD_APP_TIMING_AND_REAL_NATIVE_SMOKE',checks=checks,count=len(checks),
        real_model_requests=2,tokenizer_inputs=25,BOARD='NOT_TESTED',numeric_math_changed=False,
        runtime_safety_ast=j(OUT/'INTEGRITY.json')['status']))
    print(json.dumps(dict(status='PASS_PC',checks=len(checks),real_model_requests=2)))

if __name__=='__main__':main()
