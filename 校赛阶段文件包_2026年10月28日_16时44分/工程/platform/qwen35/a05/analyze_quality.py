"""Quality differences are measured, not numerics acceptance or hardware error."""
import argparse,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args();root=ROOT/a.input;result={}
for baseline,candidate in [('H0','S0'),('S0','S1'),('H0','S1')]:
    b=json.loads((root/baseline/'manifest.json').read_text());c=json.loads((root/candidate/'manifest.json').read_text());rows=[]
    for bb,cc in zip(b['logits'],c['logits'],strict=True):
        assert bb['position']==cc['position'];x=np.fromfile(root/baseline/bb['file'],dtype='<f4').astype('float64');y=np.fromfile(root/candidate/cc['file'],dtype='<f4').astype('float64')
        lx=x-np.max(x);lx-=np.log(np.exp(lx).sum());ly=y-np.max(y);ly-=np.log(np.exp(ly).sum());delta=x-y
        rows.append({'position':bb['position'],'max_abs':float(np.max(np.abs(delta))),'rmse':float(np.sqrt(np.mean(delta*delta))),'kl_reference_to_candidate':float(np.sum(np.exp(lx)*(lx-ly))),'top1_equal':bool(np.argmax(x)==np.argmax(y))})
    result[baseline+'->'+candidate]={'positions':len(rows),'top1_equal':sum(x['top1_equal'] for x in rows),'mean_kl':sum(x['kl_reference_to_candidate'] for x in rows)/len(rows),'rows':rows}
result.update(domain='PC',hardware_error=None,BOARD='NOT_TESTED',scope='one short frozen teacher-forced diagnostic; full-vocabulary logits. Not clinical quality or perplexity corpus. S1 differs from S0 in ORIGINAL-BF16 MLP weights plus W4A8 and graph, not pure Q4 byte reinterpretation.')
with (root/'quality.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:{kk:vv for kk,vv in v.items() if kk!='rows'} for k,v in result.items() if isinstance(v,dict)}))
