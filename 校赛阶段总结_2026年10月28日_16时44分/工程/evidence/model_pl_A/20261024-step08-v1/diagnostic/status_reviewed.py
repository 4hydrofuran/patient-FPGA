"""Read-only ongoing/final process and lease identity; never a recovery action."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path('/var/lib/kv260-a12/step08-diagnostic-20261024-v1')

def main():
    assert os.geteuid()==0 and hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    sys.path.insert(0,str(ROOT/'control/support'))
    from accelerator_release_gate_v2 import collect,require_no_users
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    from isolated_idle_policy import LOCKS
    import time
    scans=[]
    for i in range(4):
        s=collect(allow_ps_display=True)
        try:require_no_users(s,True,boot_id=boot);s['no_users_gate']=True
        except RuntimeError as e:s['no_users_gate']=False;s['gate_reason']=str(e)
        scans.append(s)
        if s['no_users_gate']:break
        time.sleep(.1)
    rows=Path('/proc/locks').read_text().splitlines();locks={}
    for p in LOCKS:
        st=p.stat();key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);found=[]
        for line in rows:
            for field in line.split():
                if field.count(':')!=2:continue
                try:a,b,c=field.split(':');value=int(a,16),int(b,16),int(c)
                except ValueError:continue
                if value==key:found.append(line)
        locks[str(p)]=found
    names=['manager-pid.json','manager-exit.json','manager.stderr.txt','run-v1/result.json','run-v1/s2/ISOLATED.json']
    files={n:(ROOT/n).read_text() for n in names if (ROOT/n).is_file()}
    pids=[]
    if 'manager-pid.json' in files:
        ids=json.loads(files['manager-pid.json']);pids.extend(ids.values())
    for sub in ('s1','s2'):
        p=ROOT/'run-v1'/sub/'identity.json'
        if p.is_file():pids.append(json.loads(p.read_text())['pid'])
    raw=subprocess.check_output(['dmesg','--raw']);history=Path('/var/lock/kv260-a1/history/a12-full-diagnostic-20261024-v1')
    state=dict(boot_id=boot,kernel=os.uname().release,files=files,scans=scans,locks=locks,
       known_processes_absent={str(p):not Path('/proc',str(p)).exists() for p in pids},
       active_lease_exists=Path('/var/lock/kv260-a1/active').exists(),module_present=Path('/sys/module/zocl').exists(),
       lease_archived=history.is_dir(),lease_sha256=hashlib.sha256((history/'lease.json').read_bytes()).hexdigest() if history.is_dir() else None,
       gdm_state=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True).stdout.strip(),
       fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
       overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},
       kernel_raw=raw.decode(),kernel_sha256=hashlib.sha256(raw).hexdigest(),new_calculation=0,signals=0)
    print(json.dumps(state),flush=True)

if __name__=='__main__':main()
