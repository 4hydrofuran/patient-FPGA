"""Read-only current boot, stale lease, canonical paths, boot packages audit."""
import hashlib,json,os,stat,subprocess,sys
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT='d6d3b16f-f78c-4efa-acaa-14fc8b076fe8'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def command(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return dict(argv=a,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
assert os.geteuid()==0 and sha('/etc/machine-id')==MACHINE
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert os.uname().release=='6.8.0-1036-xilinx'
sys.path.insert(0,str(ROOT/'control/support'))
from kernel_log_gate import diagnostics,digest
from accelerator_release_gate_v2 import collect
r=dict(machine_sha256=MACHINE,boot_id=BOOT,kernel=os.uname().release,
    active_inventory={},canonical_paths={},boot_files={},support_hashes={},commands=[],temperatures={})
for name in ('accelerator_release_gate_v2.py','kernel_log_gate.py'):
    r['support_hashes'][name]=sha(ROOT/'control/support'/name)
active=Path('/var/lock/kv260-a1/active')
for p in sorted(active.rglob('*')):
    st=p.lstat();item=dict(mode=st.st_mode,uid=st.st_uid,gid=st.st_gid,inode=st.st_ino,device=st.st_dev,symlink=p.is_symlink())
    if stat.S_ISREG(st.st_mode):item.update(bytes=st.st_size,sha256=sha(p))
    r['active_inventory'][str(p.relative_to(active))]=item
for name in ('/var/lock/kv260-a1','/var/lock/kv260-a1/active','/var/lock/kv260-a1/history',
             '/var/lock/kv260-a1/deployment.lock','/run/lock','/run/lock/patient-qwen-linear.lock',
             '/var/lock/kv260-a1/a12-finalize-coordinator.lock'):
    p=Path(name)
    if not p.exists():r['canonical_paths'][name]=None;continue
    st=p.lstat();r['canonical_paths'][name]=dict(mode=st.st_mode,uid=st.st_uid,gid=st.st_gid,inode=st.st_ino,device=st.st_dev,symlink=p.is_symlink(),resolved=str(p.resolve()))
for n in ('image.fit','boot.scr.uimg','a10-candidate-irq2-20261021.fit'):
    p=Path('/boot/firmware')/n;r['boot_files'][n]=dict(bytes=p.stat().st_size,sha256=sha(p))
raw=subprocess.check_output(['dmesg','--raw']).decode()
r['kernel_raw']=raw;r['kernel_sha256']=digest(raw);r['kernel_diagnostics']=diagnostics(raw)
r['scan']=collect(allow_ps_display=True)
for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input'):
    r['temperatures'][str(p)]=int(p.read_text())
for argv in (['findmnt','-n','-o','SOURCE,TARGET,FSTYPE,OPTIONS','--target','/boot/firmware'],
             ['df','-k','/','/boot/firmware'],['ip','-4','-br','addr'],['ip','-4','route'],
             ['busctl','--timeout=3','call','org.freedesktop.NetworkManager',
              '/org/freedesktop/NetworkManager/Settings','org.freedesktop.NetworkManager.Settings',
              'GetConnectionByUuid','s','bf6e1c82-2a97-4698-a913-3993a03f3bd7']):
    r['commands'].append(command(argv))
print(json.dumps(r),flush=True)
