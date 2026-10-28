"""Fresh read-only identity/scene capture before an authorized TT10-01 recovery.

No signals, lock acquisition/release, writes, module, service or PL operations.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def optional(p):
    p=Path(p)
    return p.read_text() if p.is_file() else None
def capture_process(pid):
    p=Path('/proc')/str(pid);answer=dict(pid=pid)
    try:
        answer.update(stat=(p/'stat').read_text(),argv=(p/'cmdline').read_bytes().split(b'\0')[:-1],
            status=(p/'status').read_text(),wchan=(p/'wchan').read_text(),executable_sha256=sha(p/'exe'),
            maps=(p/'maps').read_text(),fds={d.name:os.readlink(d) for d in (p/'fd').iterdir()},
            children=(p/'task'/str(pid)/'children').read_text(),threads=sorted(t.name for t in (p/'task').iterdir()))
        answer['argv']=[x.decode('utf-8',errors='replace') for x in answer['argv']]
    except (OSError,ValueError) as exc:answer['observation_error']=type(exc).__name__+': '+str(exc)
    return answer

assert os.geteuid()==0 and os.uname().machine=='aarch64'
assert sha('/etc/machine-id')==MACHINE,'Registered machine identity differs; no mutation'
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
result=dict(event='TT10_01_FRESH_RECOVERY_SCENE_READ_ONLY',machine_sha256=MACHINE,boot_id=boot,kernel=os.uname().release,
    started_monotonic_ns=time.monotonic_ns(),processes=[],files={},module_present=Path('/sys/module/zocl').exists(),
    module_refcount=optional('/sys/module/zocl/refcnt'),memory=Path('/proc/meminfo').read_text(),
    fpga_state=optional('/sys/class/fpga_manager/fpga0/state'),dfx_state_exists=Path('/state.txt').exists(),
    staged_window_exists=Path('/lib/firmware/xilinx/a12-tt10-01-20261024-v1').exists())
root=Path('/sys/kernel/config/device-tree/overlays')
result['overlays']={p.name:optional(p/'status') for p in root.iterdir() if p.is_dir()} if root.exists() else None
for name in ('manifest.json','stage-receipt.json','run-v1/review.json','run-v1/result.json','run-v1/s2/ISOLATED.json','run-v1/s1/exit.json','recovery-v1/result.json'):
    p=ROOT/name
    if p.is_file():result['files'][name]=dict(sha256=sha(p),bytes=p.stat().st_size,value=json.loads(p.read_text()))
active=Path('/var/lock/kv260-a1/active/lease.json')
result['active_lease']=dict(sha256=sha(active),value=json.loads(active.read_text())) if active.is_file() else None
locks=Path('/proc/locks').read_text();result['canonical_locks']={}
for name in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
    p=Path(name)
    if not p.exists():result['canonical_locks'][name]=None;continue
    st=p.stat();needle='%02x:%02x:%d'%(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino)
    result['canonical_locks'][name]=dict(inode=st.st_ino,device=st.st_dev,matching_rows=[s for s in locks.splitlines() if needle in s])
pids=set()
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:argv=(p/'cmdline').read_bytes().split(b'\0')
    except (OSError,ProcessLookupError):continue
    if any(str(ROOT).encode() in a for a in argv):pids.add(int(p.name))
if result['active_lease']:pids.add(result['active_lease']['value']['pid'])
for pid in sorted(pids):
    row=capture_process(pid);result['processes'].append(row)
    for child in row.get('children','').split():
        if int(child) not in pids:result['processes'].append(capture_process(int(child)))
for name in ('s1','s2'):
    folder=ROOT/'run-v1'/name/'worker';result['files'][name+'_worker']=dict(exists=folder.exists())
    for file in ('stdout.jsonl','events.jsonl'):
        p=folder/file
        if p.exists():
            lines=p.read_text().splitlines();result['files'][name+'_worker'][file]=dict(bytes=p.stat().st_size,last=json.loads(lines[-1]) if lines else None)
service=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True,timeout=3)
result['gdm']=dict(exit_code=service.returncode,stdout=service.stdout,stderr=service.stderr)
kernel=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
result['kernel_log']=dict(exit_code=kernel.returncode,stderr=kernel.stderr.decode(errors='replace'),raw=kernel.stdout.decode('utf-8',errors='strict'),sha256=hashlib.sha256(kernel.stdout).hexdigest())
if (ROOT/'control/support/accelerator_release_gate_v2.py').exists():
    sys.path.insert(0,str(ROOT/'control/support'))
    try:
        from accelerator_release_gate_v2 import collect
        result['release_scan']=collect(allow_ps_display=True)
    except Exception as exc:result['release_scan_error']=type(exc).__name__+': '+str(exc)
result['finished_monotonic_ns']=time.monotonic_ns()
result['recovery_archive']={}
archive=Path('/var/lock/kv260-a1/history/a12-tt10-01-20261024-v1-priorboot-abnormal-20261025-v1/lease.json')
result['recovery_archive']=dict(path=str(archive),sha256=sha(archive),bytes=archive.stat().st_size,value=json.loads(archive.read_text()))
recovery=Path('/var/lib/kv260-a12/recovery-20261025-stale-lease-v2')
result['recovery_records']={name:json.loads((recovery/name).read_text()) for name in ('before.json','baseline-review.json','archive-reserved.json','result.json')}
result['boot_maintenance']={name:json.loads((Path('/var/lib/kv260-a12/recovery-20261025-boot-once-v1')/name).read_text()) for name in ('reboot-reserved.json','reboot-command.json')}
print(json.dumps(result),flush=True)
