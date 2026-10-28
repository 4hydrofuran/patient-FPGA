"""Prepare exact detached finalizer; no board connection during generation."""
import base64
import gzip
import json
from common import ROOT,sha

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


if __name__=='__main__':
    pins=json.loads((OUT/'SCRIPT_PINS.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'platform/qwen35/a12/step07_finalize_policy.py')==pins['policy_sha256']
    assert sha(ROOT/'platform/qwen35/a12/step07_finalize_board.py')==pins['board_template_sha256']
    code=(OUT/'execute_reviewed.py').read_bytes();assert sha(OUT/'execute_reviewed.py')==pins['execute_sha256']
    wrapper='''import subprocess,json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/step07-finalize-20261024-v1')
with (root/'controller.stdout.txt').open('x') as out,(root/'controller.stderr.txt').open('x') as err:
 p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'controller.py')],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
 with (root/'controller-pid.json').open('x') as f:json.dump(dict(pid=p.pid,wrapper_pid=os.getpid()),f)
 rc=p.wait()
 with (root/'controller-exit.json').open('x') as f:json.dump(dict(pid=p.pid,exit_code=rc),f)
'''
    launch='''import base64,gzip,hashlib,json,os,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/step07-finalize-20261024-v1')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert not os.path.lexists(root)
assert root.parent.stat().st_uid==0 and not root.parent.stat().st_mode&0o022
payload=gzip.decompress(base64.b64decode(PAYLOAD));assert hashlib.sha256(payload).hexdigest()==PIN
os.umask(0o077);root.mkdir(mode=0o700)
with (root/'controller.py').open('xb') as f:f.write(payload)
wrapper=WRAPPER
p=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',wrapper],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True)
print(json.dumps(dict(status='DETACHED_FINALIZE_ONLY_DISPATCHED',wrapper_pid=p.pid,hardware_operations=0)),flush=True)
'''.replace('PAYLOAD',repr(base64.b64encode(gzip.compress(code)).decode())).replace('==PIN','=='+repr(pins['execute_sha256'])).replace('wrapper=WRAPPER','wrapper='+repr(wrapper))
    with (OUT/'launch_reviewed.py').open('x',encoding='utf-8',newline='\n') as f:f.write(launch)
    print('Verified detached closeout launch prepared; zero new computation')
