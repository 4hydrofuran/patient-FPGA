import json,sys
from native_client import ROOT,Worker
out=ROOT/sys.argv[1];out.mkdir(exist_ok=False)
inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text())
w=Worker(out/'worker',binary='/home/member-a/qwen35-a05/build-v4/qwen35-s1')
records=[]
try:
    for chunk in (1,2,4,8):
        r=w.call({'id':str(chunk),'tokens':inp['tokens'],'max_tokens':2,'teacher_tokens':inp['teacher'],'prefill_chunk':chunk,
          'logits_mode':'all','diagnostic_dir':str(out/('chunk-'+str(chunk))),'diagnostic_nodes':True,'dump_state':True})
        records.append(r);assert r.get('status')=='OK'
finally:w.close()
with (out/'records.json').open('x') as f:json.dump(records,f,indent=2)
