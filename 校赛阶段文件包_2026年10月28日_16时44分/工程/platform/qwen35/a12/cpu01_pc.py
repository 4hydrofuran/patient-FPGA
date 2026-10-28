"""Real Linux full-model old/new equivalence and V2/management-reader regression."""
import copy
import json
import os
from pathlib import Path
import time
from common import ROOT, save, sha
from supervisor import OwnedWorker
from cpu01_profile import audit_profile
from cpu01_numeric import compare_cases

OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'
WORK=Path('/home/member-a/kv260-build/a12-cpu01-integrated-20261024-v1')


def one(binary, folder, profile):
    env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))}
    if binary.parent==WORK/'pc':
        base=Path(json.loads((ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json').read_text(encoding='utf-8'))['workspace'])
        env['LD_LIBRARY_PATH']=str(base/'pc')
    worker=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8'],directory=folder,env=env,health=lambda:None,max_runs=1,max_loads=1,expires=time.monotonic()+240)
    assert worker.get(90)['type']=='ready'
    request=dict(id='diag_exact',op='generate',tokens=list(range(1,10)),teacher_tokens=[10,11],max_tokens=2,prefill_chunk=256,logits_mode='all',diagnostic_dir=str(folder/'diag'),diagnostic_all_layers=True,dump_state=True,state_fingerprint=True,profile=profile,profile_detail=profile)
    worker.send(request)
    while True:
        result=worker.get(120)
        if result['type'] in ('result','error'):break
    save(folder/'result.json',result)
    assert result['type']=='result' and result['status']=='OK', result
    assert worker.close(timeout=15)
    if profile: audit_profile(result['request_profile'])
    return result


def main():
    base=Path(json.loads((ROOT/'evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json').read_text(encoding='utf-8'))['pc'])
    results={}
    for name,binary,enabled in [('old',base,True),('new_off',WORK/'pc/qwen35-a12',False),('new_on',WORK/'pc/qwen35-a12',True)]:
        results[name]=one(binary,OUT/'pc-model'/name,enabled)
    comparisons={n:compare_cases(OUT/'pc-model/old',OUT/'pc-model'/n) for n in ('new_off','new_on')}
    profile=results['new_on']['request_profile']
    checked=0
    for mutation in ('parent_invalid','node_invalid','sum_invalid','unknown_schema'):
        value=copy.deepcopy(profile)
        if mutation=='parent_invalid':value['accounting_valid']=False
        if mutation=='node_invalid':value['node_profile']['accounting_valid']=False
        if mutation=='sum_invalid':value['node_profile']['phases']['prefill']['total']['wall_us']+=1
        if mutation=='unknown_schema':value['node_profile']['schema']='UNRECOGNIZED'
        try:audit_profile(value)
        except AssertionError:checked+=1
        else:raise AssertionError('reader accepted '+mutation)
    for phase in ('prefill','decode'):
        rows=profile['node_profile']['phases'][phase]['aggregates']
        assert any(r['role']=='output_head' and r['weight']=='token_embd.weight' for r in rows)
    save(OUT/'PC_MODEL.json',dict(status='PASS_PC_OLD_NEW_LOGITS_PROJECTIONS_HYBRID_STATE_BIT_EXACT',comparisons=comparisons,reader_rejections=checked,new_binary_sha256=sha(WORK/'pc/qwen35-a12'),BOARD='NOT_TESTED'))
    print('PASS_PC_FULL_MODEL_AND_EXPLICIT_V1_V2_READER')


if __name__=='__main__':main()
