import subprocess,json
code=r'''
import hashlib,json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/original-pl-20261026-v1');bundle=root/'bundle'
assert os.uname().release=='6.8.12-a10irq2' and not Path('/sys/module/zocl').exists()
assert not Path('/var/lock/kv260-a1/active').exists()
assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
archive=root/'precompute-staging-history';archive.mkdir(mode=0o700);records=[]
for name in ('a11-mlp.bit.bin','a11-mlp.dtbo'):
    p=Path('/lib/firmware')/name;source=bundle/'hardware'/name
    old=hashlib.sha256(p.read_bytes()).hexdigest();assert old==hashlib.sha256(source.read_bytes()).hexdigest()
    records.append(dict(path=str(p),sha256=old,symlink=p.is_symlink(),resolved=str(p.resolve())))
    p.rename(archive/name)
run=bundle/'run-v1';assert not (run/'s2').exists()
run.rename(archive/'failed-precompute-run-v1')
(archive/'RECORD.json').write_text(json.dumps(dict(status='MATCHING_STALE_FIRMWARE_ARCHIVED_NO_COMPUTE_OR_PL_OPERATION',files=records),indent=2))
print(json.dumps(dict(status='MATCHING_STALE_FIRMWARE_ARCHIVED_NO_COMPUTE_OR_PL_OPERATION',files=records)))
'''
r=subprocess.run(['sudo','-n','python3','-B','-I','-c',code],capture_output=True,text=True,timeout=20)
print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True);print('__A12_UPLOAD_END__',flush=True)
