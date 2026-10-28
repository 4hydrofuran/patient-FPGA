"""Compare first-token node values, respecting captured actual tensor strides."""
import json,sys
import numpy as np
from pathlib import Path
from analyze_state import diff
root=Path(__file__).resolve().parents[3];p=root/sys.argv[1];results={}
base=p/'chunk-1';bm=json.loads((base/'nodes.json').read_text())
def arr(path,m):
    return np.ndarray(m['shape'],dtype='<f4',buffer=(path/m['file']).read_bytes(),strides=m['strides'])
for chunk in (2,4,8):
    other=p/f'chunk-{chunk}';om=json.loads((other/'nodes.json').read_text());records=[]
    assert len(bm)==len(om)
    for a,b in zip(bm,om):
        assert a['name']==b['name']
        x=arr(base,a);y=arr(other,b);crop=tuple(slice(0,min(i,j)) for i,j in zip(x.shape,y.shape))
        r=diff(y[crop],x[crop]);records.append({'name':a['name'],'op':a['op'],'shapes':[a['shape'],b['shape']],**r})
    results[str(chunk)]=records
with (p/'node-analysis.json').open('x') as f:json.dump(results,f,indent=2)
for c,v in results.items():print(json.dumps({'T':c,'first_nonidentical':[r for r in v if not r['bit_equal']][:4]}))
