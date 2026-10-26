import subprocess,json
code=r'''
import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/original-pl-20261026-v1');run=root/'bundle/run-v1'
lease=Path('/var/lock/kv260-a1/active/lease.json')
r=dict(kernel=os.uname().release,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),manager_pid=2907,manager_present=Path('/proc/2907').exists(),lease=json.loads(lease.read_text()) if lease.exists() else None,zocl_present=Path('/sys/module/zocl').exists(),overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},new_model_requests_sent=0,acceptance='FAILED_BEFORE_MODEL_REQUEST',forced_signals=0)
identity=run/'s2/identity.json'
if identity.exists():
    r['worker']=json.loads(identity.read_text());r['worker_present']=Path('/proc',str(r['worker']['pid'])).exists()
r['isolation']=json.loads((run/'s2/ISOLATED.json').read_text())
print(json.dumps(r))
'''
r=subprocess.run(['sudo','-n','python3','-B','-I','-c',code],capture_output=True,text=True,timeout=10)
print('__A12_UPLOAD_BEGIN__',flush=True);print(json.dumps(dict(exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)),flush=True);print('__A12_UPLOAD_END__',flush=True)
