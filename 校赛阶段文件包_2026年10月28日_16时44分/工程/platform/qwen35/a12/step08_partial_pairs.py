"""Read-only early comparison of completed dev pairs; no cancellation/device action."""
import hashlib
import json
import os
from pathlib import Path
assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
root=Path('/var/lib/kv260-a12/step08-generation-20261024-v1');rows=[]
keys=('output_tokens','text','eos','state_fingerprint','last_prompt_logits_fnv64','prompt_tokens')
for p in sorted((root/'run-v1/s2').glob('*/result.json')):
    b=json.loads(p.read_text());a=json.loads((root/'run-v1/s1'/p.parent.name/'result.json').read_text())
    matches={k:a[k]==b[k] for k in keys}
    rows.append(dict(id=p.parent.name,matches=matches,S1_text=a['text'],S2_text=b['text'],EOS=b['eos'],
        actual_completions=b['bridge']['a12_route']['host_verified_completions'],decode_calls=b['decode_calls'],
        prefill_requested_logits=b['prefill_requested_logits'],output_tokens=len(b['output_tokens'])))
print(json.dumps(dict(status='PARTIAL_MATCH' if all(all(r['matches'].values()) for r in rows) else 'FAIL_PARTIAL_PAIR',
    rows=rows,completed=len(rows),no_device_action=True),ensure_ascii=False),flush=True)
assert all(all(r['matches'].values()) for r in rows)
