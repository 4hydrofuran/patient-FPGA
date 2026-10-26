"""Snapshot parked single-gate results; no signal, unlock, lease edit or PL command."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT=Path('/var/lib/kv260-a12/step07-single-20261023-v1')


def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    sys.path.insert(0,str(ROOT/'control/support'))
    from accelerator_release_gate_v2 import collect,require_no_users,start_ticks
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert (ROOT/'run-v1/s2/ISOLATED.json').is_file() and not (ROOT/'manager-exit.json').exists()
    lease=Path('/var/lock/kv260-a1/active/lease.json');lease_row=json.loads(lease.read_text());pid=lease_row['pid']
    assert lease_row['window']=='a12-single-gate-20261023-v1' and lease_row['identity'].endswith(boot)
    assert json.loads((ROOT/'manager-pid.json').read_text())['pid']==pid
    proc=Path('/proc')/str(pid);assert start_ticks(proc)==lease_row['owner_start_ticks']
    status=(proc/'status').read_text();maps=(proc/'maps').read_text()
    assert 'libxrt_' not in maps and 'libsp_linear_a12_trial' not in maps
    threads={p.name:(p/'children').read_text() for p in (proc/'task').iterdir()};assert all(not v.strip() for v in threads.values())
    fds={}
    for p in (proc/'fd').iterdir():
        try:fds[p.name]=os.readlink(p)
        except FileNotFoundError:continue
    assert not any(v.startswith(('/dev/dri/','/dev/zocl','/dev/xclmgmt','/dev/mem','/dev/uio')) for v in fds.values())
    exits={n:json.loads((ROOT/'run-v1'/n/'exit.json').read_text()) for n in ('s1','s2')}
    assert all(v['exit_code']==0 for v in exits.values()) and exits['s2']['host_permission_runs']==3
    scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=boot)
    assert not Path('/sys/module/zocl').exists()
    gdm=subprocess.check_output(['systemctl','is-active','gdm']).decode().strip();assert gdm=='active'
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    kernel=subprocess.check_output(['dmesg','--raw'])
    snapshot=dict(status='STOPPED_FINALIZATION_OWNER_RETAINED_NO_DEVICE_USERS',boot_id=boot,
        manager_pid=pid,manager_start_ticks=start_ticks(proc),manager_cmdline=(proc/'cmdline').read_bytes().decode(),
        manager_status=status,manager_maps=maps,manager_fds=fds,manager_thread_children=threads,
        manager_exit_code=None,worker_exits=exits,lease=lease_row,lease_sha256=hashlib.sha256(lease.read_bytes()).hexdigest(),
        locks_raw=Path('/proc/locks').read_text(),scan=scan,gdm_state=gdm,module_present=False,
        kernel_raw=kernel.decode(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),
        failure=json.loads((ROOT/'run-v1/s2/ISOLATED.json').read_text()),
        scope='Evidence snapshot only; active lease and both locks retained; no signals or forced cleanup')
    with (ROOT/'stopped-snapshot-v1.json').open('x') as f:json.dump(snapshot,f,indent=2)
    package=ROOT/'stopped-readback-v1.tar.gz'
    with package.open('xb') as out:
        with tarfile.open(fileobj=out,mode='w:gz',compresslevel=1) as tar:
            for p in sorted((ROOT/'run-v1').rglob('*')):
                if p.is_file():tar.add(p,arcname=p.relative_to(ROOT).as_posix(),recursive=False)
            for name in ('stopped-snapshot-v1.json','manager-pid.json','manager.stdout.jsonl','manager.stderr.txt','ldd.txt','manifest.json'):
                tar.add(ROOT/name,arcname=name,recursive=False)
    target=Path('/home/ubuntu/a12-step07-single-stopped-readback-20261023-v1.tar.gz')
    with package.open('rb') as src,target.open('xb') as out:shutil.copyfileobj(src,out)
    os.chown(target,1000,1000);os.chmod(target,0o600)
    h=hashlib.sha256(package.read_bytes()).hexdigest()
    print(json.dumps(dict(status=snapshot['status'],manager_pid=pid,package=dict(bytes=package.stat().st_size,sha256=h,download=str(target)),worker_exits=exits)),flush=True)


if __name__=='__main__':main()
