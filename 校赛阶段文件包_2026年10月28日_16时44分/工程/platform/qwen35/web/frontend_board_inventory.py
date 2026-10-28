"""Current-board preparation inventory only; no driver, service, lease or boot writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

def command(argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=8)
    return dict(argv=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

assert os.geteuid()==0
assert sha(Path('/etc/machine-id'))=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
lease=Path('/var/lock/kv260-a1/active/lease.json')
lease_data=json.loads(lease.read_text()) if lease.exists() else None
overlays=Path('/sys/kernel/config/device-tree/overlays')
modules=Path('/usr/lib/modules/6.8.12-a10irq2/extra/zocl.ko')
fit=Path('/boot/firmware/a10-candidate-irq2-20261021.fit')
r=dict(scope='A12_FRONTEND_CURRENT_BOOT_READ_ONLY',machine_sha256=sha(Path('/etc/machine-id')),
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
    active_lease=lease.exists(),lease=None if lease_data is None else {k:lease_data.get(k) for k in ('window','identity','owner','pid','owner_start_ticks','expires_monotonic_ns','scope')},
    zocl_loaded=Path('/sys/module/zocl').exists(),overlays={p.name:(p/'status').read_text().strip() for p in overlays.iterdir() if p.is_dir() and (p/'status').is_file()},
    interfaces=command(['ip','-4','-br','addr']),routes=command(['ip','-4','route']),
    memory_kib={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.split(':')[0] in ('MemTotal','MemAvailable','CmaTotal','CmaFree')},
    irq2_fit=dict(exists=fit.is_file(),bytes=fit.stat().st_size if fit.is_file() else None),
    irq2_zocl=dict(exists=modules.is_file(),sha256=sha(modules) if modules.is_file() else None),
    ssh_public_key=' '.join(Path('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()[:2]),
    ssh_status=command(['systemctl','is-active','ssh.service','ssh.socket']),
    prior_frontend_template=Path('/var/lib/kv260-a12/web-modes-20261027-v2/web_managed.py').is_file(),
    original_frontend=Path('/home/ubuntu/patient-web-demo-20261026/web_gateway/src/patient_web/api.py').is_file(),
    board_contact=True,compute_runs=0,pl_loads=0,reboots=0,mutations=0,status='READ_ONLY_INVENTORY_COMPLETE')
if lease_data:
    pid=lease_data.get('pid');p=Path('/proc')/str(pid)
    r['lease_sha256']=sha(lease)
    r['lease_process']=dict(exists=p.is_dir(),comm=(p/'comm').read_text().strip() if p.is_dir() else None,
        start_ticks=(p/'stat').read_text().rsplit(')',1)[1].split()[19] if p.is_dir() else None)
    locks=Path('/proc/locks').read_text().splitlines();r['canonical_locks']={}
    for name in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
        p=Path(name)
        if p.exists():
            st=p.stat();identity='%02x:%02x:%d'%(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
            r['canonical_locks'][name]=dict(inode=st.st_ino,holders=[line for line in locks if identity in line])
        else:r['canonical_locks'][name]=None
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True)
print(json.dumps(r),flush=True)
print('__TT10_UART_ROOT_SCENE_END__',flush=True)
