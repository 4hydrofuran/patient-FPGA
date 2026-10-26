"""PC plans for an additive UART stage and one no-compute diagnostic launch."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/mlp_board_A/20261023-open-investigation-v1'
PACKAGE=OUT/'open-package-v1'
OLD=ROOT/'platform/local/a11-mlp-20261023-v1'
REMOTE='/var/lib/kv260-a11/a11-open-20261023-v1'
UPLOAD='/home/ubuntu/a11-open-upload-20261023-v1'
BOOT='8422f92f-d01f-4849-ad19-6e66b640a9ad'

def sha(b):return hashlib.sha256(b).hexdigest()
def py(code):return '/usr/bin/python3 -B -I -c '+"'"+code.replace("'","'\"'\"'")+"'"
def job(name,command,seconds=8):return dict(name=name,command=command,seconds=seconds)
def put(name,obj):
    with (OUT/name).open('x',encoding='utf-8') as f:json.dump(obj,f,indent=2)

def prepare():
    pin=sha((PACKAGE/'manifest.json').read_bytes())
    # The reviewed launcher preserves exact fresh baseline/boot/bundle/owner gates.
    s=(ROOT/'platform/qwen35/a11/launch_mlp_once.py').read_text()
    s=s.replace('/var/lib/kv260-a11/a11-mlp-20261023-v1',REMOTE)
    s=s.replace('3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c',pin)
    baseline=sha((ROOT/'evidence/mlp_board_A/20261023-final-closeout-v1/readback_01/kernel.raw.txt').read_bytes())
    s=s.replace('1c4e880e36fa39f3bb0c516fac2cea00ce85b03b68969500a8ef190409b78655',baseline)
    s=s.replace('A11_MLP_REVIEW_V1','A11_OPEN_REVIEW_V1').replace('compute_authorized=True','compute_authorized=False').replace('max_submissions=23','max_submissions=0')
    s=s.replace('USER_APPROVED_A11_23_SERIAL_CALLS_55C_NO_STRESS_NO_RETRY_20261023',
                'USER_REQUESTED_ERROR_DIAGNOSIS_20261023_ONE_OPEN_ZERO_SUBMISSIONS')
    s=s.replace('--execute-authorized-mlp-once','--execute-authorized-open-once')
    with (OUT/'launch_open_once.py').open('x') as f:f.write(s)
    files={}
    for p in sorted(PACKAGE.rglob('*')):
        if not p.is_file():continue
        name=p.relative_to(PACKAGE).as_posix();data=p.read_bytes();old=OLD/name
        files[name]=dict(sha256=sha(data),bytes=len(data))
        if old.is_file() and old.read_bytes()==data: files[name]['old']=name
        else: files[name]['base64']=base64.b64encode(data).decode()
    data=(OUT/'launch_open_once.py').read_bytes()
    files['launch_open_once.py']=dict(sha256=sha(data),bytes=len(data),base64=base64.b64encode(data).decode())
    payload=gzip.compress(json.dumps(files,sort_keys=True).encode(),mtime=0)
    with (OUT/'uart_payload.gz').open('xb') as f:f.write(payload)
    blob=base64.b64encode(payload).decode()
    jobs=[job('reserve_upload',py("from pathlib import Path;import os;assert os.getuid()==1000;assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=="+repr(BOOT)+";Path("+repr(UPLOAD)+").mkdir(mode=0o700)"))]
    for i in range(0,len(blob),2800):
        jobs.append(job('chunk_'+str(i//2800),"printf '%s' '"+blob[i:i+2800]+"' >> "+UPLOAD+'/payload.b64'))
    jobs.append(job('sudo_auth','sudo -v',10))
    stage=f'''import base64,gzip,hashlib,json,os
from pathlib import Path
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=={BOOT!r}
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
b=base64.b64decode(Path({(UPLOAD+'/payload.b64')!r}).read_bytes(),validate=True)
assert hashlib.sha256(b).hexdigest()=={sha(payload)!r}
files=json.loads(gzip.decompress(b));out=Path({REMOTE!r});old=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
assert hashlib.sha256((old/'manifest.json').read_bytes()).hexdigest()=='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
os.umask(0o077);out.mkdir(mode=0o700)
for name,row in files.items():
 assert not Path(name).is_absolute() and '..' not in Path(name).parts
 data=(old/row['old']).read_bytes() if 'old' in row else base64.b64decode(row['base64'],validate=True)
 assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
 p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as f:f.write(data)
print(json.dumps(dict(status='STAGED_NO_HARDWARE_ACTION',files=len(files),manifest_sha256=hashlib.sha256((out/'manifest.json').read_bytes()).hexdigest())))
'''
    enc=base64.b64encode(stage.encode()).decode()
    jobs.append(job('root_stage','sudo -n '+py("import base64;exec(compile(base64.b64decode("+repr(enc)+"),'reviewed_stage','exec'))"),12))
    put('stage_jobs.json',jobs)
    # Detached root wrapper records waitpid. A timed-out/parked manager is not killed.
    wrapper=f'''import subprocess,json,os
from pathlib import Path
p=Path({REMOTE!r})
out=(p/'host.stdout.jsonl').open('xb');err=(p/'host.stderr.txt').open('xb')
c=subprocess.Popen(['/usr/bin/python3','-B','-I',str(p/'launch_open_once.py'),{BOOT!r}],stdin=subprocess.DEVNULL,stdout=out,stderr=err,close_fds=True)
with (p/'launcher-pid.json').open('x') as f:json.dump(dict(pid=c.pid,wrapper_pid=os.getpid()),f)
rc=c.wait();out.close();err.close()
with (p/'host-exit.json').open('x') as f:json.dump(dict(exit_code=rc,pid=c.pid),f)
'''
    launch="import subprocess,sys;from pathlib import Path;p=Path("+repr(REMOTE)+");assert not (p/'launch-reservation').exists();(p/'launch-reservation').touch(exist_ok=False);c=subprocess.Popen(['/usr/bin/python3','-B','-I','-c',"+repr(wrapper)+"],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True,close_fds=True);print(c.pid)"
    # Encode to ensure one physical UART line.
    encoded=base64.b64encode(launch.encode()).decode()
    put('launch_jobs.json',[job('sudo_auth','sudo -v',10),job('launch_once','sudo -n '+py('import base64;exec(base64.b64decode('+repr(encoded)+'))'),10)])
    poll="import json;from pathlib import Path;p=Path("+repr(REMOTE)+");names=['launcher-pid.json','host-exit.json','worker-result.json','worker.stderr.txt','host.stderr.txt','STOP.json'];print(json.dumps({n:(p/n).read_text() for n in names if (p/n).exists()}));q=p/'host.stdout.jsonl';print(q.read_text()[-6000:] if q.exists() else '')"
    put('poll_jobs.json',[job('poll_diagnostic','sudo -n '+py(poll),10)])
    print(json.dumps(dict(payload_bytes=len(payload),uart_chunks=(len(blob)+2799)//2800,manifest_sha256=pin,baseline_sha256=baseline)))

if __name__=='__main__':prepare()
