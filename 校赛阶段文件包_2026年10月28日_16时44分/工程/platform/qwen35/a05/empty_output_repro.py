"""Retain the v6 empty-output crash and verify the same input on the repaired build."""
import json,sys
from native_client import ROOT,Worker
out=ROOT/sys.argv[1];out.mkdir(exist_ok=False);binary=sys.argv[2];expected=sys.argv[3]
inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text());records={}
w=Worker(out/'worker',binary=binary)
try:
    for mode in ('all','final'):
        records[mode]=w.call({'id':mode,'tokens':inp['tokens'],'prefill_chunk':1,'max_tokens':1,'logits_mode':mode})
finally:w.close()
with (out/'report.json').open('x') as f:json.dump({'argv':w.argv,'records':records,'exit_code':w.p.returncode,'expected':expected},f,indent=2)
print(json.dumps({'all':records['all']['type'],'final':records['final']['type'],'exit':w.p.returncode}))
assert records['all'].get('status')=='OK'
if expected=='failure':assert records['final']['type']=='eof' and w.p.returncode!=0
else:assert records['final'].get('status')=='OK' and w.p.returncode==0
