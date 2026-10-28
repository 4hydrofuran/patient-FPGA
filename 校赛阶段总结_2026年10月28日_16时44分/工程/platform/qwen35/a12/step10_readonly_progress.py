"""Read-only bounded process/worker evidence; no signals or device operations."""
import hashlib,json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/step10-baseline-20261024-v1')
assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
result={}
for name in ('manager.stderr.txt','manager-exit.json','run-v1/s2/ISOLATED.json'):
    p=root/name
    if p.is_file():result[name]=p.read_text()[-8192:]
for side in ('s1','s2'):
    folder=root/'run-v1'/side;r={}
    for name in ('ready.json','identity.json','exit.json'):
        p=folder/name
        if p.is_file():r[name]=json.loads(p.read_text())
    p=folder/'worker/stdout.jsonl'
    if p.is_file():
        with p.open('rb') as f:
            f.seek(max(0,p.stat().st_size-12000));r['tail']=f.read().decode(errors='replace')
    identity=folder/'identity.json'
    if identity.is_file():
        pid=json.loads(identity.read_text())['pid'];proc=Path('/proc')/str(pid)
        if proc.is_dir():
            r['stat']= (proc/'stat').read_text();r['status']=(proc/'status').read_text()
            r['libraries']=[s for s in (proc/'maps').read_text().splitlines() if 'libggml' in s or 'libllama' in s or 'libsp_linear' in s]
    result[side]=r
result['frequencies']={str(p):p.read_text() for p in Path('/sys/devices/system/cpu').glob('cpufreq/policy*/scaling_cur_freq')}
print(json.dumps(result),flush=True)
