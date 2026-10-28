import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-random-20261027-v1');s=root/'continuous/bundle/run-v1/s2'
r={'status':'CASE20_STARTUP_PROGRESS','files':{},'lease':None}
for n in ('manager.stdout','manager.stderr','continuous/bundle/run-v1/s2/worker/stderr.txt','continuous/bundle/run-v1/s2/worker/events.jsonl','continuous/bundle/run-v1/s2/worker/stdout.jsonl'):
 p=root/n
 if p.exists():
  raw=p.read_bytes();r['files'][n]={'bytes':len(raw),'tail':raw[-1600:].decode(errors='replace')}
p=Path('/var/lock/kv260-a1/active/lease.json')
if p.exists():
 x=json.loads(p.read_text());r['lease']={k:x.get(k) for k in ('window','pid','expires_monotonic_ns')}
r['root_entries']=[p.name for p in (root/'continuous/bundle/run-v1').iterdir()] if (root/'continuous/bundle/run-v1').exists() else []
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
