"""Independent closeout readback and tiny evidence archive; no signals or hardware mutations."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

OLD=Path('/var/lib/kv260-a12/step07-single-20261023-v1')
NEW=Path('/var/lib/kv260-a12/step07-finalize-20261024-v1')
CENTRAL=Path('/var/lock/kv260-a1')


def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    for i in range(50):
        if (NEW/'controller-exit.json').exists() or (NEW/'STOP.json').exists():break
        time.sleep(.2)
    observed={p.name:p.read_text() for p in NEW.iterdir() if p.is_file() and p.suffix=='.json'}
    if not (NEW/'controller-exit.json').exists():
        print(json.dumps(dict(status='CONTROLLER_NOT_EXITED_READONLY_STATE',files=observed)),flush=True);return
    assert json.loads((NEW/'controller-exit.json').read_text())['exit_code']==0,observed
    assert not (NEW/'STOP.json').exists(),observed
    manifest=json.loads((OLD/'manifest.json').read_text());assert hashlib.sha256((OLD/'manifest.json').read_bytes()).hexdigest()=='c3bdb07de4e97cd74c03e62b718b558bdf5aba79b9dd118b452c2a710969f64d'
    pins={r['path']:r for r in manifest['files']}
    for n in ('accelerator_release_gate_v2.py','kernel_log_gate.py'):
        p=OLD/'control/support'/n;assert hashlib.sha256(p.read_bytes()).hexdigest()==pins['control/support/'+n]['sha256']
    sys.path.insert(0,str(OLD/'control/support'))
    from accelerator_release_gate_v2 import collect,require_no_users
    from kernel_log_gate import KernelLogGate
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();old=json.loads((OLD/'stopped-snapshot-v1.json').read_text())
    gate=KernelLogGate();assert gate.observe(boot,old['kernel_raw'],old['kernel_sha256'])['allowed']
    raw=subprocess.check_output(['dmesg','--raw']);kr=gate.observe(boot,raw.decode());assert kr['allowed']
    scans=[]
    for i in range(4):
        s=collect(allow_ps_display=True);scans.append(s)
        try:require_no_users(s,True,boot_id=boot)
        except RuntimeError:
            if i==3:raise
            time.sleep(.15)
        else:break
    assert not Path('/sys/module/zocl').exists() and not (CENTRAL/'active').exists()
    oldexit=json.loads((OLD/'manager-exit.json').read_text());assert oldexit==dict(pid=27132,exit_code=-9)
    assert not Path('/proc/27132').exists() and not Path('/proc/27125').exists()
    lockraw=Path('/proc/locks').read_text();locks={}
    for path in (CENTRAL/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock'),CENTRAL/'a12-finalize-coordinator.lock'):
        st=path.stat();key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);rows=[]
        for l in lockraw.splitlines():
            for part in l.split():
                if part.count(':')==2:
                    try:a,b,c=part.split(':');identity=(int(a,16),int(b,16),int(c))
                    except ValueError:continue
                    if identity==key:rows.append(l)
        locks[str(path)]=rows
    assert not any(locks.values())
    archive=CENTRAL/'history/a12-single-gate-20261023-v1-finalized-20261024-v1'
    assert hashlib.sha256((archive/'lease.json').read_bytes()).hexdigest()==old['lease_sha256']
    gdm=subprocess.check_output(['systemctl','is-active','gdm']).decode().strip();assert gdm=='active'
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
    assert overlays=={'k26-starter-kits_image_1':'applied'}
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    result=dict(status='PASS_INDEPENDENT_FINALIZE_ONLY_NO_DEVICE_USERS_LOCKS_OR_ACTIVE_LEASE',
       boot_id=boot,kernel=os.uname().release,scans=scans,locks=locks,old_manager_exit=oldexit,
       controller_exit=json.loads((NEW/'controller-exit.json').read_text()),
       old_wrapper_absent=True,old_manager_absent=True,ZOCL_absent=True,active_lease=False,
       GDM_active=True,overlays=overlays,fpga_state='operating',lease_archive=str(archive),lease_sha256=old['lease_sha256'],
       kernel_raw=raw.decode(),kernel_gate=kr,new_computation=0,PL_or_driver_mutations=0,
       resource=dict(memory_raw=Path('/proc/meminfo').read_text(),temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]))
    with (NEW/'independent-readback-v1.json').open('x') as f:json.dump(result,f,indent=2)
    package=NEW/'readback-v1.tar.gz'
    with package.open('xb') as f:
        with tarfile.open(fileobj=f,mode='w:gz',compresslevel=1) as tar:
            for p in sorted(NEW.iterdir()):
                if p.is_file() and p!=package:tar.add(p,arcname=p.name,recursive=False)
            tar.add(OLD/'manager-exit.json',arcname='old-manager-exit.json',recursive=False)
    dest=Path('/home/ubuntu/a12-step07-finalize-20261024-v1.tar.gz')
    with package.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst)
    os.chown(dest,1000,1000);os.chmod(dest,0o600)
    print(json.dumps(dict(status=result['status'],controller_exit=result['controller_exit'],old_manager_exit=oldexit,
       package=dict(bytes=package.stat().st_size,sha256=hashlib.sha256(package.read_bytes()).hexdigest(),download=str(dest))),),flush=True)


if __name__=='__main__':main()
