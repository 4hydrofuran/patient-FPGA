import subprocess,json
code=r'''
import hashlib,json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/original-pl-20261026-v1');bundle=root/'bundle';archive=root/'precompute-staging-history'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert archive.is_dir() and not list(archive.iterdir())
p=Path('/lib/firmware/a11-mlp.dtbo');assert p.is_file() and not p.is_symlink()
h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==hashlib.sha256((bundle/'hardware/a11-mlp.dtbo').read_bytes()).hexdigest()
p.rename(archive/p.name)
run=bundle/'run-v1';assert not (run/'s2').exists();run.rename(archive/'failed-precompute-run-v1')
(archive/'RECORD.json').write_text(json.dumps(dict(status='MATCHING_STALE_DTBO_ARCHIVED',sha256=h,PL_operations=0)))
print(json.dumps(dict(status='MATCHING_STALE_DTBO_ARCHIVED',sha256=h,PL_operations=0)))
'''
r=subprocess.run(['sudo','-n','python3','-B','-I','-c',code],capture_output=True,text=True,timeout=10)
print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True);print('__A12_UPLOAD_END__',flush=True)
