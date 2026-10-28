"""Explicit diagnostic variant: original F16 non-MLP + unchanged W4A8 MLP.
Does not change the default GGUF, sidecar, app selection or tolerances.
Uses retained v1 physical-batch binary to isolate non-MLP precision effects.
"""
import json,sys
from native_client import ROOT,Worker
p=ROOT/sys.argv[1];p.mkdir(exist_ok=False);inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text())
# Explicit local-only harness subclass, actual native executable, not simulated outputs.
w=Worker(p/'worker',model='f16',binary='/home/member-a/qwen35-a05/build-v1/qwen35-s1')
records=[]
try:
    for chunk in (256,1,8):
        r=w.call({'id':str(chunk),'tokens':inp['tokens'],'teacher_tokens':inp['teacher'],'max_tokens':2,'prefill_chunk':chunk,'logits_mode':'all','diagnostic_dir':str(p/('chunk-'+str(chunk))),'dump_state':True});records.append(r);assert r.get('status')=='OK'
finally:w.close()
with (p/'records.json').open('x') as f:json.dump({'variant':'ALL_NON_MLP_F16_MLP_ORIGINAL_W4A8','default_changed':False,'records':records},f,indent=2)
