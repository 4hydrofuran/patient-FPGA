import json,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/gui-qa-20261026-v1');r={}
for n in ('started.json','bundle/run-v1/s2/WEB_REAL_VERIFICATION.json','bundle/run-v1/s2/USER_INPUT_READY.json','bundle/run-v1/s2/ISOLATED.json','manager.stderr'):
    p=root/n
    if p.exists():r[n]=p.read_text(errors='replace')[-2500:]
for n in ('ready.json','warm-result.json','INTERACTIVE_READY.json'):
    r[n]=(root/'bundle/run-v1/s2'/n).exists()
try:r['status']=json.load(urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3))
except Exception as e:r['http_error']=str(e)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
