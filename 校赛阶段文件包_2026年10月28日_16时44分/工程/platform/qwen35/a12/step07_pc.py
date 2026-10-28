"""Selected same-math graph and discarded-consumer regression for instrumented build."""
import json
from pathlib import Path
from common import save
from step07_protocol import OUT
from test_graph import one


if __name__=='__main__':
    build=json.loads((OUT/'BUILD.json').read_text());binary=Path(build['pc']);out=OUT/'pc-graph-v1';out.mkdir()
    baseline=one(binary,out/'s1',None);trial=one(binary,out/'l0_gate','l0_gate')
    assert baseline['logits']==trial['logits'] and baseline['state']==trial['state']
    rejected=one(binary,out/'counterfactual','l0_gate',fault=True)
    prior=json.loads((OUT.parent/'20261023-preboard-v1/graph-v2/SUMMARY.json').read_text())['runs'][0]
    assert baseline['logits']==prior['logits'] and baseline['state']==prior['state']
    save(OUT/'PC_GRAPH.json',dict(status='PASS_SELECTED_PC_GRAPH_BIT_EXACT_AND_REJECTION',runs=[baseline,trial,rejected],
                               canonical_v1_unchanged=True,BOARD='NOT_TESTED'))
    print('PASS_SELECTED_PC_GRAPH_BIT_EXACT_AND_REJECTION')
