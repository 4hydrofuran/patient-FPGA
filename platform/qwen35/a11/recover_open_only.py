"""One specifically authorized recovery of the 20261023 stopped-open window.

Not an A11 test or normal worker exit. No retry, SIGKILL, forced unload, reboot,
device opens, new test loads or native imports. A failed in-flight management
command retains this recovery process/locks for review, never kills the child.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

ROOT = Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
BOOT = '8422f92f-d01f-4849-ad19-6e66b640a9ad'
MANAGER, WORKER = 3202, 3308
TICKS = {MANAGER: 90192, WORKER: 91251}
MANIFEST = '3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
LEASE = '3c13e30e1747b61c4a89296273d614771410e5f06713ce8b208f1f4c20d24a4c'
KLOG = '7c872eec56b90c0c0d1d1b79d1ad930a424e01b5f3245406938b5c921a481967'
LOG_PINS = {
    'lifecycle.jsonl': '8d645605180920158daa83b7cc5dcadfc0f4f4759545ea461114ea3a9a19da03',
    'worker.stdout.jsonl': '13ec17f4b9b16e1348934ba4ee4d22870bee305f9639086a9a0e8c58561d46aa',
    'STOP.json': 'ca4670e5a3f73439ea5b01859babc80a3a773f167eed2d5a3e822da0487654dc',
}


def need(ok, why):
    if not ok:
        raise RuntimeError(why)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def validate_history(files):
    for name, pin in LOG_PINS.items():
        need(sha(files[name]) == pin, 'stopped history changed: '+name)
    rows = [json.loads(line) for line in files['lifecycle.jsonl'].splitlines()]
    permits = [r for r in rows if r['event'] == 'NEXT_OPERATION_PERMITTED']
    need(len(permits) == 1 and permits[0]['phase'] == 'open' and permits[0]['job'] == 0,
         'not proven pre-submission failure')
    need(rows[-1]['event'] == 'QUARANTINED_MANAGER_AND_LOCKS_RETAINED', 'manager not quarantined')
    worker = [json.loads(line) for line in files['worker.stdout.jsonl'].splitlines()]
    need([r['event'] for r in worker] == ['PERMIT_AND_HEALTH','WORKER_PARKED_NO_CLOSE'] and
         worker[-1]['reason'] == 'RuntimeError: open failed status=8', 'different worker stop')


def validate_process(pid, stat, status, cmdline, wchan, threads, children):
    fields = stat.rsplit(')', 1)[1].split()
    need(pid in TICKS and int(fields[19]) == TICKS[pid], 'PID/start time changed')
    need(fields[0] == 'S' and wchan == 'hrtimer_nanosleep' and threads == [str(pid)], 'not isolated sleeping waiter')
    values = dict(line.split(':',1) for line in status.splitlines())
    need(values['Uid'].split() == ['0']*4 and values['TracerPid'].strip() == '0', 'UID/tracer differs')
    bit = 1 << (signal.SIGUSR1-1)
    need(all(not int(values[k].strip(),16) & bit for k in ('SigBlk','SigIgn','SigCgt')), 'SIGUSR1 not default/unblocked')
    need(all(int(values[k].strip(),16) == 0 for k in ('SigPnd','ShdPnd')), 'pending signal')
    prefix = ['/usr/bin/python3','-B','-I',str(ROOT/('mlp_worker.py' if pid == WORKER else 'mlp_manager_entry.py'))]
    need(cmdline[:4] == prefix, 'unexpected program')
    if pid == WORKER:
        need(int(fields[1]) == MANAGER and children == [], 'worker parent/children differ')
    else:
        need(children == [WORKER], 'manager children differ')


def cleanup_sequence(io):
    """Exception at any step forbids every following mutation; no retries."""
    io.preflight()
    io.terminate(WORKER)
    io.release_gate('worker_exited_manager_still_owns_locks', True)
    io.terminate(MANAGER)
    io.claim_cleanup_locks()
    io.release_gate('cleanup_locks_acquired', True)
    io.remove_test()
    io.release_gate('test_removed', True)
    io.unload_module()
    io.release_gate('module_removed', False)
    io.load_default()
    io.release_gate('default_loaded', False)
    io.start_graphics()
    io.finish()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-cleanup-only', action='store_true')
    args = ap.parse_args()
    if not args.execute_authorized_cleanup_only:
        print(json.dumps(dict(mode='PLAN_ONLY',boot_id=BOOT,compute=0,pids=[WORKER,MANAGER])))
        return 0
    need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and os.uname().release == '6.8.12-a10irq2', 'platform differs')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'boot differs')
    need(sha((ROOT/'manifest.json').read_bytes()) == MANIFEST, 'bundle changed')
    manifest = json.loads((ROOT/'manifest.json').read_text())
    for name, entry in manifest['files'].items():
        path = ROOT/name
        need(not path.is_symlink() and path.resolve().is_relative_to(ROOT) and
             path.stat().st_size == entry['bytes'] and sha(path.read_bytes()) == entry['sha256'], 'payload changed')
    # Only hash-verified, non-native collectors/policies are imported.
    sys.path.insert(0, str(ROOT))
    from accelerator_release_gate_v2 import collect, require_release, require_no_users
    from isolated_idle_policy import CENTRAL, DEFAULT, LOCKS, MACHINE, BOOT_FILES, LIBRARIES, trusted_file, digest, lock_owned
    from idle_board_trial import Trial, RESTORE, active_handle, check_removed
    from mlp_kernel_gate import MinimalGate

    class Recovery(Trial):
        boot = BOOT
        kernel_release = '6.8.12-a10irq2'
        temperature_limit_mC = 55000
        memory_reserve_KiB = 1048576

        def __init__(self):
            self.source = ROOT
            self.held = []
            self.pidfds = {}
            self.changed = False
            self.kernel_gate = MinimalGate()
            self.dest = ROOT/'recovery-only-20261023-v1'
            self.archive = CENTRAL/'history/a11-mlp-20261023-v1-aborted-open'
            for p in (ROOT, CENTRAL, CENTRAL/'active', CENTRAL/'active/lease.json', *LOCKS): trusted_file(p)
            need(digest('/etc/machine-id') == MACHINE, 'wrong board')
            need(not os.path.lexists(self.dest) and not os.path.lexists(self.archive), 'cleanup already reserved/consumed')
            self.dest.mkdir(mode=0o700)
            self.log = (self.dest/'lifecycle.jsonl').open('x')
            self.emit('RECOVERY_RESERVED',scope='USER_ALLOWED_CLEANUP_ONLY',pid=os.getpid(),
                      start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),normal_worker_exit=False)

        def emit(self, event, **data):
            row = dict(event=event,monotonic_ns=time.monotonic_ns(),**data)
            self.log.write(json.dumps(row)+'\n');self.log.flush();os.fsync(self.log.fileno())
            print(json.dumps({k:row[k] for k in ('event','pid','exit_code','phase','reason') if k in row}),flush=True)

        def kernel_checkpoint(self, phase, mutation=None):
            need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'boot changed')
            p = subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3)
            need(p.returncode == 0 and not p.stderr, 'kernel unavailable')
            raw = p.stdout.decode('utf-8')
            action = 'load_default' if mutation == ['dfx-mgr-client','-load',DEFAULT] and phase == 'after_mutation' else 'none'
            if self.kernel_gate.previous is None:
                need(sha(p.stdout) == KLOG, 'baseline changed; fresh review required')
            result = self.kernel_gate.observe_action(BOOT,raw,KLOG,action)
            self.emit('KERNEL_GATE',phase=phase,raw_log=raw,**result)
            need(result['allowed'], 'new/unreviewed kernel diagnostic')

        def stopped_history(self):
            validate_history({n:(ROOT/n).read_bytes() for n in LOG_PINS})
            need(digest(CENTRAL/'active/lease.json') == LEASE, 'lease changed')
            need(not (ROOT/'worker-result.json').exists() and not (ROOT/'mlp-receipt.json').exists(), 'unexpected result')
            need((ROOT/'worker.stderr.txt').read_bytes() == b'' and not list((ROOT/'outputs').iterdir()), 'unexpected output')
            need(sorted(p.name for p in (ROOT/'permits').iterdir()) == ['allow-001.json','ready-001.json'], 'new permit')
            need((ROOT/'permits/allow-001.json').read_bytes() == (ROOT/'permits/ready-001.json').read_bytes(), 'permit mismatch')

        def process(self, pid):
            p = Path('/proc')/str(pid)
            validate_process(pid,(p/'stat').read_text(),(p/'status').read_text(),
                (p/'cmdline').read_bytes().decode().rstrip('\0').split('\0'),(p/'wchan').read_text().strip(),
                sorted(q.name for q in (p/'task').iterdir()),
                [int(v) for v in (p/'task'/str(pid)/'children').read_text().split()])
            maps = (p/'maps').read_text()
            allowed = {str(ROOT/n) for n in ('lifecycle.jsonl','worker.stdout.jsonl','worker.stderr.txt')}
            allowed |= {str(q) for q in LOCKS}|{'/dev/pts/0','/dev/null'}
            fds = {q.name:os.readlink(q) for q in (p/'fd').iterdir()}
            need(set(fds.values()) <= allowed, 'unexpected process FD')
            if pid == MANAGER:
                need('libxrt_' not in maps and '/dev/' not in maps, 'manager owns native/device mapping')
                need(all(lock_owned(q,MANAGER) for q in LOCKS), 'manager locks changed')
            self.emit('EXACT_PROCESS_RECHECKED',pid=pid,maps=maps,fds=fds,status=(p/'status').read_text())

        def pins(self):
            for path, pin in {**BOOT_FILES,**LIBRARIES}.items():need(digest(path) == pin,'platform pin changed')
            for name,pin in RESTORE.items():need(digest(Path('/lib/firmware/xilinx')/DEFAULT/name) == pin,'default asset changed')
            need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT,'default setting changed')

        def preflight(self):
            self.stopped_history();self.pins();self.kernel_checkpoint('before_signals')
            need(Path('/sys/module/zocl/srcversion').read_text().strip() == '15F2AC2306CB3CB7257CFCB','different driver')
            initial = self.snapshot('cleanup_initial');self.initial_vart=initial['vart_sha256']
            need(initial['overlays'] == {ROOT.name+'_image_1':'applied'} and initial['module_refcount'] == 1,'changed PL/refcount')
            gdm = subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,timeout=3)
            need(gdm.stdout.strip() == b'inactive','graphics no longer isolated')
            for pid in (WORKER,MANAGER):
                self.pidfds[pid] = os.pidfd_open(pid,0)
                self.process(pid)
                need(not select.select([self.pidfds[pid]],[],[],0)[0], 'process already exited')
            scan = collect(allow_ps_display=True)
            self.emit('INITIAL_DEVICE_SCAN',scan=scan)
            need(scan['scan_complete'] and not scan['scan_issues'] and not scan['device_holders'] and
                 len(scan['device_mappings']) == 1 and scan['device_mappings'][0]['pid'] == WORKER,'unexpected device user')
            row = scan['device_mappings'][0]['map'].split()
            lo,hi = [int(v,16) for v in row[0].split('-')]
            need(hi-lo == 65536 and row[2] == 'b0000000' and row[-1] == '/dev/dri/renderD128','mapping changed')

        def terminate(self,pid):
            self.stopped_history();self.kernel_checkpoint('before_signal_'+str(pid))
            self.process(pid)
            need(not select.select([self.pidfds[pid]],[],[],0)[0],'waiter already exited')
            self.emit('SIGNAL_BEGIN',pid=pid,signal='SIGUSR1',normal_exit=False)
            self.changed=True
            signal.pidfd_send_signal(self.pidfds[pid],signal.SIGUSR1,None,0)
            need(bool(select.select([self.pidfds[pid]],[],[],3)[0]),'exit unconfirmed; no second signal')
            self.emit('PIDFD_EXIT_CONFIRMED',pid=pid,normal_exit=False)
            time.sleep(.5)  # passive settlement, never a retry or new signal
            self.kernel_checkpoint('after_signal_'+str(pid))

        def claim_cleanup_locks(self):
            import fcntl
            need(all(select.select([fd],[],[],0)[0] for fd in self.pidfds.values()),'old process exit unconfirmed')
            need(digest(CENTRAL/'active/lease.json') == LEASE,'lease changed during handover')
            for path in LOCKS:
                fd=os.open(path,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC);self.held.append(fd)
                fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            need(all(lock_owned(path,os.getpid()) for path in LOCKS),'cleanup lock ownership unproven')
            self.emit('RECOVERY_LOCKS_ACQUIRED',pid=os.getpid(),original_active_lease_retained=True)

        def release_gate(self,phase,loaded):
            self.kernel_checkpoint('before_scan_'+phase)
            scan=collect(allow_ps_display=True)
            ref=Path('/sys/module/zocl/refcnt')
            count=int(ref.read_text()) if ref.exists() else None
            self.kernel_checkpoint('after_scan_'+phase)
            self.emit('RELEASE_OBSERVATION',phase=phase,scan=scan,module_refcount=count)
            if loaded:require_release(scan,count,not self.kernel_gate.blocked,boot_id=BOOT)
            else:
                need(count is None and not Path('/sys/module/zocl').exists(),'module still present')
                require_no_users(scan,not self.kernel_gate.blocked,boot_id=BOOT)

        def command(self,argv,state_changing=False):
            permitted = [ ['dfx-mgr-client','-listPackage'],['rmmod','zocl'],['dfx-mgr-client','-load',DEFAULT] ]
            remove = len(argv)==3 and argv[:2]==['dfx-mgr-client','-remove'] and argv[2].isascii() and argv[2].isdigit()
            need(argv in permitted or remove,'command outside cleanup scope')
            need(all(lock_owned(path,os.getpid()) for path in LOCKS),'cleanup locks lost')
            if state_changing:self.snapshot('health_before_mutation')
            return super().command(argv,state_changing)

        def remove_test(self):
            self.release_gate('immediately_before_remove',True)
            handle=active_handle(self.command(['dfx-mgr-client','-listPackage']),ROOT.name)
            self.command(['dfx-mgr-client','-remove',handle],True)
            check_removed(self.snapshot('test_removed'),True)

        def unload_module(self):
            self.command(['rmmod','zocl'],True)
            check_removed(self.snapshot('module_removed'),False)

        def load_default(self):
            self.command(['dfx-mgr-client','-load',DEFAULT],True)
            self.default_state()

        def default_state(self):
            s=self.snapshot('default_restored')
            need(s['overlays']=={DEFAULT+'_image_1':'applied'} and s['module_refcount'] is None and
                 not s['zocl_bound'] and not s['render_nodes'] and not s['accelerator_card_nodes'] and
                 s['fpga_state']=='operating' and s['vart_sha256']==self.initial_vart,'default restoration differs')
            return s

        def start_graphics(self):
            self.kernel_checkpoint('before_gdm_start')
            p=subprocess.Popen(['systemctl','start','gdm.service'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:out,err=p.communicate(timeout=30)
            except subprocess.TimeoutExpired:
                self.park('GDM_START_UNKNOWN_NO_KILL')
            self.emit('GDM_START',exit_code=p.returncode,stdout=out.decode(),stderr=err.decode())
            need(p.returncode==0,'GDM start failed')
            self.kernel_checkpoint('after_gdm_start')

        def finish(self):
            self.pins();state=self.default_state()
            gdm=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,timeout=3)
            need(gdm.returncode==0 and gdm.stdout.strip()==b'active','GDM not restored')
            self.release_gate('final',False)
            need(digest(CENTRAL/'active/lease.json')==LEASE and not os.path.lexists(self.archive),'archive precondition differs')
            trusted_file(CENTRAL/'history')
            need((CENTRAL/'active').resolve()==CENTRAL.resolve()/'active' and
                 self.archive.parent.resolve()==CENTRAL.resolve()/'history','archive target escapes')
            (CENTRAL/'active').rename(self.archive)
            result=dict(status='RECOVERY_COMPLETE_REQUIRES_INDEPENDENT_READBACK',boot_id=BOOT,final=state,
                abnormal_worker_termination=True,normal_worker_exit=False,signals='one SIGUSR1 per pinned worker/manager',
                compute_runs=0,A11='NOT_PASSED',gdm_state='active',lease_archive=str(self.archive))
            with (self.dest/'result.json').open('x') as f:json.dump(result,f,indent=2);f.flush();os.fsync(f.fileno())
            self.emit('RECOVERY_COMPLETE',result=result)
            for fd in reversed(self.held):os.close(fd)
            self.held.clear()
            for fd in self.pidfds.values():os.close(fd)

        def park(self,reason):
            self.emit('RECOVERY_STOPPED_NO_RETRY',reason=reason,locks_retained=bool(self.held))
            while True:time.sleep(30)

    signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
    os.umask(0o077)
    recovery=Recovery()
    try:cleanup_sequence(recovery)
    except BaseException as exc:
        if recovery.held:recovery.park(type(exc).__name__+': '+str(exc))
        recovery.emit('RECOVERY_STOPPED_NO_RETRY',reason=type(exc).__name__+': '+str(exc),locks_retained=False)
        return 2
    return 0


if __name__=='__main__':raise SystemExit(main())
