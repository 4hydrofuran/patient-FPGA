import json
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');run=root/'bundle/run-v1';r={}
rows=[json.loads(l) for l in (run/'lifecycle.jsonl').read_text().splitlines()]
r['recent_events']=[{k:v for k,v in x.items() if k not in ('raw_log','memory_kib','zocl_binding_details','ps_display_holders','device_holders','raw_hex')} for x in rows[-8:]]
r['rejections']=[{k:v for k,v in x.items() if k not in ('raw_log','kernel_delta','memory_kib')} for x in rows if x.get('allowed') is False or 'BLOCK' in x['event']][-4:]
for p in run.glob('*kernel*'):
    if p.is_file():r[p.name]=p.read_text(errors='replace')[-2400:]
worker=run/'s2/worker';rows=[json.loads(l) for l in (worker/'events.jsonl').read_text().splitlines()]
r['recent_worker_events']=rows[-3:]
r['permission_counts']={'all':sum(x.get('event')=='PERMISSION' for x in rows),'submits_allowed':sum(x.get('event')=='PERMISSION' and x.get('request',{}).get('phase')=='submit' and x.get('allow') is True for x in rows)}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
