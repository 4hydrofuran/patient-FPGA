"""Read-only A12 step06 board inventory; no signals, locks, devices, or writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
FROZEN=Path('/var/lib/kv260-a11/a11-mlp-20261023-v3')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and sha('/etc/machine-id')==MACHINE
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert sha(FROZEN/'manifest.json')=='64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde'
    manifest=json.loads((FROZEN/'manifest.json').read_text())
    for name in ('accelerator_release_gate_v2.py','isolated_idle_policy.py','kernel_log_gate.py'):
        assert sha(FROZEN/name)==manifest['files'][name]['sha256']
    sys.path.insert(0,str(FROZEN))
    from accelerator_release_gate_v2 import collect,require_no_users
    from isolated_idle_policy import LOCKS,LIBRARIES
    scans=[]
    for attempt in range(4):
        s=collect(allow_ps_display=True)
        try:require_no_users(s,True,boot_id=boot);s['no_users_gate']=True
        except RuntimeError as e:s['no_users_gate']=False;s['gate_reason']=str(e)
        scans.append(s)
        if s['no_users_gate']:break
        time.sleep(.1)
    locktext=Path('/proc/locks').read_text();locks={}
    for p in LOCKS:
        info=p.stat();wanted=(os.major(info.st_dev),os.minor(info.st_dev),info.st_ino);rows=[]
        for line in locktext.splitlines():
            for field in line.split():
                if field.count(':')==2:
                    try:a,b,c=field.split(':');key=(int(a,16),int(b,16),int(c))
                    except ValueError:continue
                    if key==wanted:rows.append(line)
        locks[str(p)]=rows
    kernel=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
    assert kernel.returncode==0 and not kernel.stderr
    gdm=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True,timeout=3)
    library={name:dict(sha256=sha(name),matches=sha(name)==pin) for name,pin in LIBRARIES.items()}
    roots=(Path('/opt/patient-qwen'),Path('/var/lib/patient-qwen'),Path('/home/ubuntu/Patientqwen'))
    assets={}
    names=('artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf','models/model.lock.json',
           'models/sidecar_A/qwen35-v1/manifest.json','quant/qwen35_tensor_map.json',
           'modules/linear_A/cpu_config.json')
    for root in roots:
        assets[str(root)]={name:(dict(bytes=(root/name).stat().st_size,sha256=sha(root/name))
                                if (root/name).is_file() else None) for name in names}
    overlays=Path('/sys/kernel/config/device-tree/overlays')
    ref=Path('/sys/module/zocl/refcnt')
    result=dict(schema='A12_STEP06_READONLY_PREFLIGHT_V1',boot_id=boot,kernel=os.uname().release,
        machine_sha256=MACHINE,monotonic_ns=time.monotonic_ns(),scans=scans,locks=locks,
        active_lease_exists=Path('/var/lock/kv260-a1/active').exists(),
        module_present=Path('/sys/module/zocl').exists(),module_refcount=int(ref.read_text()) if ref.exists() else None,
        fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
        overlays={p.name:(p/'status').read_text().strip() for p in overlays.iterdir() if p.is_dir()},
        gdm_state=gdm.stdout.strip(),memory_raw=Path('/proc/meminfo').read_text(),
        temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
        library_pins=library,kernel_raw=kernel.stdout.decode('utf-8'),kernel_sha256=hashlib.sha256(kernel.stdout).hexdigest(),
        assets=assets,home_top_level=[p.name for p in Path('/home/ubuntu').iterdir()],
        opt_top_level=[p.name for p in Path('/opt').iterdir()],
        disk=subprocess.check_output(['df','-B1','/opt','/var/lib','/home/ubuntu'],text=True),
        board_mutations=0,accelerator_submissions=0)
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
