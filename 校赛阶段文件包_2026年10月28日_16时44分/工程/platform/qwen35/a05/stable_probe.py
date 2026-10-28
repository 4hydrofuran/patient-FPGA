"""Actual S1 physical-T probe: never spoof result/activation/BO evidence."""
import json,sys
from native_client import ROOT,Worker
out=ROOT/sys.argv[1];out.mkdir(exist_ok=False)
inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text())
binary=sys.argv[2] if len(sys.argv)>2 else '/home/member-a/qwen35-a05/build-v5/qwen35-s1'
w=Worker(out/'worker',binary=binary);records={}
try:
    for chunk in (1,2,4,8,256):
        r=w.call({'id':str(chunk),'tokens':inp['tokens'],'max_tokens':2,'teacher_tokens':inp['teacher'],'prefill_chunk':chunk,
          'save_logits_reference':chunk==1,'compare_logits':chunk!=1,'logits_mode':'all',
          'diagnostic_dir':str(out/f'chunk-{chunk}'),'diagnostic_all_layers':True,'dump_state':True})
        records[str(chunk)]=r
        print(json.dumps({'T':chunk,'status':r.get('status'),'comparison':r.get('logits_comparison')}),flush=True)
        assert r.get('status')=='OK',r
finally:w.close()
with (out/'results.json').open('x') as f:json.dump({'ready':w.ready,'records':records},f,indent=2)
assert all(r['logits_comparison']['failures']==0 for c,r in records.items() if c!='1')
