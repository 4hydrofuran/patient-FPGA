"""Real PC model graph comparisons; the selected route is explicitly a CPU math double."""
import argparse
import json
import os
from pathlib import Path
import time
from common import ROOT, sha, save
from supervisor import OwnedWorker


def one(binary, directory, scope, *, fault=False, physical=8, chunk=8):
    env=os.environ.copy();env.pop('SP_A12_CONFIG',None);env.pop('SP_A12_TEST_DROP_OUTPUT',None)
    if scope:
        config=directory.parent/(directory.name+'-route.json')
        cpu=ROOT/'modules/linear_A/cpu_config.json'
        lib=binary.parent/'libsp_linear_cpu.so'
        save(config,dict(contract_sha256='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6',
            fallback='disabled',fpga_required=True,scope=scope,execution_kind='PC_MATH_DOUBLE',
            library=str(lib),library_sha256=sha(lib),backend_config=str(cpu),backend_config_sha256=sha(cpu),trace_limit=4096))
        env['SP_A12_CONFIG']=str(config)
    if fault:env['SP_A12_TEST_DROP_OUTPUT']='1'
    worker=OwnedWorker([str(binary),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),
                       '4','256','all','TILED','4',str(physical)],directory=directory,env=env,
                       health=lambda:None,max_runs=4096,max_loads=72,expires=time.monotonic()+180)
    try:
        ready=worker.get(90)
        assert ready['type']=='ready',ready
        diagnostic=directory/'diag'
        req=dict(id='fixed',op='generate',tokens=[1,2,3,4,5,6,7,8,9],teacher_tokens=[10,11],
                 max_tokens=2,prefill_chunk=chunk,logits_mode='all',diagnostic_dir=str(diagnostic),
                 diagnostic_all_layers=True,diagnostic_report=True,a12_consumer_trace=bool(scope),
                 state_fingerprint=True,dump_state=True)
        worker.send(req)
        while True:
            r=worker.get(90)
            if r['type'] in ('result','error'):break
        save(directory/'result.json',r);save(directory/'ready.json',ready)
        if fault:
            assert r['type']=='error' and 'different or stale Y' in r['message'],r
            assert r['state_cleared'] is True
            return dict(scope=scope,counterfactual='DROPPED_GRAPH_Y_DETECTED',status='PASS_PC_REJECTION')
        assert r['type']=='result' and r['status']=='OK' and r['state_cleared_before_response'],r
        assert r['state_position_after_clear']==-1 and r['partial_output_usable'] is True
        trace=r['bridge'].get('a12_route',{}).get('a12_trace',[])
        if scope:
            assert trace and all(x['consumer_verified'] for x in trace)
            assert all(x['execution_kind']=='PC_MATH_DOUBLE' for x in trace)
            assert r['bridge']['a12_route']['a12_hardware_global_count'] is None
        return dict(scope=scope or 'CPU_ALL',status='PASS_PC_MODEL_MATH',trace_calls=len(trace),
                    trace_layers=sorted(set(x['layer'] for x in trace)),
                    logits={p.name:sha(p) for p in diagnostic.glob('logits-*.f32')},
                    state=sha(diagnostic/'hybrid-state.bin'),fingerprint=r.get('state_fingerprint'))
    finally:
        assert worker.close(timeout=10),'test worker did not exit normally; no kill was used'


def main(binary,out):
    out.mkdir(exist_ok=False,parents=True);rows=[]
    baseline=one(binary,out/'s1',None);rows.append(baseline)
    for scope in ('l0_gate','l0','all'):
        row=one(binary,out/scope,scope)
        assert row['logits']==baseline['logits'] and row['state']==baseline['state'],row
        rows.append(row)
    for physical in (1,2,4):
        row=one(binary,out/f'T{physical}','all',physical=physical,chunk=physical)
        # Logit file names are identical regardless of physical partition.
        assert row['logits']==baseline['logits'] and row['state']==baseline['state'],row
        rows.append(row)
    rows.append(one(binary,out/'counterfactual','l0_gate',fault=True))
    save(out/'SUMMARY.json',dict(status='PASS_PC_FULL_GRAPH_NOT_BOARD',runs=rows,
        same_math_logits_and_state='BIT_EXACT',BOARD='NOT_TESTED',
        operator_tolerance_unchanged=True,graph_tolerance_unchanged=True))
    print(json.dumps(dict(status='PASS_PC_FULL_GRAPH_NOT_BOARD',cases=len(rows))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();main(a.binary,a.out)
