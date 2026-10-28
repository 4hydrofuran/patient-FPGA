"""Read-only compact progress from exact step08 windows, without proc scans/signals."""
import json
import os
from pathlib import Path
import hashlib
import time

assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
result=dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,windows={})
for variant in ('diagnostic','generation'):
    root=Path('/var/lib/kv260-a12')/('step08-'+variant+'-20261024-v1')
    if not root.is_dir():continue
    files={}
    for name in ('manager-pid.json','manager-exit.json','manager.stderr.txt','run-v1/result.json','run-v1/s2/ISOLATED.json'):
        p=root/name
        if p.is_file():files[name]=p.read_text()[-8192:]
    life=root/'run-v1/lifecycle.jsonl';selected=[]
    if life.exists():
        for line in life.read_text().splitlines():
            row=json.loads(line)
            if row['event']=='CASE_FINISHED':selected.append(row)
        files['lifecycle_last']=json.loads(life.read_text().splitlines()[-1])
    workers={}
    for side in ('s1','s2'):
        folder=root/'run-v1'/side;events=folder/'worker/events.jsonl';stdout=folder/'worker/stdout.jsonl'
        info=dict(completed=[p.parent.name for p in folder.glob('*/result.json')])
        for name in ('identity.json','exit.json'):
            p=folder/name
            if p.is_file():info[name]=json.loads(p.read_text())
        if events.exists():
            rows=[json.loads(l) for l in events.read_text().splitlines()]
            submits=[r for r in rows if r.get('request',{}).get('phase')=='submit']
            info.update(permission_submits=len(submits),last_events=rows[-2:])
        p=folder/'worker/stderr.txt'
        if p.exists():info['stderr_tail']=p.read_text()[-2000:]
        workers[side]=info
    result['windows'][variant]=dict(files=files,finished_cases=selected,workers=workers)
result['host_monotonic_ns']=time.monotonic_ns()
print(json.dumps(result),flush=True)
