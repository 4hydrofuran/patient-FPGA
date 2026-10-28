"""Compare the new CPU control against preserved final A05 v8, no hardware."""
import json
from pathlib import Path
from common import EVIDENCE,save,sha
from test_graph import one


if __name__=='__main__':
    folder=EVIDENCE/'canonical-a05-v8'
    if (folder/'result.json').exists():
        r=json.loads((folder/'result.json').read_text())
        assert r['type']=='result' and r['status']=='OK' and r['state_cleared_before_response']
        row=dict(scope='CPU_ALL',status='PASS_PC_MODEL_MATH',
                 logits={p.name:sha(p) for p in (folder/'diag').glob('logits-*.f32')},
                 state=sha(folder/'diag/hybrid-state.bin'),fingerprint=r.get('state_fingerprint'),
                 note='reuses actual successful canonical run; original postprocessing KeyError retained')
    else:
        row=one(Path('/home/member-a/qwen35-a05/build-v8/qwen35-s1'),folder,None)
    expected=json.loads((EVIDENCE/'graph-v2/SUMMARY.json').read_text())['runs'][0]
    assert row['logits']==expected['logits'] and row['state']==expected['state']
    save(EVIDENCE/'CANONICAL_COMPARISON.json',dict(status='PASS_PC_CANONICAL_A05_V8_BIT_EXACT',
        canonical=row,new_control=expected,BOARD='NOT_TESTED'))
    print('PASS_PC_CANONICAL_A05_V8_BIT_EXACT')
