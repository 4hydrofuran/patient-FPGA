"""Reviewed resource-only correction: evict our deployment-archive cache, retain files."""
import base64
import hashlib
import json
from pathlib import Path
from common import ROOT
from step06_prepare import OUT


if __name__=='__main__':
    s=(ROOT/'platform/qwen35/a12/step06_cpu.py').read_text()
    s=s.replace("out=root/'run-v1'","out=root/'run-v2'")
    s=s.replace('a12-step06-cpu-20261023-v1','a12-step06-cpu-20261023-v2')
    s=s.replace("requests=json.loads((root/'control/requests.json').read_text());results=[]",
       "requests=[dict(json.loads((root/'control/requests.json').read_text())[0],diagnostic=False)];results=[]")
    pin=hashlib.sha256(s.encode()).hexdigest();(OUT/'step06_cpu_resource_v2.py').write_text(s)
    script='''import base64,hashlib,json,os,stat,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/step06-20261023-v1')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert json.loads((root/'manager-exit.json').read_text())['exit_code']==0
assert not (root/'run-v2').exists()
def memory():
 return {l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.split(':')[0] in ('MemAvailable','CmaFree','Cached')}
before=memory();files=[]
for p in (Path('/home/ubuntu/a12-step06-20261023-v1.tar'),root/'readback-v1.tar.gz',Path('/home/ubuntu/a12-step06-readback-20261023-v1.tar.gz')):
 st=p.lstat();assert stat.S_ISREG(st.st_mode) and not p.is_symlink()
 fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
 try:os.fsync(fd);os.posix_fadvise(fd,0,0,os.POSIX_FADV_DONTNEED)
 finally:os.close(fd)
 files.append(dict(path=str(p),bytes=st.st_size,content_unchanged=True))
cache=dict(before=before,after=memory(),files=files,scope='Only this task deployment/readback archives; no drop_caches or model-page eviction')
with (root/'archive-cache-review-v2.json').open('x') as f:json.dump(cache,f,indent=2)
code=base64.b64decode(PAYLOAD);assert hashlib.sha256(code).hexdigest()==PIN
source=root/'control/step06_cpu_resource_v2.py'
with source.open('xb') as f:f.write(code)
wrapper=WRAPPER
p=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(status='RESOURCE_ONLY_V2_DISPATCHED',wrapper_pid=p.pid,cache=cache)),flush=True)
'''
    wrapper='''import json,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/step06-20261023-v1')
with (root/'manager-v2.stdout.jsonl').open('x') as out,(root/'manager-v2.stderr.txt').open('x') as err:
 p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'control/step06_cpu_resource_v2.py')],stdout=out,stderr=err,stdin=subprocess.DEVNULL)
 with (root/'manager-v2-pid.json').open('x') as f:json.dump(dict(pid=p.pid),f)
 rc=p.wait()
 with (root/'manager-v2-exit.json').open('x') as f:json.dump(dict(pid=p.pid,exit_code=rc),f)
'''
    script=script.replace('PAYLOAD',repr(base64.b64encode(s.encode()).decode())).replace('==PIN','=='+repr(pin)).replace('wrapper=WRAPPER','wrapper='+repr(wrapper))
    (OUT/'resource_revision_reviewed.py').write_text(script)
    # Independent readback reuses the verified implementation with NEW filenames only.
    read=(ROOT/'platform/qwen35/a12/step06_readback.py').read_text()
    read=read.replace('manager-exit.json','manager-v2-exit.json').replace('manager-pid.json','manager-v2-pid.json')
    read=read.replace('manager.stdout.jsonl','manager-v2.stdout.jsonl').replace('manager.stderr.txt','manager-v2.stderr.txt')
    read=read.replace('run-v1','run-v2').replace('readback-v1.tar.gz','readback-v2.tar.gz')
    read=read.replace('a12-step06-readback-20261023-v1.tar.gz','a12-step06-readback-20261023-v2.tar.gz')
    read=read.replace("'ldd.txt','deployment-manifest.json'","'ldd.txt','deployment-manifest.json','archive-cache-review-v2.json'")
    (OUT/'resource_readback_reviewed.py').write_text(read)
    print('Resource-only revision prepared; no math, tolerance, model or binary change')
