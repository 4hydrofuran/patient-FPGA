"""Current-boot root read-only inventory. No recovery/config/module/service writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def read(p):
    try:return dict(value=Path(p).read_text(errors='replace'),error=None)
    except OSError as exc:return dict(value=None,error=type(exc).__name__+': '+str(exc))
def command(argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=5)
        return dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
    except (OSError,subprocess.TimeoutExpired) as exc:return dict(exit_code=None,error=type(exc).__name__+': '+str(exc))
def listing(p):
    try:return [dict(name=x.name,bytes=x.stat().st_size,is_dir=x.is_dir(),symlink=x.is_symlink()) for x in sorted(Path(p).iterdir())]
    except OSError as exc:return dict(error=type(exc).__name__+': '+str(exc))
assert os.geteuid()==0 and sha('/etc/machine-id')==MACHINE
r=dict(scope='NEW_BOOT_READ_ONLY_ROOT_SCENE_NO_MUTATION',uid=os.getuid(),machine_sha256=MACHINE,
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
    observed_monotonic_ns=time.monotonic_ns(),cmdline=read('/proc/cmdline'),device_tree_model=read('/proc/device-tree/model'),
    device_tree_compatible=read('/proc/device-tree/compatible'),memory=read('/proc/meminfo'),modules=read('/proc/modules'),
    installed_modules=listing('/lib/modules'),boot_files=listing('/boot'),firmware_boot_files=listing('/boot/firmware'),
    ip_link=command(['ip','-br','link']),ip_addr=command(['ip','-4','-br','addr']),ip_route=command(['ip','-4','route']),
    macb_modinfo=command(['modinfo','-k',os.uname().release,'macb']),net_devices={},boot_configs={},task_files={},locks={})
for p in Path('/sys/class/net').iterdir():
    r['net_devices'][p.name]=dict(address=read(p/'address'),state=read(p/'operstate'),carrier=read(p/'carrier'),device_driver=str((p/'device/driver').resolve()))
for name in ('/boot/extlinux/extlinux.conf','/boot/firmware/extlinux/extlinux.conf','/etc/dfx-mgrd/default_firmware','/etc/vart.conf'):
    r['boot_configs'][name]=read(name)
for name in ('manifest.json','stage-receipt.json','run-v1/review.json','run-v1/s2/ISOLATED.json','recovery-v1/result.json'):
    p=ROOT/name
    if p.is_file():r['task_files'][name]=dict(bytes=p.stat().st_size,sha256=sha(p),value=json.loads(p.read_text()))
active=Path('/var/lock/kv260-a1/active/lease.json')
r['active_lease']=dict(sha256=sha(active),value=json.loads(active.read_text())) if active.exists() else None
raw=Path('/proc/locks').read_text()
for name in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
    p=Path(name)
    if not p.exists():r['locks'][name]=None;continue
    st=p.stat();identity='%02x:%02x:%d'%(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
    r['locks'][name]=dict(inode=st.st_ino,device=st.st_dev,matching_rows=[line for line in raw.splitlines() if identity in line])
r['old_PIDs']={str(pid):(Path('/proc')/str(pid)).exists() for pid in (167484,167575)}
r['old_window_processes']=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        argv=(p/'cmdline').read_bytes().split(b'\0')
        if any(str(ROOT).encode() in a for a in argv):r['old_window_processes'].append(dict(pid=int(p.name),argv=[a.decode(errors='replace') for a in argv if a],stat=(p/'stat').read_text()))
    except OSError:pass
r['kernel_log']=command(['dmesg','--raw'])
r['services']={name:command(['systemctl','is-active',name]) for name in ('gdm.service','ssh.service','NetworkManager.service','systemd-networkd.service')}
overlay=Path('/sys/kernel/config/device-tree/overlays')
r['overlays']={p.name:read(p/'status') for p in overlay.iterdir() if p.is_dir()} if overlay.exists() else None
r['fpga_state']=read('/sys/class/fpga_manager/fpga0/state');r['zocl_present']=Path('/sys/module/zocl').exists();r['zocl_refcount']=read('/sys/module/zocl/refcnt')
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True)
print(json.dumps(r),flush=True)
print('__TT10_UART_ROOT_SCENE_END__',flush=True)
