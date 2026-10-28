"""Assembly template: zero-compute inventory, exact waiting-owner retirement, lease archival."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

OLD=Path('/var/lib/kv260-a12/step07-single-20261023-v1')
NEW=Path('/var/lib/kv260-a12/step07-finalize-20261024-v1')
CENTRAL=Path('/var/lock/kv260-a1')
LOCKS=(CENTRAL/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock'))


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,r):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.flush();os.fsync(f.fileno())


def lock_rows(path):
    st=path.stat();key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);rows=[]
    for line in Path('/proc/locks').read_text().splitlines():
        parts=line.split()
        for part in parts:
            if part.count(':')!=2:continue
            try:a,b,c=part.split(':');identity=(int(a,16),int(b,16),int(c))
            except ValueError:continue
            if identity==key:rows.append(dict(raw=line,pid=int(parts[4]),kind=parts[1],mode=parts[3]))
    return rows


class Context:
    def __init__(self,e,output=None):
        self.e=e;self.output=output;self.events=[]
        assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2'
        assert digest('/etc/machine-id')==e['machine_sha256']
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==e['boot_id']
        assert digest(OLD/'manifest.json')==e['manifest_sha256']
        m=load(OLD/'manifest.json');pins={r['path']:r for r in m['files']}
        for name in ('accelerator_release_gate_v2.py','kernel_log_gate.py','isolated_idle_policy.py','idle_board_trial.py'):
            p=OLD/'control/support'/name;assert digest(p)==pins['control/support/'+name]['sha256']
        for name in ('control/step07_manager.py','platform/qwen35/a12/window.py'):
            assert digest(OLD/name)==pins[name]['sha256']
        for name,pin in e['output_pins'].items():assert digest(OLD/name)==pin
        sys.path.insert(0,str(OLD/'control/support'))
        from accelerator_release_gate_v2 import collect,require_no_users,start_ticks
        from kernel_log_gate import KernelLogGate
        from isolated_idle_policy import BOOT_FILES,LIBRARIES
        from idle_board_trial import RESTORE
        self.collect=collect;self.require_no_users=require_no_users;self.start_ticks=start_ticks
        for name,pin in {**BOOT_FILES,**LIBRARIES}.items():assert digest(name)==pin
        for name,pin in RESTORE.items():assert digest(Path('/lib/firmware/xilinx/k26-starter-kits')/name)==pin
        self.gate=KernelLogGate();baseline=load(OLD/'stopped-snapshot-v1.json')
        assert self.gate.observe(e['boot_id'],baseline['kernel_raw'],baseline['kernel_sha256'])['allowed']
        self.record('HISTORICAL_PINS_AND_PLATFORM_FILES_VERIFIED',hardware_operations=0)

    def record(self,event,**row):
        r=dict(event=event,monotonic_ns=time.monotonic_ns(),**row);self.events.append(r)
        if self.output:
            with (self.output/'events.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(r)+'\n');f.flush();os.fsync(f.fileno())

    def kernel(self):
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.e['boot_id']
        p=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3);assert p.returncode==0 and not p.stderr
        raw=p.stdout.decode('utf-8');r=self.gate.observe(self.e['boot_id'],raw)
        self.record('KERNEL_OBSERVATION',raw_log=raw,**r)
        return r['allowed']

    def devices(self):
        assert not Path('/sys/module/zocl').exists()
        scan=complete_scan(self.collect,self.require_no_users,self.e['boot_id'],self.kernel,self.record)
        overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
        assert overlays=={'k26-starter-kits_image_1':'applied'}
        assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating'
        assert subprocess.check_output(['systemctl','is-active','gdm.service']).strip()==b'active'
        assert Path('/etc/dfx-mgrd/default_firmware').read_text().strip()=='k26-starter-kits'
        temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
        assert temps and all(0<v<55000 for v in temps) and mem['MemAvailable']>=1048576 and mem['CmaFree']>=32768
        return dict(scan=scan,overlays=overlays,temperatures_mC=temps,
                    memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree')},default_restored=True,kernel_allowed=True)

    def snapshot(self):
        device=self.devices();e=self.e;proc=Path('/proc')/str(e['manager_pid'])
        assert self.start_ticks(proc)==e['manager_start_ticks']
        cmd=(proc/'cmdline').read_bytes().split(b'\0');assert cmd==[b'/usr/bin/python3',b'-B',b'-I',str(OLD/'control/step07_manager.py').encode(),b'']
        status=(proc/'status').read_text();state=next(l for l in status.splitlines() if l.startswith('State:')).split()[1]
        maps=(proc/'maps').read_text();tasks=list((proc/'task').iterdir())
        children={p.name:(p/'children').read_text() for p in tasks}
        fds={p.name:os.readlink(p) for p in (proc/'fd').iterdir()}
        expected_fds={'0':'/dev/null','1':str(OLD/'manager.stdout.jsonl'),'2':str(OLD/'manager.stderr.txt'),
                      '3':str(OLD/'run-v1/lifecycle.jsonl'),'4':str(LOCKS[0]),'5':str(LOCKS[1])}
        exits={name:load(OLD/'run-v1'/name/'exit.json') for name in ('s1','s2')}
        lease=CENTRAL/'active/lease.json';assert digest(lease)==e['lease_sha256'];lr=load(lease)
        assert lr['pid']==e['manager_pid'] and lr['owner_start_ticks']==e['manager_start_ticks']
        assert lr['window']=='a12-single-gate-20261023-v1' and lr['scope']=='l0_gate'
        rows={str(p):lock_rows(p) for p in LOCKS}
        out=dict(boot_id=e['boot_id'],machine_sha256=digest('/etc/machine-id'),manager_pid=e['manager_pid'],
          manager_start_ticks=self.start_ticks(proc),lease_sha256=digest(lease),manifest_sha256=digest(OLD/'manifest.json'),
          no_device_users=True,no_manager_devices=fds==expected_fds,
          no_manager_XRT=('libxrt_' not in maps and 'libsp_linear_a12_trial' not in maps),
          no_manager_children=all(not v.strip() for v in children.values()),single_sleeping_thread=(len(tasks)==1 and state=='S'),
          source_pins_match=True,workers_normal_exit=all(r['exit_code']==0 for r in exits.values()),
          default_restored=device['default_restored'],kernel_allowed=device['kernel_allowed'],ZOCL_absent=True,module_refcount=None,
          old_manager_owns_both_locks=all(len(v)==1 and v[0]['pid']==e['manager_pid'] and v[0]['kind']=='FLOCK' and v[0]['mode']=='WRITE' for v in rows.values()),
          known_parked_code=load(OLD/'run-v1/s2/ISOLATED.json')['reason']=='RuntimeError: PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT',
          manager_cmdline=[v.decode() for v in cmd],manager_status=status,manager_maps=maps,manager_fds=fds,
          children=children,locks=rows,lease=lr,worker_exits=exits,device=device,observed_monotonic_ns=time.monotonic_ns())
        validate_retirement(out,e);self.record('PARKED_OWNER_FULL_INVENTORY_VERIFIED',snapshot=out)
        return out


def execute(e):
    signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
    os.umask(0o077);locks=[];guard=None;ctx=None
    try:
        ctx=Context(e,NEW)
        guard=os.open(CENTRAL/'a12-finalize-coordinator.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with os.fdopen(os.dup(guard),'r') as f:
            st=os.fstat(f.fileno());assert st.st_uid==0 and not st.st_mode&0o022
        pidfd=os.pidfd_open(e['manager_pid'],0)
        snapshot=ctx.snapshot();save(NEW/'before-retirement.json',snapshot)
        retire_once(pidfd,snapshot,e,ctx.record);os.close(pidfd)
        # No unlock of somebody else's OFD. Kernel closed retired owner's FDs;
        # take the canonical locks ourselves while the old lease still blocks admissions.
        for path in LOCKS:
            fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(fd)
        ctx.record('CANONICAL_LOCKS_ACQUIRED_BY_FINALIZER',pid=os.getpid())
        assert all(len(lock_rows(p))==1 and lock_rows(p)[0]['pid']==os.getpid() for p in LOCKS)
        exitpath=OLD/'manager-exit.json'
        for i in range(50):
            if exitpath.exists():break
            time.sleep(.1)
        oldexit=load(exitpath);assert oldexit['pid']==e['manager_pid'] and oldexit['exit_code']==-9
        # A wrapper that reaped the owner naturally completes itself; never signal it.
        wrapper=load(OLD/'manager-pid.json')['wrapper_pid']
        for i in range(50):
            if not Path('/proc',str(wrapper)).exists():break
            time.sleep(.1)
        assert not Path('/proc',str(wrapper)).exists(),'old wrapper still present'
        final=ctx.devices();save(NEW/'before-archive.json',dict(device=final,old_manager_exit=oldexit,wrapper_absent=True))
        active=CENTRAL/'active';assert digest(active/'lease.json')==e['lease_sha256']
        target=CENTRAL/'history/a12-single-gate-20261023-v1-finalized-20261024-v1'
        assert not os.path.lexists(target)
        save(NEW/'recovery-receipt.json',dict(status='RECOVERY_NO_DEVICE_OWNER_RETIREMENT_NOT_NORMAL_OLD_EXIT',
            old_manager_exit=oldexit,method='identity_bound_pidfd_SIGKILL_after_quiescence',hardware_operations=0,
            new_computation=0,worker_normal_exit_preserved=True,old_lease_sha256=e['lease_sha256'],archive=str(target)))
        active.rename(target)
        ctx.record('ORIGINAL_ISOLATION_LEASE_ARCHIVED_UNCHANGED',archive=str(target),sha256=digest(target/'lease.json'))
        assert digest(target/'lease.json')==e['lease_sha256']
        for fd in reversed(locks):os.close(fd)
        locks=[]
        assert not (CENTRAL/'active').exists() and not any(lock_rows(p) for p in LOCKS)
        final=ctx.devices()
        save(NEW/'result.json',dict(status='PASS_FINALIZE_ONLY_OLD_MANAGER_ABNORMAL_EXIT_PRESERVED',
            old_manager_exit=oldexit,new_computation=0,hardware_operations=0,default_restored=True,
            active_lease=False,canonical_locks_held=False,old_manager_absent=not Path('/proc',str(e['manager_pid'])).exists(),
            old_wrapper_absent=True,archive=str(target),lease_sha256=digest(target/'lease.json'),final=final))
        os.close(guard);guard=None
        print(json.dumps(dict(status='PASS_FINALIZE_ONLY_OLD_MANAGER_ABNORMAL_EXIT_PRESERVED')),flush=True)
    except BaseException as exc:
        save(NEW/'STOP.json',dict(reason=type(exc).__name__+': '+str(exc),new_computation=0,
           canonical_lock_fds_before_exit=len(locks),no_retry_signal=True,
           active_lease_preserved=(CENTRAL/'active/lease.json').exists(),
           disposition='No hardware owned by this controller. Close only its own descriptors; preserve isolation lease/evidence for a fresh reconciliation.'))
        for fd in reversed(locks):os.close(fd)
        if guard is not None:os.close(guard)
        raise


def main(mode,e):
    if mode=='preflight':
        c=Context(e);snapshot=c.snapshot()
        print(json.dumps(dict(status='PASS_READONLY_EXACT_PARKED_OWNER_PREFLIGHT',snapshot=snapshot,events=c.events)),flush=True)
    elif mode=='execute':execute(e)
    else:raise ValueError('unsupported closeout mode')
