"""Prepare exact detached CPU manager launch and read-only status query."""
import json
from common import sha
from step06_prepare import OUT


if __name__=='__main__':
    manifest_pin=sha(OUT/'deployment-manifest.json')
    launch='''import hashlib,json,os,subprocess,sys
from pathlib import Path
root=Path('/var/lib/kv260-a12/step06-20261023-v1')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256((root/'deployment-manifest.json').read_bytes()).hexdigest()==PIN
m=json.loads((root/'deployment-manifest.json').read_text())
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==m['boot_id']
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
for name,row in m['files'].items():
 if name.startswith(('runtime/','control/')):
  p=root/name;assert p.stat().st_size==row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256']
assert not (root/'run-v1').exists()
(root/'CPU_LAUNCH_RESERVED').touch(exist_ok=False)
wrapper=WRAPPER
p=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
with (root/'wrapper-pid.json').open('x') as f:json.dump(dict(pid=p.pid),f)
print(json.dumps(dict(status='CPU_MANAGER_DISPATCHED_ONCE',wrapper_pid=p.pid,PL_submissions_allowed=0)),flush=True)
'''
    wrapper='''import json,subprocess,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/step06-20261023-v1')
with (root/'manager.stdout.jsonl').open('x') as out,(root/'manager.stderr.txt').open('x') as err:
 p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'control/step06_cpu.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
 with (root/'manager-pid.json').open('x') as f:json.dump(dict(pid=p.pid,wrapper_pid=os.getpid()),f)
 rc=p.wait()
 with (root/'manager-exit.json').open('x') as f:json.dump(dict(pid=p.pid,exit_code=rc),f)
'''
    launch=launch.replace('==PIN','=='+repr(manifest_pin)).replace('wrapper=WRAPPER','wrapper='+repr(wrapper))
    (OUT/'launch_reviewed.py').write_text(launch,encoding='utf-8')
    poll='''import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/step06-20261023-v1')
assert os.geteuid()==0
names=['manager-pid.json','manager-exit.json','manager.stdout.jsonl','manager.stderr.txt',
       'run-v1/worker-identity.json','run-v1/STOP.json','run-v1/ready.json','run-v1/teacher_T8-result.json',
       'run-v1/teacher_T1-result.json','run-v1/natural-result.json','run-v1/result.json']
data={}
for name in names:
 p=root/name
 if p.is_file():
  raw=p.read_text();data[name]=raw if len(raw)<3000 else raw[-3000:]
print(json.dumps(data),flush=True)
'''
    (OUT/'poll_reviewed.py').write_text(poll,encoding='utf-8')
    print('One CPU launch and read-only poll scripts prepared')
