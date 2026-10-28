"""Real pinned native PC graph/state/cancel checks and fail-closed app registry."""
import json,os,subprocess,sys,time
from pathlib import Path
from common import ROOT,sha,save,CONTRACT
from step09_common import OUT
from supervisor import OwnedWorker
from test_graph import one

def j(p):return json.loads(p.read_text(encoding='utf-8'))
def response(w,req):
    w.send(req)
    while True:
        r=w.get(120)
        if r['type'] in ('result','error','reset'):return r

if __name__=='__main__':
    binary=Path(j(ROOT/'evidence/model_pl_A/20261023-step07-single-v1/BUILD.json')['pc'])
    dest=OUT/'pc-graph';dest.mkdir();rows=[]
    baseline=one(binary,dest/'s1',None);rows.append(baseline)
    for t in (1,2,4,8):
        row=one(binary,dest/('T'+str(t)),'all',physical=t,chunk=t)
        assert row['logits']==baseline['logits'] and row['state']==baseline['state'];rows.append(row)
    rows.append(one(binary,dest/'discarded_y','l0_gate',fault=True))
    env=os.environ.copy();env.pop('SP_A12_CONFIG',None);env.pop('SP_A12_TEST_DROP_OUTPUT',None)
    args=[str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    w=OwnedWorker(args,directory=OUT/'pc-session',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+180)
    assert w.get(60)['type']=='ready';records=[]
    for req in j(OUT/'REQUESTS.json')['short']:
        if req.get('diagnostic'):continue
        req=dict(req);cancel=req.pop('cancel_test',False)
        if not cancel:r=response(w,req)
        else:
            w.send(req)
            while w.get(120)['type']!='token':pass
            w.cancel('PC native cancel after first token');assert w.close(timeout=15)
            r=[j for j in map(json.loads,(OUT/'pc-session/stdout.jsonl').read_text().splitlines()) if j.get('type')=='result' and j.get('id')==req['id']][0]
            assert r['status']=='CANCELLED' and not r['partial_output_usable'] and r['state_cleared_before_response']
        if req.get('cache_policy') in ('R1','R2'):assert r['type']=='error' and r['state_cleared']
        records.append(r)
    assert w.closed
    # Native startup negatives execute the real entry; no platform or device is opened.
    cfg=dict(contract_sha256=CONTRACT,fallback='disabled',fpga_required=True,scope='all',execution_kind='PC_MATH_DOUBLE',library='/missing/a12.so',library_sha256='0'*64,backend_config=str(ROOT/'modules/linear_A/cpu_config.json'),backend_config_sha256=sha(ROOT/'modules/linear_A/cpu_config.json'),trace_limit=4096)
    negatives=[]
    for name,changes in [('missing_library',{}),('wrong_contract',dict(contract_sha256='0'*64)),('forbidden_fallback',dict(fallback='cpu'))]:
        p=OUT/(name+'.json');save(p,dict(cfg,**changes));r=subprocess.run(args,input='',text=True,capture_output=True,env=dict(env,SP_A12_CONFIG=str(p)),timeout=90)
        save(OUT/(name+'-receipt.json'),dict(argv=args,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
        assert r.returncode==2 and 'S1_FAILURE:' in r.stderr and '"type":"ready"' not in r.stdout
        negatives.append(dict(case=name,exit_code=r.returncode))
    sys.path.insert(0,str(ROOT))
    from system_qwen35.app.default_e2e.policy import registry,HardwareUnavailable
    from system_qwen35.app.domain import load_case,Transcript
    from system_qwen35.app.planning import plan
    try:registry('fpga_required')
    except HardwareUnavailable:pass
    else:raise AssertionError('missing HW silently fell back')
    assert registry('cpu_same_math')['actual_backend']=='CPU_REFERENCE'
    policies=[]
    for row in j(ROOT/'eval/qwen35/a02/dev/questions-v2.json'):
        if row['expected_route']=='FACT':continue
        p=plan(load_case(row['case_id']),Transcript.parse(dict(request_id=row['id'],text=row['question'],source='typed',final=True)),[])
        if p.route in ('REFUSE','CLARIFY'):policies.append(dict(id=row['id'],route=p.route,model_calls=0))
    save(OUT/'PC_MATRIX.json',dict(status='PASS_PC_NATIVE_PARTITION_STATE_CANCEL_AND_FAIL_CLOSED',graph=rows,session=records,startup_negatives=negatives,policy=policies,board='NOT_TESTED',no_auto_fallback=True,binary_sha256=sha(binary)))
    print('PASS_PC_TASK09_NATIVE_GRAPH_STATE_CANCEL_FAIL_CLOSED')
