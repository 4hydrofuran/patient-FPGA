"""Bounded read-only progress for the exact window; no scans/signals/device opens."""
import hashlib,json,os
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/tt10-01-20261025-v2')
assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='1d0499ab-f1f9-438c-969a-3e701a0d806f'
def load(p):return json.loads(p.read_text()) if p.is_file() else None
def tail(p,budget=8192):
    if not p.is_file():return None
    with p.open('rb') as f:
        size=p.stat().st_size;f.seek(max(0,size-budget));data=f.read(budget)
    if size>budget:data=data.split(b'\n',1)[-1]
    return data.decode('utf-8',errors='replace')
r=dict(scope='EXACT_WINDOW02_READ_ONLY_STATUS',root_exists=ROOT.exists(),manager_pid=4112,
    manager_stdout=tail(ROOT/'manager.stdout.jsonl'),manager_stderr=tail(ROOT/'manager.stderr.txt'),
    manager_exit=load(ROOT/'manager-exit.json'),result=load(ROOT/'run-v1/result.json'),
    s2_isolated=load(ROOT/'run-v1/s2/ISOLATED.json'),lease=load(Path('/var/lock/kv260-a1/active/lease.json')),
    lifecycle=tail(ROOT/'run-v1/lifecycle.jsonl'),backends={})
proc=Path('/proc/4112')
if proc.exists():
    r['manager_stat']=(proc/'stat').read_text();r['manager_children']=(proc/'task/4112/children').read_text()
for name in ('s1','s2'):
    d=ROOT/'run-v1'/name
    r['backends'][name]=dict(ready=load(d/'ready.json'),normal_exit=load(d/'exit.json'),worker_stderr=tail(d/'worker/stderr.txt'),cases={})
    for case in ('diag_exact','warm_prefix','diag_full_R0','diag_hit','app_R0','app_hit'):
        p=d/case/'result.json'
        if p.is_file():
            x=load(p);r['backends'][name]['cases'][case]={k:x.get(k) for k in ('type','id','status','eos','decode_calls','state_cleared_before_response')}
    worker=d/'worker/stdout.jsonl';last=tail(worker,4096)
    if last:
        lines=last.splitlines()
        try:
            x=json.loads(lines[-1]);r['backends'][name]['worker_last']={k:x.get(k) for k in ('type','id','status','error','message')}
        except (ValueError,IndexError):r['backends'][name]['worker_last']='PARTIAL_OR_NON_JSON'
print(json.dumps(r),flush=True)
