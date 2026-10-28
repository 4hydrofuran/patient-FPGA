import ast,gzip,hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
s=(E/'stage_v2.py').read_text();assignment=next(n for n in ast.parse(s).body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='payload')
payload=ast.literal_eval(assignment.value)
b=gzip.compress(json.dumps(payload).encode(),mtime=0);pin=hashlib.sha256(b).hexdigest()
(E/'patch.json.gz').write_bytes(b)
remote='/home/ubuntu/a11-compute-patch-20261023-v1/patch.json.gz'
start=s.splitlines();old='\n'.join(start[assignment.lineno-1:assignment.end_lineno])
new="import gzip\npatch=Path("+repr(remote)+").read_bytes()\nassert hashlib.sha256(patch).hexdigest()=="+repr(pin)+"\npayload=json.loads(gzip.decompress(patch))"
(E/'stage_v2_small.py').write_bytes(s.replace(old,new).encode())
print(json.dumps(dict(patch_sha256=pin,patch_bytes=len(b))))
