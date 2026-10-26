import json,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v3')
r={'active':Path('/var/lock/kv260-a1/active').exists()}
for name in ('manager.stdout','manager.stderr','bundle/run-v1/s2/INTERACTIVE_READY.json','bundle/run-v1/s2/ISOLATED.json','bundle/run-v1/s2/manual-compute-closed.json','bundle/run-v1/result.json'):
    p=root/name
    if p.is_file():r[name]=p.read_text(errors='replace')[-2400:]
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3) as f:r['web_status']=json.load(f)
except Exception as e:r['http_error']=str(e)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
