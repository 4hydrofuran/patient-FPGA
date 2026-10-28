"""Reviewed sequential Python-only A12 profiling; preserve owners on any failure."""
import base64
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

DATA = None
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    with path.open('x',encoding='utf-8') as stream:json.dump(data,stream);stream.write('\n')


def emit(event,**data):print(json.dumps(dict(event=event,**data)),flush=True)


def preflight():
    capture=io.StringIO()
    code=gzip.decompress(base64.b64decode(DATA['preflight']))
    with contextlib.redirect_stdout(capture):exec(compile(code,'cpu01b_fresh_preflight','exec'),{'__name__':'__main__'})
    result=json.loads(capture.getvalue())
    assert result['machine_sha256']==MACHINE and result['kernel']=='6.8.12-a10irq2'
    assert result['scans'][-1]['no_users_gate'] and not result['active_lease_exists'] and not result['module_present']
    assert not any(result['locks'].values()) and result['gdm_state']=='active' and result['fpga_state']=='operating'
    assert result['overlays']=={'k26-starter-kits_image_1':'applied'}
    assert all(item['matches'] for item in result['library_pins'].values())
    return result


def stage(config,fresh):
    parent=Path(DATA['parent']);root=Path(config['remote'])
    assert sha(parent/'manifest.json')==DATA['parent_manifest_sha256']
    assert not os.path.lexists(root)
    previous=json.loads((parent/'manifest.json').read_text())
    for row in previous['files']:
        p=parent/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    root.mkdir(mode=0o700)
    manifest=config['manifest']
    for row in manifest['files']:
        name=row['path'];assert not Path(name).is_absolute() and '..' not in Path(name).parts
        data=gzip.decompress(base64.b64decode(config['delta'][name])) if name in config['delta'] else (parent/name).read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with dest.open('xb') as stream:stream.write(data)
    # Refresh only this reviewed window's preflight, and bind its exact bytes into its manifest.
    path=root/'control/preflight.json'
    path.write_text(json.dumps(fresh,indent=2)+'\n')
    for row in manifest['files']:
        if row['path']=='control/preflight.json':row.update(bytes=path.stat().st_size,sha256=sha(path))
    save(root/'manifest.json',manifest);os.chmod(root/'bin/qwen35-a12',0o700)
    save(root/'stage-receipt.json',dict(status='STAGED_NO_PL_MUTATION',mode=config['mode'],manifest_sha256=sha(root/'manifest.json'),preflight_sha256=sha(path)))
    return root


def readback(root,mode):
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode='w:gz') as tar:
        for name in ('run-v1','manifest.json','stage-receipt.json','manager-exit.json','manager.stdout.jsonl','manager.stderr.txt','independent-postcheck.json','delayed-postcheck.json'):
            path=root/name
            if path.exists():tar.add(path,arcname=name,recursive=True)
    raw=archive.getvalue()
    emit('READBACK',mode=mode,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())


def main():
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2'
    assert sha(Path('/etc/machine-id'))==MACHINE
    os.umask(0o077)
    for config in DATA['configurations']:
        fresh=preflight();emit('FRESH_GATE_PASS',mode=config['mode'],boot_id=fresh['boot_id'])
        root=stage(config,fresh)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_','GGML_','OMP_'))}
        # Manager recreates its original pinned environment before starting a worker.
        with (root/'manager.stdout.jsonl').open('x') as out,(root/'manager.stderr.txt').open('x') as err:
            child=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'control'/config['manager'])],stdin=subprocess.DEVNULL,stdout=out,stderr=err,env=env,start_new_session=True,close_fds=True)
            emit('MANAGER_STARTED',mode=config['mode'],pid=child.pid)
            deadline=time.monotonic()+2100
            while child.poll() is None:
                if time.monotonic()>deadline:
                    emit('STOP_OWNER_RETAINED_NO_SIGNAL',mode=config['mode'],pid=child.pid);return 3
                time.sleep(10)
                cases=[]
                run=root/'run-v1'
                for backend in ('s1','s2'):
                    for name in ('short_profile','natural_plain','natural_profile'):
                        if (run/backend/name/'client-timing.json').exists():cases.append(backend+'/'+name)
                emit('PROGRESS',mode=config['mode'],pid=child.pid,completed=cases)
            save(root/'manager-exit.json',dict(pid=child.pid,exit_code=child.returncode))
        if child.returncode:
            readback(root,config['mode']);emit('STOP_BAD_MANAGER_EXIT',mode=config['mode'],exit_code=child.returncode);return 2
        # Fresh full no-user scans are independent of the manager's completion record.
        independent=preflight();save(root/'independent-postcheck.json',independent)
        time.sleep(3)
        delayed=preflight();save(root/'delayed-postcheck.json',delayed)
        readback(root,config['mode']);emit('WINDOW_NORMAL_RESTORED',mode=config['mode'])
    emit('ALL_WINDOWS_NORMAL_EXIT');return 0


if __name__=='__main__':raise SystemExit(main())
