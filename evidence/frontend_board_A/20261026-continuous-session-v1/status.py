import json,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-multi-20261026-v1');r={}
for n in ('started.json','manager.stderr','bundle/run-v1/s2/CONTINUOUS_VERIFICATION.json','bundle/run-v1/s2/USER_INPUT_READY.json','bundle/run-v1/s2/ISOLATED.json'):
    p=root/n
    if p.exists():r[n]=p.read_text(errors='replace')[-6000:]
for n in ('ready.json','warm-result.json','INTERACTIVE_READY.json'):r[n]=(root/'bundle/run-v1/s2'/n).exists()
r['completed_verification_turns']=[p.name for p in (root/'bundle/run-v1/s2').glob('multi-turn-*.json')]
try:r['status']=json.load(urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3))
except Exception as e:r['http_error']=str(e)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
