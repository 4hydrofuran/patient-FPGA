"""Real pinned native PC comparisons and clock/accounting validity; never BOARD evidence."""
import json,os,time
from pathlib import Path
from common import ROOT,sha,save
from step10_common import OUT
from supervisor import OwnedWorker
from test_graph import one

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    # The PC part is already built before the ARM portion of the same queue job.
    submit=j(OUT/'build_submit_01.json')['stdout'].strip()
    work=Path('/home/member-a/kv260-build/ra02-coordinator/work')/submit
    binary=work/'pc/qwen35-a12'
    old=Path(j(ROOT/'evidence/model_pl_A/20261023-step07-single-v1/BUILD.json')['pc'])
    dest=OUT/'pc-native';dest.mkdir()
    previous=one(old,dest/'previous',None)
    current=one(binary,dest/'current',None)
    routed=one(binary,dest/'math_double','all')
    for row in (current,routed):assert row['logits']==previous['logits'] and row['state']==previous['state']
    dropped=one(binary,dest/'discarded_y','l0_gate',fault=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))}
    args=[str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    w=OwnedWorker(args,directory=OUT/'pc-profile',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+180)
    assert w.get(90)['type']=='ready';results=[]
    req=dict(op='generate',tokens=list(range(1,10)),teacher_tokens=[10,11,12,13],max_tokens=4,prefill_chunk=256,
             logits_mode='final',state_fingerprint=True)
    for enabled in (False,True):
        w.send(dict(req,id='profile_'+str(enabled),profile=enabled))
        while True:
            r=w.get(90)
            if r['type'] in ('result','error'):break
        assert r['type']=='result' and r['status']=='OK',r
        results.append(r)
    assert w.close(timeout=15)
    a,b=results
    for key in ('output_tokens','text','eos','state_fingerprint','last_prompt_logits_fnv64'):assert a[key]==b[key],key
    prof=b['request_profile'];assert prof['accounting_valid']
    for phase in ('prefill','decode'):
        buckets=prof['node_profile']['phases'][phase]
        total=sum(v['wall_ms'] for v in buckets.values())
        graph=prof['phases'][phase]['cpu_graph_wall_ms']
        assert 0<total<=graph
        assert buckets['mlp_custom']['calls']==prof['phases'][phase]['mlp_calls']
    save(OUT/'PC_NATIVE.json',dict(status='PASS_PC_UNCHANGED_RAW_LOGITS_STATE_AND_PROFILE_CLOCKS',
         graph=[previous,current,routed,dropped],profile_results=results,binary_sha256=sha(binary),
         public_contract_sha256=sha(ROOT/'contracts/qwen35/sp_linear_v1.h'),BOARD='NOT_TESTED'))
    print('PASS_PC_NATIVE_PROFILE_AND_MATH')
