import hashlib,json,os,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/step08-diagnostic-20261024-v1')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()=='6291710c7c9d33e66b919f73bb5c0a5d37093e2927737c7d887ede78563d3b7a'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert not (root/'run-v1').exists()
(root/'STEP08_DIAGNOSTIC_LAUNCH_RESERVED').touch(exist_ok=False)
wrapper="import json,subprocess,os\nfrom pathlib import Path\nroot=Path('/var/lib/kv260-a12/step08-diagnostic-20261024-v1')\nwith (root/'manager.stdout.jsonl').open('x') as out,(root/'manager.stderr.txt').open('x') as err:\n p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'control/step08_manager.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)\n with (root/'manager-pid.json').open('x') as f:json.dump(dict(pid=p.pid,wrapper_pid=os.getpid()),f)\n rc=p.wait()\n with (root/'manager-exit.json').open('x') as f:json.dump(dict(pid=p.pid,exit_code=rc),f)\n"
p=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(status='STEP08_DIAGNOSTIC_MANAGER_DISPATCHED_ONCE',wrapper_pid=p.pid)),flush=True)
