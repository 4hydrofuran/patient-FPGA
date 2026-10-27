"""Derived bounds only; never qualifies board memory from a PC calculation."""
import json
from common import ROOT, EVIDENCE, save


def budget(entries, scope, prompt=128, output=2, requests=1):
    chosen=[e for e in entries if scope=='all' or (e['layer']==0 and (scope=='l0' or scope=='l0_'+e['op']))]
    align=lambda n:(n+8191)//8192*8192
    io=sum(map(align,(8*4864,8*4,8*4864*4,64)))
    rows=[]
    for e in chosen:
        files=e['files']; w=files['w.bin']['bytes']; s=files['sw.bin']['bytes']
        rows.append(dict(id=e['id'],logical_bytes=w+s,bo_charge_bytes=align(w)+align(s)))
    # upper bound includes all graph nodes; actual legitimate last-layer pruning is traced.
    calls=len(chosen)*((prompt+7)//8+output-1)*requests
    return dict(scope=scope,prompt_token_limit=prompt,output_token_limit=output,
                request_limit=requests,physical_ubatch=8,weight_load_limit=len(chosen),
                max_successful_runs=calls,io_bo_charge_bytes=io,
                weights=rows,explicit_bo_limit_bytes=io+sum(r['bo_charge_bytes'] for r in rows),
                logical_weight_bytes=sum(r['logical_bytes'] for r in rows),
                allocation_count=4+2*len(chosen),max_session_seconds=120,
                measured_board_physical_peak_bytes=None,board_qualified=False)


if __name__=='__main__':
    entries=json.loads((ROOT/'models/sidecar_A/qwen35-v1/manifest.json').read_text())['entries']
    save(EVIDENCE/'RESOURCE_CALL_BUDGET.json',dict(status='DERIVED_NOT_MEASURED',
        profiles=[budget(entries,s) for s in ('l0_gate','l0','all')],
        full_graph_cpu_weights_bytes=140378112,
        accounts=dict(GGUF_non_target_pages='measure RSS/PSS incl startup repack peak',
                      sidecar_host='CPU remainder owns packed copies; PL selected temporaries released after load',
                      weight_BO='charged incl 8192 alignment; mapped pages overlap PSS/CMA',
                      XRT_implicit=None,graph_workspace=None,hybrid_state=None,output_head=None,
                      physical_peak=None),
        health=dict(stop_temperature_mC=55000,min_MemAvailable_kib=1048576,min_CmaFree_kib=32768),
        policy='separate PSS/RSS, explicit BO and CMA accounts; never add overlapping physical accounts',
        deployment='DENIED_UNTIL_FRESH_BOARD_BASELINE_AND_LOAD_PEAK_VALIDATED',
        failure_policy='stop new submissions; timeout or unknown completion retains ownership, no kill/unload'))
    print('DERIVED_NOT_MEASURED: budgets saved; no board allocation authorized by this file')
