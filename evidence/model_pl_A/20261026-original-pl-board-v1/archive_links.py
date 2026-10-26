import subprocess,json
code=r'''
import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/original-pl-20261026-v1');bundle=root/'bundle'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
archive=root/'precompute-staging-history';assert archive.is_dir() and not list(archive.iterdir())
records=[]
for name in ('a11-mlp.bit.bin','a11-mlp.dtbo'):
    p=Path('/lib/firmware')/name
    assert p.is_symlink() and not p.exists()
    target=os.readlink(p);assert target.startswith('/lib/firmware/xilinx/') and target.endswith('/'+name)
    records.append(dict(path=str(p),target=target,dangling=True,link_bytes_preserved=True));p.rename(archive/name)
run=bundle/'run-v1';assert not (run/'s2').exists();run.rename(archive/'failed-precompute-run-v1')
(archive/'RECORD.json').write_text(json.dumps(dict(status='DANGLING_TEST_LINKS_ARCHIVED_NO_PL_OPERATION',files=records),indent=2))
print(json.dumps(dict(status='DANGLING_TEST_LINKS_ARCHIVED_NO_PL_OPERATION',files=records)))
'''
r=subprocess.run(['sudo','-n','python3','-B','-I','-c',code],capture_output=True,text=True,timeout=20)
print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True);print('__A12_UPLOAD_END__',flush=True)
