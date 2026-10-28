"""Offline join of returned output, actual graph consumer, model input and diagnostics."""
import json
from common import EVIDENCE,sha,save


if __name__=='__main__':
    summary=json.loads((EVIDENCE/'graph-v2/SUMMARY.json').read_text());rows=[]
    for case in ('l0_gate','l0','all','T1','T2','T4'):
        folder=EVIDENCE/'graph-v2'/case
        result=json.loads((folder/'result.json').read_text())
        diag=json.loads((folder/'diag/manifest.json').read_text())
        projections=diag['projections']
        joined=[]
        for record in result['bridge']['a12_route']['a12_trace']:
            identifier=f"l{record['layer']:02}_{record['op']}"
            matches=[p for p in projections if p['id']==identifier and p['execution']==record['execution']]
            assert len(matches)==1,(case,identifier,record['execution'])
            p=matches[0];x=folder/'diag'/p['input'];y=folder/'diag'/p['output']
            assert record['consumer_verified'] and sha(y)==record['output_sha256']
            assert p['T']==record['T'] and p['N']==record['N']
            joined.append(dict(record,shape=dict(T=p['T'],N=p['N'],K=p['K']),
                input_strides=p['input_strides'],input_sha256=sha(x),
                graph_output_sha256=sha(y),actual_graph_op=p['op'],
                input_file=str(x.relative_to(EVIDENCE)),output_file=str(y.relative_to(EVIDENCE))))
        assert joined
        rows.append(dict(case=case,joined_calls=len(joined),layers=sorted(set(r['layer'] for r in joined))))
        save(folder/'TRACE_AUDIT.json',dict(domain='PC_MATH_DOUBLE_NOT_FPGA',calls=joined))
    save(EVIDENCE/'TRACE_AUDIT.json',dict(status='PASS_PC_INPUT_RETURN_CONSUMER_CHAIN',cases=rows,
        hardware_global_count=None,BOARD='NOT_TESTED',
        counterfactual='graph-v2/counterfactual/result.json rejects dropped graph output'))
    print(json.dumps(dict(status='PASS_PC_INPUT_RETURN_CONSUMER_CHAIN',cases=len(rows))))
