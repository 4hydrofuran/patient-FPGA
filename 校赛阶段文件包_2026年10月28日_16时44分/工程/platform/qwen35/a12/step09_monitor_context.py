"""Bounded read-only generation progress stream; never signals or touches devices."""
import hashlib
import json
import os
from pathlib import Path
import time

assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
root=Path('/var/lib/kv260-a12/step09-context-20261024-v1')
assert root.is_dir()
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def tail(p):
    if not p.is_file():return []
    with p.open('rb') as f:
        size=f.seek(0,2);start=max(0,size-8192);f.seek(start);data=f.read()
    lines=data.splitlines()
    if start:lines=lines[1:]
    result=[]
    for line in lines:
        try:result.append(json.loads(line))
        except (ValueError,UnicodeDecodeError):pass
    return result
for attempt in range(601):
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    row=dict(boot_id=boot,monotonic_ns=time.monotonic_ns(),attempt=attempt,workers={})
    for side in ('s1','s2'):
        folder=root/'run-v1'/side;events=tail(folder/'worker/events.jsonl')
        row['workers'][side]=dict(completed=sorted(p.parent.name for p in folder.glob('*/result.json')),
            last_event=events[-1] if events else None,normal_exit=json.loads((folder/'exit.json').read_text()) if (folder/'exit.json').is_file() else None)
        row['workers'][side]['pending']=sorted(p.parent.name for p in folder.glob('*/request.json') if not (p.parent/'result.json').exists())
        identity=folder/'identity.json'
        if identity.is_file():
            pid=json.loads(identity.read_text())['pid'];stat=Path('/proc')/str(pid)/'stat'
            try:
                fields=stat.read_text().rsplit(')',1)[1].split()
                row['workers'][side]['process']=dict(pid=pid,state=fields[0],cpu_ticks=int(fields[11])+int(fields[12]),start_ticks=int(fields[19]))
            except FileNotFoundError:row['workers'][side]['process']=dict(pid=pid,absent=True)
    life=tail(root/'run-v1/lifecycle.jsonl')
    row['latest_lifecycle']=life[-1] if life else None
    row['recent_health']=next((r for r in reversed(life) if r['event']=='LIVE_HEALTH'),None)
    row['startup_negative']={p.parent.name:json.loads(p.read_text()) for p in (root/'run-v1/startup-negative').glob('*/rejection.json')}
    for name in ('manager-exit.json','manager.stderr.txt','run-v1/s2/ISOLATED.json','run-v1/result.json'):
        p=root/name
        if p.is_file():row[name]=p.read_text()[-8192:]
    print(json.dumps(row),flush=True)
    if 'manager-exit.json' in row or 'run-v1/s2/ISOLATED.json' in row:break
    if attempt<600:time.sleep(30)
