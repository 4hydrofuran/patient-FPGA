"""Export only this run's bounded ordinary receipts; no model/state diagnostics."""
import hashlib,json,os,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/pl-authfix-20261026-v1')
files=[]
for name in ('preflight.json','authorization.json','binding-source.py','run_bound_original.py','run_bound_original2.py','manager.stdout','manager.stderr','ATTEMPT_RESULT.json'):
 p=root/name
 if p.is_file():files.append(p)
run=root/'bundle/run-v1'
if run.exists():files += [p for p in run.rglob('*') if p.is_file()]
previous=root/'setup-attempt-01'
if previous.exists():files += [p for p in previous.rglob('*') if p.is_file()]
assert sum(p.stat().st_size for p in files)<=16777216
export=root/'receipt-export.zip'
with zipfile.ZipFile(export,'x',zipfile.ZIP_DEFLATED) as archive:
 for p in files:archive.write(p,p.relative_to(root).as_posix())
n=export.stat().st_size;digest=hashlib.sha256()
with export.open('rb') as f:
 for b in iter(lambda:f.read(65536),b''):digest.update(b)
with export.open('rb') as f:
 response=urllib.request.urlopen(urllib.request.Request('http://192.168.2.1:8765/receipt.zip',data=f,headers={'Content-Length':str(n)},method='POST'),timeout=30).read(100)
assert response==b'RECEIVED'
over=Path('/sys/kernel/config/device-tree/overlays')
print('__PL_BEGIN__');print(json.dumps(dict(status='RUN_RECEIPTS_EXPORTED',bytes=n,sha256=digest.hexdigest(),
 boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
 active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists(),
 overlays={d.name:(d/'status').read_text().strip() for d in over.iterdir() if d.is_dir()})));print('__PL_END__')
