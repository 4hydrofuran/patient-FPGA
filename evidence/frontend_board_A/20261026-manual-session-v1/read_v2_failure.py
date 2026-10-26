import json
from pathlib import Path
r=Path('/var/lib/kv260-a12/manual-web-20261026-v2')
rows=[json.loads(l) for l in (r/'bundle/run-v1/lifecycle.jsonl').read_text().splitlines()]
last=next(x for x in reversed(rows) if x['event']=='READBACK')
print('__PL_BEGIN__');print(json.dumps(dict(started=json.loads((r/'started.json').read_text()),last_snapshot=last)));print('__PL_END__')
