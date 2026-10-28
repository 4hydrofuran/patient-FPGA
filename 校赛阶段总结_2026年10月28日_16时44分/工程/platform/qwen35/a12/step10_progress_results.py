"""Small read-only snapshot of already-finished candidate cases; no device access."""
import hashlib,json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/step10-optimized-20261024-v1')
assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='86e4938b-0f65-4166-9237-c547b67e1451'
result={'scope':'INTERIM_READ_ONLY_NOT_FINAL_AUDIT','workers':{}}
for side in ('s1','s2'):
    folder=root/'run-v1'/side;rows=[]
    for p in sorted(folder.glob('*/result.json')):
        try:r=json.loads(p.read_text())
        except ValueError:continue
        row={k:r[k] for k in ('id','status','prefill_ms','ttft_ms','decode_ms','decode_calls','eos')}
        row['output_token_count']=len(r['output_tokens'])
        client=p.with_name('client-timing.json')
        if client.is_file():
            try:q=json.loads(client.read_text());row['client_first_token_ms']=q['first_token_wall_ms'];row['client_complete_ms']=q['result_wall_ms']
            except ValueError:pass
        rows.append(row)
    result['workers'][side]=rows
for name in ('manager-exit.json','run-v1/s2/ISOLATED.json','manager.stderr.txt'):
    p=root/name
    if p.is_file():result[name]=p.read_text()[-2048:]
print(json.dumps(result),flush=True)
