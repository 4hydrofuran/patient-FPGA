"""Numerical diagnosis, not an additional independent kernel golden."""
import json
import numpy as np
from analyze_state import ROOT,projections
out=ROOT/'eval/qwen35/a05/batch-fix-v1'
nodes=json.loads((ROOT/'eval/qwen35/a05/node-probe-v1/node-analysis.json').read_text())
# These two states are at different prefix positions in the first call. Their
# difference is expected and MUST NOT be interpreted as a first-token defect.
not_same_position={'conv_state_last-0','new_state-0'}
first={t:[x for x in values if x['name'] not in not_same_position and not x['bit_equal']][:3] for t,values in nodes.items()}
base=projections(ROOT/'eval/qwen35/a05/state-v1/chunk-256')
def aq(x):
    s=np.max(np.abs(x),axis=1).astype(np.float32)/np.float32(127)
    s=np.where(s==0,np.float32(1),s).astype(np.float32)
    return np.clip(np.rint(x/s[:,None]),-127,127).astype(np.int8),s
diagnosis={}
for t in (1,2,4,8):
    p=projections(ROOT/f'eval/qwen35/a05/state-v1/chunk-{t}')
    layer0={}
    for name,x in p.items():
        if not name.startswith('l00_'):continue
        b=base[name]['x'];x=x['x'];qx,sx=aq(x);qb,sb=aq(b)
        layer0[name]={'input_max_abs':float(np.max(np.abs(x-b))),
          'a8_code_differences':int(np.count_nonzero(qx!=qb)),
          'scale_max_abs':float(np.max(np.abs(sx-sb))),'elements':int(x.size)}
    assert len(layer0)==3,layer0
    diagnosis[str(t)]=layer0
obj={'first_token_projection_differences':first,'excluded_incomparable_state_nodes':sorted(not_same_position),
 'historical_layer0_A8_diagnosis':diagnosis,'scope':'PC numerical scheduling diagnosis, not hardware or new kernel reference',
 'correction':'node-analysis.json includes all cropped nodes; final recurrent/conv state of first T tokens cannot be compared to state of first 1 token. Full equal-prefix states are compared by analyze_state.py.'}
with (out/'root-cause-v2.json').open('x') as f:json.dump(obj,f,indent=2)
print(json.dumps({'first_projection_nodes':{t:[x['name'] for x in v] for t,v in first.items()},'layer0':diagnosis}))
