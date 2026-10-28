"""Read the exact staged preflight and archive evidence; no writes or model work."""
import base64,hashlib,json,os
from pathlib import Path
assert os.geteuid()==0
root=Path('/var/lib/kv260-a12/tt10-01-20261025-v2')
files={}
for name,p in [('control/preflight.json',root/'control/preflight.json'),
               ('manifest.json',root/'manifest.json'),('stage-receipt.json',root/'stage-receipt.json'),
               ('archived-lease.json',Path('/var/lock/kv260-a1/history/a12-tt10-01-20261025-v2/lease.json'))]:
    b=p.read_bytes();files[name]=dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),base64=base64.b64encode(b).decode())
print(json.dumps(dict(scope='WINDOW02_STAGED_AND_ARCHIVED_RAW_RECORDS_READ_ONLY',files=files)),flush=True)
