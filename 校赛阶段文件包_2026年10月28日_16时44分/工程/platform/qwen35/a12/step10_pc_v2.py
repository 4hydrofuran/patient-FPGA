"""Recheck corrected clocks against preserved actual v1 outputs and native on/off results."""
import json,os,time
from pathlib import Path
from common import ROOT,sha,save
from step10_common import OUT
from supervisor import OwnedWorker

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    # v1 completed all four raw graph/consumer runs before its timing-category assertion.
    graph=OUT/'pc-native';ref=graph/'previous/diag'
    for name in ('current','math_double'):
        actual=graph/name/'diag'
        for p in ref.glob('logits-*.f32'):assert p.read_bytes()==(actual/p.name).read_bytes()
        assert (ref/'hybrid-state.bin').read_bytes()==(actual/'hybrid-state.bin').read_bytes()
    assert 'different or stale Y' in j(graph/'discarded_y/result.json')['message']
    binary=Path(j(OUT/'BUILD-v2.json')['pc'])
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))}
    args=[str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
    w=OwnedWorker(args,directory=OUT/'pc-profile-v2',env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+180)
    assert w.get(90)['type']=='ready';results=[]
    req=dict(op='generate',tokens=list(range(1,10)),teacher_tokens=[10,11,12,13],max_tokens=4,prefill_chunk=256,logits_mode='final',state_fingerprint=True)
    prior=[json.loads(s) for s in (OUT/'pc-profile/stdout.jsonl').read_text().splitlines() if json.loads(s).get('type')=='result']
    assert len(prior)==2
    for enabled in (False,True):
        w.send(dict(req,id='profile_'+str(enabled),profile=enabled))
        while True:
            r=w.get(90)
            if r['type'] in ('result','error'):break
        assert r['type']=='result' and r['status']=='OK';results.append(r)
    assert w.close(timeout=15)
    for r in results+prior:
        for key in ('output_tokens','text','eos','state_fingerprint','last_prompt_logits_fnv64'):assert r[key]==results[0][key],key
    prof=results[1]['request_profile'];assert prof['accounting_valid']
    for phase in ('prefill','decode'):
        buckets=prof['node_profile']['phases'][phase]
        assert 0<sum(v['wall_ms'] for v in buckets.values())<=prof['phases'][phase]['cpu_graph_wall_ms']
        assert buckets['mlp_custom']['calls']==prof['phases'][phase]['mlp_calls']
    save(OUT/'PC_NATIVE.json',dict(status='PASS_PC_UNCHANGED_RAW_LOGITS_STATE_AND_PROFILE_CLOCKS',
         prior_graph='pc-native',first_failed_receipt='pc_native_01.json',corrected_source='source-v2',
         profile_results=results,binary_sha256=sha(binary),BOARD='NOT_TESTED'))
    print('PASS_PC_CORRECTED_PROFILE_AND_MATH')
