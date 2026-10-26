import json
from pathlib import Path
folder=Path(__file__).parent
receipt=json.loads((folder/'preflight-uart.json').read_text(encoding='utf-8-sig'))
data=next(json.loads(q.strip()) for q in receipt['output'].splitlines() if q.strip().startswith('{') and 'baseline_sha256' in q)
with (folder/'preflight-local.json').open('x',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,indent=2)
print('BASELINE',data['baseline_sha256'],'SCAN',data['scan_complete'],'MEMORY',data['memory'])
for q in data['diagnostics']:print(q['text'])
