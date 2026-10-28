"""One explicitly authorized normal reboot, no lease finalization or computation."""
import fcntl,hashlib,json,os,stat,subprocess,sys,time
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
OUT=Path('/var/lib/kv260-a12/recovery-20261025-boot-once-v1')
BOOT='d6d3b16f-f78c-4efa-acaa-14fc8b076fe8'
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
LEASE=Path('/var/lock/kv260-a1/active/lease.json')
LEASE_SHA='568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7'
PINS={'image.fit':'23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
      'boot.scr.uimg':'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
      'a10-candidate-irq2-20261021.fit':'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'}
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def save(name,obj):
    with (OUT/name).open('x') as f:json.dump(obj,f);f.write('\n');f.flush();os.fsync(f.fileno())
def trusted(p):
    s=Path(p).lstat()
    assert s.st_uid==0 and not stat.S_ISLNK(s.st_mode) and not s.st_mode&0o022,str(p)
    return s
assert os.geteuid()==0 and sha('/etc/machine-id')==MACHINE
assert os.uname().release=='6.8.0-1036-xilinx'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert sha(LEASE)==LEASE_SHA and not OUT.exists()
assert sha(ROOT/'control/support/accelerator_release_gate_v2.py')=='1db0bfbac7623309a922c0a56978b0bd3d519a68904884d86d578ef872363668'
sys.path.insert(0,str(ROOT/'control/support'))
from accelerator_release_gate_v2 import collect
OUT.mkdir(mode=0o700)
fds=[]
try:
    trusted('/var/lock/kv260-a1');trusted('/var/lock/kv260-a1/active')
    for name,create in (('/var/lock/kv260-a1/a12-finalize-coordinator.lock',False),
                        ('/var/lock/kv260-a1/deployment.lock',False),
                        ('/run/lock/patient-qwen-linear.lock',True)):
        p=Path(name)
        # Only the volatile canonical lock absent in the read-only audit may be created.
        flags=os.O_RDWR|os.O_NOFOLLOW|(os.O_CREAT|os.O_EXCL if create else 0)
        fd=os.open(p,flags,0o600);fds.append(fd);s=os.fstat(fd)
        assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022 and s.st_nlink==1
        assert p.lstat().st_ino==s.st_ino and p.lstat().st_dev==s.st_dev
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert sha(LEASE)==LEASE_SHA
    assert not Path('/sys/module/zocl').exists()
    assert not Path('/lib/firmware/xilinx/a12-tt10-01-20261024-v1').exists()
    overlay=Path('/sys/kernel/config/device-tree/overlays')
    assert {p.name:(p/'status').read_text().strip() for p in overlay.iterdir() if p.is_dir()}=={'k26-starter-kits_image_1':'applied'}
    assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
    assert subprocess.check_output(['systemctl','is-active','gdm.service']).strip()==b'active'
    temperatures=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    assert temperatures and all(0<t<55000 for t in temperatures)
    for name,pin in PINS.items():assert sha(Path('/boot/firmware')/name)==pin,name
    for p in Path('/proc').iterdir():
        if not p.name.isdecimal():continue
        try:a=(p/'cmdline').read_bytes().split(b'\0')
        except FileNotFoundError:raise RuntimeError('Process disappeared during reboot preflight')
        assert not any(str(ROOT).encode() in x for x in a),'Old-window process still present'
    scan=collect(allow_ps_display=True)
    assert scan['scan_complete'] and scan['boot_id']==BOOT and scan['boot_id_after']==BOOT
    assert not scan['scan_issues'] and not scan['device_holders'] and not scan['device_mappings']
    raw=subprocess.check_output(['dmesg','--raw'])
    assert hashlib.sha256(raw).hexdigest()=='9191287a4b763164d6010168548d6c8a5242ae1ea0f9903e7d84e17f9ec1e6f4','Current recovery scene changed'
    # This exact diagnosed log is retained, NOT accepted by the compute/release gate.
    save('before.json',dict(boot_id=BOOT,kernel=os.uname().release,scan=scan,temperatures=temperatures,
         lease_sha256=LEASE_SHA,boot_hashes=PINS,compute_gate='BLOCKED',purpose='USER_AUTHORIZED_ONE_NORMAL_RECOVERY_REBOOT'))
    assert sha(LEASE)==LEASE_SHA and Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
    save('reboot-reserved.json',dict(command=['/usr/bin/systemctl','reboot'],max_commands=1,
         lease_modified=False,compute_runs=0,pl_loads=0,normal_release_claimed=False))
    print(json.dumps(dict(event='AUTHORIZED_ONE_NORMAL_REBOOT_RESERVED',boot_id=BOOT)),flush=True)
    result=subprocess.run(['/usr/bin/systemctl','reboot'],capture_output=True,text=True,timeout=10)
    save('reboot-command.json',dict(exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr))
    assert result.returncode==0,'No retry or reset'
    # Keep all three locks until shutdown terminates this process. No second command.
    for _ in range(120):time.sleep(1)
    raise RuntimeError('Normal reboot not observed before deadline; no retry')
except Exception as exc:
    save('stopped.json',dict(error=type(exc).__name__+': '+str(exc),retry=False))
    raise
finally:
    for fd in reversed(fds):os.close(fd)
