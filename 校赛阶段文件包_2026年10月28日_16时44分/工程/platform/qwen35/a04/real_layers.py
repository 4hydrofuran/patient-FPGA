"""All captured rows vs independent scalar, optimized C++ and original FP32.

No graph replacement: local S1 diagnostics do not claim full-model S1 quality.
"""
import hashlib,json,os,resource,struct,subprocess,sys,time
from pathlib import Path
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
import numpy as np
from quant.reference import scalar


def error(a,b):
    a=np.asarray(a,dtype=np.float64);b=np.asarray(b,dtype=np.float64);d=a-b
    return {'max_abs':float(np.max(np.abs(d))),'rmse':float(np.sqrt(np.mean(d*d))),
        'nrmse':float(np.linalg.norm(d)/max(np.linalg.norm(b),1e-30)),
        'tolerance_failures':int(np.sum(np.abs(d)>1e-4+1e-5*np.abs(b)))}


def main():
    out=ROOT/'eval/qwen35/a04/real-v1';out.mkdir(exist_ok=False)
    side=ROOT/'models/sidecar_A/qwen35-v1';man=json.loads((side/'manifest.json').read_text())
    entries={e['id']:e for e in man['entries']};mapping=json.loads((ROOT/'quant/qwen35_tensor_map.json').read_text())
    source={f"l{e['layer']:02d}_{e['op']}":e for e in mapping['mlp']};rows=[]
    caps=ROOT/'eval/qwen35/a04/captures-v1';start=time.monotonic()
    for kind in ('H0_F16','S0_Q4'):
        cap=json.loads((caps/kind/'manifest.json').read_text())
        for rec in cap['records']:
            ident=f"l{rec['layer']:02d}_{rec['op']}";e=entries[ident];n,k,t=rec['N'],rec['K'],rec['T']
            d=out/(kind+'_'+rec['id']);d.mkdir();xfile=caps/kind/rec['input']['file'];yf=caps/kind/rec['output']['file']
            assert hashlib.sha256(xfile.read_bytes()).hexdigest()==rec['input']['sha256']
            assert hashlib.sha256(yf.read_bytes()).hexdigest()==rec['output']['sha256']
            x=np.fromfile(xfile,dtype='<f4').reshape(t,k);observed=np.fromfile(yf,dtype='<f4').reshape(t,n)
            wf=side/e['files']['w.bin']['file'];sf=side/e['files']['sw.bin']['file']
            argv=['/home/member-a/qwen35-a04/build-v1/w4ref','run',str(n),str(k),str(t),str(wf),str(sf),str(xfile),str(d/'cpp')]
            proc=subprocess.run(argv,capture_output=True,text=True)
            with (d/'command.json').open('x') as f:json.dump({'argv':argv,'exit_code':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr},f,indent=2)
            if proc.returncode:raise RuntimeError('C++ layer failure: '+str(d))
            metrics=json.loads(proc.stdout)
            xq,sx=scalar.quant_activations(x.tolist())
            assert xq==(d/'cpp/xq.bin').read_bytes() and sx==(d/'cpp/sx.bin').read_bytes(),'A8 independent mismatch'
            begin=time.monotonic();y,integer=scalar.execute(n,k,t,wf.read_bytes(),sf.read_bytes(),xq,sx)
            oracle_s=time.monotonic()-begin
            expected=np.asarray(y,dtype='<f4').reshape(t,n);sums=np.asarray(integer,dtype='<i4')
            expected.tofile(d/'python_y.bin');sums.tofile(d/'python_sums.bin')
            cpp=np.fromfile(d/'cpp/y.bin',dtype='<f4').reshape(t,n);cpp_sums=np.fromfile(d/'cpp/sums.bin',dtype='<i4')
            same_integer=np.array_equal(sums,cpp_sums);same_bits=np.array_equal(expected.view('u4'),cpp.view('u4'))
            # Independent source decode, not importing producer or its loader.
            raw_meta=source[ident]
            with (ROOT/'artifacts/qwen35-0.8b/source'/raw_meta['source_file']).open('rb') as f:
                f.seek(raw_meta['absolute_offset']);raw=f.read(n*k*2)
            assert hashlib.sha256(raw).hexdigest()==raw_meta['source_tensor_sha256']
            original=(np.frombuffer(raw,dtype='<u2').astype('<u4')<<16).view('<f4').reshape(n,k)
            original_y=x@original.T
            original_y.astype('<f4').tofile(d/'original_fp32_y.bin')
            result={'id':rec['id'],'input_model':kind,'T':t,'N':n,'K':k,'integer_bit_exact':same_integer,
                'float_bit_exact':same_bits,'cpp_vs_independent_reference':error(cpp,expected),
                'raw_FP32_vs_W4A8_same_input':error(cpp,original_y),
                'captured_native_vs_raw_FP32_same_input':error(observed,original_y),
                'local_S1_vs_native_projection':error(cpp,observed),
                'precision_note':'Numerical tolerance applies ONLY to same-math CPP/oracle; quantization errors are separate diagnostics, not clinical quality scores.',
                'cpp_metrics':metrics,'python_oracle_s':oracle_s,'hardware_error':None,'BOARD':'NOT_TESTED'}
            rows.append(result)
            with (d/'comparison.json').open('x') as f:json.dump(result,f,indent=2)
            print(json.dumps({'row':len(rows),'id':kind+'_'+rec['id'],'integer':same_integer,'fp32':same_bits,'quant_nrmse':result['raw_FP32_vs_W4A8_same_input']['nrmse']}),flush=True)
            del original,raw,original_y,x,observed,sums,integer,y,cpp,cpp_sums,expected
    passed=all(r['integer_bit_exact'] and r['cpp_vs_independent_reference']['tolerance_failures']==0 for r in rows)
    result={'domain':'PC','passed':passed,'rows':rows,'count':len(rows),'elapsed_s':time.monotonic()-start,
        'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'CPU_reference_threads':1,
        'ledger':{'H0_to_S0':'Separate real high precision/Q4 captures; includes upstream state and generic quantization, not W4 hardware error',
                  'S0_to_S1':'Only local projection on captured S0 input measured; full graph/logits/task quality pending A05',
                  'S1_to_S2':None},'whole_model_S1':'NOT_TESTED_A05','hardware_error':None,'BOARD':'NOT_TESTED'}
    with (out/'summary.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({'count':len(rows),'passed':passed,'elapsed_s':result['elapsed_s']}))
    return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
