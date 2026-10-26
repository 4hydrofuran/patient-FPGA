"""Exactly one explicitly authorized normal reboot after fresh root no-device/lock gates."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

BOOT='76c8aef5-8266-4404-a6e5-e17005103da6'
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

if __name__=='__main__':
    assert os.geteuid()==0 and os.uname().release=='6.8.0-1036-xilinx'
    assert sha('/etc/machine-id')==MACHINE and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
    pins={'/boot/firmware/image.fit':'23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
       '/boot/firmware/boot.scr.uimg':'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
       '/boot/firmware/a10-candidate-irq2-20261021.fit':'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'}
    assert all(sha(p)==v for p,v in pins.items())
    frozen=Path('/var/lib/kv260-a11/a11-mlp-20261023-v3')
    assert sha(frozen/'manifest.json')=='64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde'
    manifest=json.loads((frozen/'manifest.json').read_text())
    for n in ('accelerator_release_gate_v2.py','isolated_idle_policy.py','kernel_log_gate.py'):
        assert sha(frozen/n)==manifest['files'][n]['sha256']
    sys.path.insert(0,str(frozen))
    from accelerator_release_gate_v2 import collect,require_no_users
    locks=[]
    for path in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        assert os.fstat(fd).st_uid==0
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(fd)
    scans=[]
    for i in range(4):
        s=collect(allow_ps_display=True);scans.append(s)
        try:require_no_users(s,True,boot_id=BOOT)
        except RuntimeError:
            if s.get('device_holders') or s.get('device_mappings') or i==3:raise
            time.sleep(.15)
        else:break
    temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    assert temps and all(0<t<55000 for t in temps)
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    assert (Path('/sys/kernel/config/device-tree/overlays')/'k26-starter-kits_image_1/status').read_text().strip()=='applied'
    assert not Path('/var/lock/kv260-a1/active').exists()
    out=Path('/var/lib/kv260-a12/step08-restore-20261024-v1');out.mkdir(mode=0o700)
    with (out/'pre-reboot.json').open('x') as f:
        json.dump(dict(boot_id=BOOT,machine_sha256=MACHINE,kernel=os.uname().release,
           scans=scans,pins=pins,temperatures_mC=temps,locks_exclusively_held=True,reboot_authorized=True,
           model_submissions=0,default_boot_files_changed=False),f);f.flush();os.fsync(f.fileno())
    print('A12_ROOT_REBOOT_GATES_PASSED_EXCLUSIVE_NORMAL_REBOOT_ONCE',flush=True)
    r=subprocess.run(['/usr/bin/systemctl','reboot'],capture_output=True)
    with (out/'reboot-command.json').open('x') as f:
        json.dump(dict(argv=['/usr/bin/systemctl','reboot'],exit_code=r.returncode),f);f.flush();os.fsync(f.fileno())
    assert r.returncode==0
    # Keep our lock descriptions until shutdown; never issue a second power action.
    while True:time.sleep(1)
