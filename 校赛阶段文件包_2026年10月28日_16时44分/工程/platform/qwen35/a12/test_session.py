"""Targeted actual PC native R0/reset/reuse/cancellation checks for the new route."""
import json
import os
from pathlib import Path
import time
from common import ROOT,EVIDENCE,sha,save
from supervisor import OwnedWorker


def start(name):
    build=Path(json.loads((EVIDENCE/'PC_BUILD-v4.json').read_text())['pc_build'])
    cfg=EVIDENCE/(name+'-route.json');cpu=ROOT/'modules/linear_A/cpu_config.json'
    save(cfg,dict(contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
        fallback='disabled',fpga_required=True,scope='all',execution_kind='PC_MATH_DOUBLE',
        library=str(build/'libsp_linear_cpu.so'),library_sha256=sha(build/'libsp_linear_cpu.so'),
        backend_config=str(cpu),backend_config_sha256=sha(cpu),trace_limit=4096))
    w=OwnedWorker([str(build/'qwen35-a12'),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),
        '4','256','all','TILED','4','8'],directory=EVIDENCE/name,
        env=dict(os.environ,SP_A12_CONFIG=str(cfg)),health=lambda:None,
        max_runs=65536,max_loads=72,expires=time.monotonic()+120)
    assert w.get(60)['type']=='ready';return w


def result(w,request):
    w.send(request)
    while True:
        r=w.get(60)
        if r['type'] in ('result','error','reset'):return r


if __name__=='__main__':
    w=start('session-v1');rows=[]
    try:
        req=dict(op='generate',id='A',tokens=[1,2,3,4,5,6,7,8,9],teacher_tokens=[10,11],
                 max_tokens=2,state_fingerprint=True)
        a=result(w,req);assert a['status']=='OK'
        reset=result(w,dict(op='reset',id='reset'));assert reset['type']=='reset'
        b=result(w,dict(req,id='B',tokens=[9,8,7,6,5,4,3,2,1]));assert b['status']=='OK'
        r1=result(w,dict(req,id='R1',cache_policy='R1'));assert r1['type']=='error'
        c=result(w,dict(req,id='A_again'));assert c['status']=='OK'
        assert a['last_prompt_logits_fnv64']==c['last_prompt_logits_fnv64'] and a['state_fingerprint']==c['state_fingerprint']
        assert all(r['state_cleared_before_response'] and r['state_position_after_clear']==-1 for r in (a,b,c))
        assert c['bridge']['a12_route']['weight_load_count']==72
        rows=[a,reset,b,r1,c]
    finally:assert w.close(timeout=10)
    save(EVIDENCE/'SESSION_REGRESSION.json',dict(status='PASS_PC_R0_RESET_CASE_SWITCH_REPLAY',records=rows,BOARD='NOT_TESTED'))
    w=start('cancel-native-v1')
    w.send(dict(op='generate',id='cancel',tokens=[1,2,3,4,5,6,7,8,9],max_tokens=64))
    while w.get(60)['type']!='token':pass
    w.cancel('PC native regression after first generated token')
    assert w.close(timeout=10)
    raw=[json.loads(s) for s in (EVIDENCE/'cancel-native-v1/stdout.jsonl').read_text().splitlines()]
    results=[r for r in raw if r.get('type')=='result']
    assert len(results)==1 and results[0]['status']=='CANCELLED' and results[0]['partial_output_usable'] is False
    assert results[0]['state_cleared_before_response'] and results[0]['state_position_after_clear']==-1
    save(EVIDENCE/'CANCEL_REGRESSION.json',dict(status='PASS_PC_REAL_NATIVE_CANCEL_NO_KILL',result=results[0],BOARD='NOT_TESTED'))
    print('PASS_PC_R0_RESET_CASE_SWITCH_REPLAY_AND_REAL_CANCEL')
