"""Actual l00 PC graph/consumer regression; no FPGA claim."""
import json
from pathlib import Path
from common import ROOT,sha,save
from step07_mlp_prepare import OUT
from test_graph import one

if __name__=='__main__':
    binary=Path(json.loads((OUT.parent/'20261023-step07-single-v1/BUILD.json').read_text())['pc'])
    out=OUT/'pc-graph-v1';out.mkdir()
    baseline=one(binary,out/'s1',None);trial=one(binary,out/'l0','l0')
    assert baseline['logits']==trial['logits'] and baseline['state']==trial['state']
    assert trial['trace_calls']==9 and trial['trace_layers']==[0]
    rejected=one(binary,out/'discarded-y','l0',fault=True)
    save(OUT/'PC_GRAPH.json',dict(status='PASS_PC_L00_GRAPH_AND_DISCARDED_Y_REJECTION',
       binary_sha256=sha(binary),runs=[baseline,trial,rejected],BOARD='NOT_TESTED'))
    print('PASS_PC_L00_GRAPH_AND_DISCARDED_Y_REJECTION')
