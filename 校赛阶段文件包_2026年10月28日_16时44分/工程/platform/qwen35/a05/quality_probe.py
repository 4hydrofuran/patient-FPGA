"""Separate H0/S0/S1 raw full-vocabulary logits, same teacher sequence."""
import argparse,json,sys
from native_client import ROOT,Worker
sys.path.insert(0,str(ROOT/'runtime/qwen35_cpu'))
from test_baseline import render
p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();out=ROOT/a.output;out.mkdir(exist_ok=False)
inp=json.loads((ROOT/'eval/qwen35/a05/state-v2/inputs.json').read_text());records={}
for name,model,scope in [('H0','f16','none'),('S0','Q4_K_M','none'),('S1','Q4_K_M','all')]:
    w=Worker(out/(name+'-worker'),scope=scope,model=model)
    try:
        r=w.call({'id':name,'tokens':inp['tokens'],'teacher_tokens':inp['teacher'],'max_tokens':len(inp['teacher']),'prefill_chunk':1,'logits_mode':'all','diagnostic_dir':str(out/name)})
        records[name]={'ready':w.ready,'result':r};assert r.get('status')=='OK',r
    finally:w.close()
    print(json.dumps({'mode':name,'status':r.get('status')}),flush=True)
with (out/'records.json').open('x') as f:json.dump(records,f,indent=2)
