"""Separate quantization diagnostic attribution, never a second correctness oracle."""
import json,os,sys
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np


def err(a,b):
    d=a.astype(np.float64)-b.astype(np.float64)
    return {'max_abs':float(np.max(np.abs(d))),'nrmse':float(np.linalg.norm(d)/max(np.linalg.norm(b),1e-30))}


def main():
    out=ROOT/'eval/qwen35/a04/quality-diagnostics-v1';out.mkdir(exist_ok=False)
    side=ROOT/'models/sidecar_A/qwen35-v1';caproot=ROOT/'eval/qwen35/a04/captures-v1'
    entries=json.loads((side/'manifest.json').read_text())['entries'];rows=[];native=[]
    source=json.loads((ROOT/'quant/qwen35_tensor_map.json').read_text())['mlp']
    source={f"l{e['layer']:02d}_{e['op']}":e for e in source}
    caps={k:json.loads((caproot/k/'manifest.json').read_text()) for k in ('H0_F16','S0_Q4')}
    for e in entries:
        if e['layer'] not in (0,3,4,23):continue
        n,k=e['N'],e['K'];g=k//128
        b=np.fromfile(side/e['files']['w.bin']['file'],dtype='u1').reshape(n//32,g,128,16)
        lanes=np.empty((n//32,g,128,32),np.int8);lanes[:,:,:,0::2]=(b&15).astype(np.int8);lanes[:,:,:,1::2]=(b>>4).astype(np.int8);lanes[lanes>=8]-=16
        sc=np.fromfile(side/e['files']['sw.bin']['file'],dtype='<f4').reshape(n//32,g,32)
        dequant=(lanes.astype(np.float32)*sc[:,:,None,:]).transpose(0,3,1,2).reshape(n,k)
        m=source[e['id']]
        with (ROOT/'artifacts/qwen35-0.8b/source'/m['source_file']).open('rb') as f:f.seek(m['absolute_offset']);raw=f.read(n*k*2)
        w=(np.frombuffer(raw,dtype='<u2').astype('<u4')<<16).view('<f4').reshape(n,k)
        for kind,cap in caps.items():
            for r in cap['records']:
                if r['layer']!=e['layer'] or r['op']!=e['op']:continue
                x=np.fromfile(caproot/kind/r['input']['file'],dtype='<f4').reshape(r['T'],k)
                resultdir=ROOT/'eval/qwen35/a04/real-v1'/(kind+'_'+r['id'])
                q=np.fromfile(resultdir/'cpp/xq.bin',dtype='i1').reshape(r['T'],k)
                sx=np.fromfile(resultdir/'cpp/sx.bin',dtype='<f4')
                xd=q.astype(np.float32)*sx[:,None]
                fp=x@w.T;only_w=x@dequant.T;only_a=xd@w.T
                combined=np.fromfile(resultdir/'cpp/y.bin',dtype='<f4').reshape(r['T'],n)
                rows.append({'input_model':kind,'id':r['id'],'W4_only_same_input':err(only_w,fp),
                    'A8_only_same_weight':err(only_a,fp),'combined_W4A8':err(combined,fp),
                    'weight_dequant_error':err(dequant,w),'activation_dequant_error':err(xd,x),
                    'A8_absmax_endpoint_count':int(np.sum(np.abs(q)==127)),
                    'source_max_abs':float(np.max(np.abs(w))),'activation_max_abs':float(np.max(np.abs(x))),
                    'bias_added':False,'orientation':'Validated [N,K], no transpose',
                    'note':'W4 and A8 contributions not additive; local diagnostic, no medical quality claim'})
    for hi,lo in zip(caps['H0_F16']['records'],caps['S0_Q4']['records']):
        assert hi['id']==lo['id']
        ah=np.fromfile(caproot/'H0_F16'/hi['output']['file'],dtype='<f4');al=np.fromfile(caproot/'S0_Q4'/lo['output']['file'],dtype='<f4')
        native.append({'id':hi['id'],'H0_to_S0_observed':err(al,ah),'decode_input_token_equal':caps['H0_F16']['decode_input_token']==caps['S0_Q4']['decode_input_token'],
                       'scope':'Includes upstream generic quantization/state differences, not same-input kernel error'})
    result={'domain':'PC','rows':rows,'H0_to_S0':native,'S1_full_graph_quality':'NOT_TESTED_A05','S1_to_S2_error':None,
        'diagnosis':'Direction/source hashes/scale bytes checked independently; no bias exists. W4/A8 contributions measured separately, no precision exception or calibration introduced.',
        'warnings':['Layer NRMSE is not task/medical accuracy. Evaluate full graph logits and frozen task set in A05.'], 'BOARD':'NOT_TESTED'}
    with (out/'summary.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'rows':len(rows),'H0_to_S0':len(native),'max_W4_only_nrmse':max(r['W4_only_same_input']['nrmse'] for r in rows),
                      'max_A8_only_nrmse':max(r['A8_only_same_weight']['nrmse'] for r in rows)}))
if __name__=='__main__':main()
