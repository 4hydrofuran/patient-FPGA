"""Parse pinned hybrid-state serializer and independently compare raw diagnostics."""
import argparse,json,struct
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
def diff(a,b,atol=.002,rtol=.0002):
    if a.shape!=b.shape:return {'passed':False,'shape_mismatch':[list(a.shape),list(b.shape)]}
    delta=np.abs(a.astype(np.float64)-b.astype(np.float64))
    finite=np.isfinite(a)&np.isfinite(b);bad=~finite|(delta>atol+rtol*np.abs(b))
    return {'passed':not bool(np.any(bad)),'bit_equal':a.tobytes()==b.tobytes(),'elements':int(a.size),'failures':int(np.count_nonzero(bad)),'max_abs':float(delta.max(initial=0)),'rmse':float(np.sqrt(np.mean(delta*delta))),'atol':atol,'rtol':rtol}
def state(path):
    raw=path.read_bytes();offset=0;arrays={};meta={}
    def num(fmt):
        nonlocal offset
        value=struct.unpack_from('<'+fmt,raw,offset)[0];offset+=struct.calcsize('<'+fmt);return value
    def cells(count,ext=False):
        result=[]
        for i in range(count):
            pos=num('i');n=num('I');assert 0<=n<=1
            xy_token=[num('i') for _ in range(3)] if ext else None
            result.append([pos,xy_token,[num('i') for _ in range(n)]])
        return result
    def tensor(name,count,trans=False):
        nonlocal offset
        ty=num('i');assert ty in (0,1),ty
        if trans:
            el=num('I');cols=num('I');assert el==(4 if ty==0 else 2);size=el*cols*count
        else:size=num('Q')*count
        assert size<=len(raw)-offset
        arrays[name]=np.frombuffer(raw,dtype='<f4' if ty==0 else '<f2',count=size//(4 if ty==0 else 2),offset=offset);offset+=size
    assert num('I')==0xaf143cd8;assert num('i')==0
    assert num('I')==1;count=num('I');assert 0<count<=2048;meta['kv']=cells(count,ext=True)
    trans=num('I');layers=num('I');assert trans in (0,1) and layers==6
    for kind in ('K','V'):
        for layer in (3,7,11,15,19,23):tensor(f'{kind}{layer}',count,kind=='V' and trans==1)
    count=num('I');assert count==1;meta['recurrent']=cells(count)
    assert num('I')==0;assert num('I')==24
    for kind in ('R','S'):
        for layer in range(24):
            if layer%4!=3:tensor(f'{kind}{layer}',count)
    assert offset==len(raw),(offset,len(raw));return meta,arrays
def projections(path):
    m=json.loads((path/'manifest.json').read_text());r={}
    for p in m['projections']:
        r.setdefault(p['id'],{'x':[],'y':[]})
        r[p['id']]['x'].append(np.fromfile(path/p['input'],dtype='<f4').reshape(p['T'],p['K']))
        r[p['id']]['y'].append(np.fromfile(path/p['output'],dtype='<f4').reshape(p['T'],p['N']))
    return {k:{xy:np.concatenate(v) for xy,v in values.items()} for k,values in r.items()}
def compare(base,other):
    bm=json.loads((base/'manifest.json').read_text());om=json.loads((other/'manifest.json').read_text());assert bm['prompt_tokens']==om['prompt_tokens'] and bm['teacher_tokens']==om['teacher_tokens']
    logits={}
    for br,orr in zip(bm['logits'],om['logits'],strict=True):
        assert br['position']==orr['position'];a=np.fromfile(other/orr['file'],dtype='<f4');b=np.fromfile(base/br['file'],dtype='<f4')
        logits[str(br['position'])]={**diff(a,b),'top1_equal':int(np.argmax(a))==int(np.argmax(b))}
    am,aa=state(other/'hybrid-state.bin');bm,ba=state(base/'hybrid-state.bin');assert am==bm
    states={k:diff(aa[k],ba[k]) for k in aa};bp=projections(base);op=projections(other)
    ps={k:{xy:diff(op[k][xy],bp[k][xy]) for xy in ('x','y')} for k in op}
    return {'logits':logits,'state_metadata_equal':True,'state_arrays':states,'projections':ps,'passed':all(x['passed'] for x in logits.values()) and all(x['passed'] for x in states.values()) and all(x['passed'] for p in ps.values() for x in p.values())}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();path=ROOT/a.input
    results={name:compare(path/'chunk-256',path/name) for name in ('chunk-1','chunk-2','chunk-4','chunk-8','scalar')}
    with (ROOT/a.output).open('x') as f:json.dump(results,f,indent=2)
    print(json.dumps({k:{'passed':v['passed'],'max_logit_difference':max(x['max_abs'] for x in v['logits'].values()),'state_fail_arrays':sum(not x['passed'] for x in v['state_arrays'].values())} for k,v in results.items()}))
    return int(not all(v['passed'] for v in results.values()))
if __name__=='__main__':raise SystemExit(main())
