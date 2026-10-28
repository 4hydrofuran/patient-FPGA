import collections
import hashlib
import json
import urllib.request
from pathlib import Path

root = Path('/var/lib/kv260-a12/case20-debug-20261027-v1')
gateway = root / 'continuous/web_gateway/src/patient_web'
cases = gateway / 'cases'
manifest = json.loads((cases / 'manifest.json').read_text())
rows = manifest['cases']
loaded = [json.loads((cases / (r['case_id'] + '.json')).read_text()) for r in rows]
result = dict(scope='READ_ONLY_DEPLOYED_CASE_DIVERSITY', root=str(root),
              case_count=len(rows), file_count=len(list(cases.glob('SYN_CP_*.json'))),
              groups=dict(collections.Counter(r['symptom_group'] for r in rows)),
              profiles=rows,
              distinct_fact_vectors=len({json.dumps(c['facts'], sort_keys=True) for c in loaded}),
              cases=[dict(case_id=c['case_id'], facts=c['facts']) for c in loaded],
              hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in [cases / 'manifest.json'] + [cases / (r['case_id'] + '.json') for r in rows]})
result['code'] = {}
for name in ('natural_patient_prompt.py', 'short_prompt_adapter.py', 'fast_response_profile.py'):
    found = list((root / 'continuous').rglob(name))
    result['code'][name] = [dict(path=str(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), text=p.read_text()) for p in found]
for endpoint in ('status', 'capabilities', 'cases'):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/' + endpoint, timeout=3) as response:
            result[endpoint] = json.load(response)
    except Exception as exc:
        result[endpoint] = dict(error=str(exc))
print('__TT10_UART_ROOT_SCENE_BEGIN__', flush=True)
print(json.dumps(result), flush=True)
print('__TT10_UART_ROOT_SCENE_END__', flush=True)
