"""Replay the final stricter offline reader over preserved real PC/BOARD outputs."""
import copy
import json
from pathlib import Path
from cpu01_profile import audit_profile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


if __name__=='__main__':
    files=[OUT/'pc-model'/mode/'result.json' for mode in ('old','new_on')]
    prior=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
    files += [prior/mode/'readback-v1/run-v1'/side/name/'result.json' for mode in ('off','on') for side in ('s1','s2') for name in ('short_profile','natural_profile')]
    for p in files:audit_profile(json.loads(p.read_text(encoding='utf-8'))['request_profile'])
    profile=json.loads((OUT/'pc-model/new_on/result.json').read_text(encoding='utf-8'))['request_profile']
    rejected=[]
    for name in ('parent_invalid','node_invalid','aggregate_count','category_sum','unknown_schema','native_nesting'):
        bad=copy.deepcopy(profile)
        if name=='parent_invalid':bad['accounting_valid']=False
        if name=='node_invalid':bad['node_profile']['accounting_valid']=False
        if name=='aggregate_count':bad['node_profile']['phases']['prefill']['aggregates'][0]['timed_groups']+=1
        if name=='category_sum':bad['node_profile']['phases']['prefill']['total']['wall_us']+=1
        if name=='unknown_schema':bad['node_profile']['schema']='UNKNOWN'
        if name=='native_nesting':bad['phases']['prefill']['linear_service_wall_ms']+=1
        try:audit_profile(bad)
        except AssertionError:rejected.append(name)
        else:raise AssertionError(name+' accepted')
    data=dict(status='PASS_FINAL_READER_PC_AND_PRIOR_BOARD_REPLAY',actual_profiles=len(files),rejected=rejected,
        board_package_reader='Initial subset already frozen in bundle. Final offline reader additionally verifies all native/PL nesting equations without mutating the deployed package.')
    with (OUT/'READER_CHECK.json').open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2);stream.write('\n')
    print(json.dumps(data))
