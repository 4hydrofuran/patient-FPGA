import subprocess,sys,time,json
from pathlib import Path
p=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
(p/'launch-reservation').touch(exist_ok=False)
wrapper="""import subprocess,json,os
from pathlib import Path
p=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
out=(p/'host.stdout.jsonl').open('xb');err=(p/'host.stderr.txt').open('xb')
c=subprocess.Popen(['/usr/bin/python3','-B','-I',str(p/'launch_mlp_once.py'),'8422f92f-d01f-4849-ad19-6e66b640a9ad'],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
with (p/'launcher-pid.json').open('x') as f:json.dump(dict(pid=c.pid,wrapper_pid=os.getpid()),f)
rc=c.wait();out.close();err.close()
with (p/'host-exit.json').open('x') as f:json.dump(dict(exit_code=rc,pid=c.pid),f)
"""
c=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(wrapper_pid=c.pid,status='LAUNCHED_ONCE_NO_RETRY')),flush=True)
for i in range(90):
 if (p/'host-exit.json').exists() or (p/'STOP.json').exists():break
 time.sleep(.5)
print(json.dumps({n:(p/n).read_text() for n in ('host-exit.json','worker-result.json','STOP.json','host.stderr.txt') if (p/n).exists()}))
