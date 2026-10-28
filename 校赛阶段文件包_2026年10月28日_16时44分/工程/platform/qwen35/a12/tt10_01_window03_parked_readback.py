"""Read-only snapshot of the exact failed v3 owner; never finalize or signal it."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile
import time

ROOT=Path('/var/lib/kv260-a12/tt10-01-20261025-v3')
BOOT='1d0499ab-f1f9-438c-969a-3e701a0d806f'
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def stamp(path):
    s=path.stat();return dict(device=s.st_dev,inode=s.st_ino,bytes=s.st_size,mtime_ns=s.st_mtime_ns)


def identity(pid):
    p=Path('/proc')/str(pid);raw=(p/'stat').read_text();fields=raw.rsplit(')',1)[1].split()
    return dict(pid=pid,state=fields[0],parent_pid=int(fields[1]),start_ticks=int(fields[19]),
        executable_sha256=digest(p/'exe'),argv=(p/'cmdline').read_bytes().decode().split('\0'),
        wchan=(p/'wchan').read_text(),maps=(p/'maps').read_text(),
        fds={x.name:os.readlink(x) for x in (p/'fd').iterdir()})


assert os.geteuid()==0 and digest('/etc/machine-id')==MACHINE
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
lease_path=Path('/var/lock/kv260-a1/active/lease.json')
lease=json.loads(lease_path.read_text());lease_sha=digest(lease_path)
assert lease['window']=='a12-tt10-01-20261025-v3' and lease['pid']==6365
assert identity(6365)['start_ticks']==lease['owner_start_ticks']
isolated=json.loads((ROOT/'run-v1/s2/ISOLATED.json').read_text())
assert isolated['lease_retained'] and isolated['no_kill']
start=time.monotonic_ns();names=[];inventory={}
for top in ('run-v1','manifest.json','stage-receipt.json','manager-exit.json','manager.stdout.jsonl','manager.stderr.txt','control/preflight.json'):
    p=ROOT/top
    if p.is_dir():names.extend(x for x in p.rglob('*') if x.is_file())
    elif p.is_file():names.append(p)
for p in sorted(set(names)):
    assert not p.is_symlink() and stat.S_ISREG(p.stat().st_mode)
    before=stamp(p);h=digest(p);after=stamp(p)
    inventory[p.relative_to(ROOT).as_posix()]=dict(**before,sha256=h,stable_while_hashed=before==after)
snapshot=dict(event='PARKED_PL_FAILURE_READ_ONLY_SNAPSHOT',started_monotonic_ns=start,
    boot_id=BOOT,kernel=os.uname().release,lease=lease,lease_sha256=lease_sha,
    isolated=isolated,processes=[identity(6365),identity(7023)],
    memory=Path('/proc/meminfo').read_text(),locks=Path('/proc/locks').read_text(),
    module_present=Path('/sys/module/zocl').exists(),
    module_refcount=Path('/sys/module/zocl/refcnt').read_text() if Path('/sys/module/zocl/refcnt').exists() else None,
    overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},
    gdm=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True).stdout,
    no_signals=True,no_hardware_operations=True,no_compute=True,inventory=inventory)
snapshot['kernel_raw_base64']=base64.b64encode(subprocess.check_output(['dmesg','--raw'])).decode()


def include(name):
    selected=any('/'+case+'/diag/' in name for case in ('warm_prefix','diag_full_R0','diag_hit'))
    if selected:
        if name.endswith(('.x.bin','.y.bin')):return False
        if name.endswith('.f32'):
            return name.rsplit('/',1)[-1] in {'logits-decode-0.f32','logits-prefill-106.f32','logits-prefill-69.f32'}
    return True


archive=io.BytesIO();changed=[]
with tarfile.open(fileobj=archive,mode='w:gz') as tar:
    for name,row in inventory.items():
        if include(name):tar.add(ROOT/name,arcname=name,recursive=False)
        p=ROOT/name
        if stamp(p)!={k:row[k] for k in ('device','inode','bytes','mtime_ns')}:changed.append(name)
    snapshot['changed_after_inventory']=changed
    snapshot['finished_monotonic_ns']=time.monotonic_ns()
    snapshot['owner_lease_unchanged']=digest(lease_path)==lease_sha
    assert snapshot['owner_lease_unchanged']
    raw=json.dumps(snapshot,ensure_ascii=False,indent=2).encode()
    entry=tarfile.TarInfo('PARKED_SNAPSHOT.json');entry.size=len(raw);tar.addfile(entry,io.BytesIO(raw))
raw=archive.getvalue()
print(json.dumps(dict(event='READBACK',mode='prefix',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
    base64=base64.b64encode(raw).decode(),snapshot_only=True)),flush=True)
