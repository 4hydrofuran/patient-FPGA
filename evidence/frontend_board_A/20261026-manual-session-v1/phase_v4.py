import json
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');r={}
for name in ('bundle/run-v1/s2/ready.json','bundle/run-v1/s2/warm-result.json','bundle/run-v1/s2/ISOLATED.json','bundle/run-v1/s2/worker/stderr.log','bundle/run-v1/s2/worker/stdout.jsonl','bundle/run-v1/s2/INTERACTIVE_READY.json'):
    p=root/name
    if p.exists():r[name]=dict(bytes=p.stat().st_size,tail=p.read_text(errors='replace')[-1500:])
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
