"""Staged real model smoke: exact scope identity and consumed outputs."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'runtime/qwen35_cpu'))
from test_baseline import render
p=argparse.ArgumentParser();p.add_argument('--scope',required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=ROOT/a.output;out.mkdir(exist_ok=False)
argv=['/home/member-a/qwen35-a05/build-v1/qwen35-s1',str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'4','1024',a.scope]
with (out/'stderr.txt').open('x') as err,(out/'wire.jsonl').open('x') as wire:
    proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
    def read():
        line=proc.stdout.readline();wire.write(line);wire.flush()
        if not line:raise RuntimeError('early exit '+str(proc.poll()))
        return json.loads(line)
    ready=read();assert ready['type']=='ready',ready
    req={'id':a.scope,'prompt':render([{'role':'user','content':'只回答数字：2加3等于多少？'}]),'max_tokens':8,'logits_mode':'final','diagnostic_dir':str(out/'diagnostic')}
    wire.write(json.dumps({'request':req},ensure_ascii=False)+'\n');proc.stdin.write(json.dumps(req)+'\n');proc.stdin.flush()
    while True:
        r=read()
        if r['type'] in ('error','result'):break
    proc.stdin.write('{"op":"shutdown"}\n');proc.stdin.flush();proc.wait(timeout=30)
    expected=72 if a.scope=='all' else 3 if a.scope=='l0' else 1 if a.scope.startswith('l0_') else 0
    ok=r.get('status')=='OK' and len(r['bridge']['weights'])==expected and all(v['calls']>0 for v in r['bridge']['weights'].values()) and r['state_position_after_clear']==-1 and proc.returncode==0
    with (out/'summary.json').open('x') as f:json.dump({'argv':argv,'ready':ready,'result':r,'exit_code':proc.returncode,'passed':ok,'expected_projection_count':expected,'BOARD':'NOT_TESTED'},f,ensure_ascii=False,indent=2)
    print(json.dumps({'scope':a.scope,'passed':ok,'text':r.get('text'),'status':r.get('status')},ensure_ascii=False));raise SystemExit(not ok)
