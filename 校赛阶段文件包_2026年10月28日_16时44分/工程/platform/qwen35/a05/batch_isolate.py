"""Use the retained failing binary; disable only the documented CPU tiled dispatch."""
import json,os,sys
from native_client import ROOT,Worker
out=ROOT/sys.argv[1];out.mkdir(exist_ok=False)
os.environ['GGML_CPU_TILED_MM']='0'
inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text())
records={}
for model in ('f16','Q4_K_M'):
    w=Worker(out/model/'worker',model=model,binary='/home/member-a/qwen35-a05/build-v1/qwen35-s1')
    try:
        for chunk in (1,2,4,8):
            r=w.call({'id':str(chunk),'tokens':inp['tokens'],'max_tokens':2,'teacher_tokens':inp['teacher'],
              'prefill_chunk':chunk,'save_logits_reference':chunk==1,'compare_logits':chunk!=1})
            records[model+'-'+str(chunk)]=r
            print(json.dumps({'model':model,'T':chunk,'status':r.get('status'),'comparison':r.get('logits_comparison')}),flush=True)
    finally:w.close()
with (out/'results.json').open('x') as f:json.dump({'env':{'GGML_CPU_TILED_MM':'0'},'records':records},f,indent=2)
