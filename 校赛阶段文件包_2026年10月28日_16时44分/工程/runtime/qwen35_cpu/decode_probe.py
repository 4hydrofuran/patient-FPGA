"""Extra short-answer sample with enough generated tokens to expose decode timing."""
import json
from pathlib import Path
from test_baseline import Native, render, ROOT
import argparse

p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
n=Native(Path('/home/member-a/qwen35-a01/native-build/qwen35-cpu'),a.model,a.output,'decode')
try:
    r=n.request({'id':'short-answer','prompt':render([{'role':'user','content':'请用约60个汉字解释为什么学习一门技能需要反复练习。不要列标题。'}]),'max_tokens':96})
    status='PASS' if r.get('status')=='OK' and len(r['output_tokens'])>=16 and '<think>' not in r['text'] and '</think>' not in r['text'] else 'FAIL'
    with (a.output/'summary.json').open('x') as f:json.dump({'status':status,'ready':n.ready,'result':r,'domain':'PC','board':'NOT_TESTED','repetitions':1,'decode_steps_per_second':1000*r['decode_calls']/r['decode_ms'] if r['decode_ms'] else None},f,ensure_ascii=False,indent=2)
    print(json.dumps({'status':status,'tokens':len(r.get('output_tokens',[])),'output':str(a.output)}))
finally:n.close()
raise SystemExit(status!='PASS')
