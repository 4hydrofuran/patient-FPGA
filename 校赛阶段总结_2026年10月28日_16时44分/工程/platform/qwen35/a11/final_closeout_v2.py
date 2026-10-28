"""One authorized metadata-only closeout. Default PLAN_ONLY.

No accelerator device opens, XRT, PL/module/service mutations or reboot calls.
No resume of the hard-stopped controller, no live patch, no lock-file deletion.
After a failure leave a durable reconciliation record, never another parked
manager. A reserved directory prevents automatic reruns, including after crash.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time

ROOT=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
V3=Path('/var/lib/kv260-a11/cleanup-v3-20261023')
DEST=Path('/var/lib/kv260-a11/final-closeout-20261023-v2')
CENTRAL=Path('/var/lock/kv260-a1')
ARCHIVE=CENTRAL/'history/a11-mlp-20261023-v1-aborted-open'
BOOT='8422f92f-d01f-4849-ad19-6e66b640a9ad'
PID,TICKS=8851,644102
MANIFEST='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
CANDIDATE='e60bba1d6dccbaa8acd3c60e962630e2d7041463f2a478cc7a75bbd6832e9611'
JOURNAL='0af388c64202b494588a680fbbac05836d7a826cc88fda26b76a2f95ad932e21'
KLOG='03a7fe81b253f0a39d76c64e5f8f976434b49aa82c402324519caaa639bd1e32'
LEASE='3c13e30e1747b61c4a89296273d614771410e5f06713ce8b208f1f4c20d24a4c'
EXPECTED_STATUS=dict(state='HARD_STOP_RECONCILE_ONLY',reason='RuntimeError: NON_TRANSIENT_SCAN_ERROR',
    generation=1,next_step='finalize',completed_steps=['takeover','remove_test','unload_module','load_default','start_graphics'],
    inflight=None,compute_runs=0,acceptance='CLEANUP_ONLY_NOT_A11_PASS')


def need(ok,why):
    if not ok:raise RuntimeError(why)


def sha(raw):return hashlib.sha256(raw).hexdigest()


def trusted(path,directory=False):
    s=path.lstat()
    need(not path.is_symlink() and s.st_uid==0 and not s.st_mode&0o022,'untrusted path '+str(path))
    if directory:need(stat.S_ISDIR(s.st_mode),'not directory')


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def write_new(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno())
    sync_dir(path.parent)


def bounded_scan(sample,validate,emit,sleep=time.sleep):
    """Discard known transient snapshots, never pass an incomplete snapshot."""
    for attempt in range(1,5):
        scan=sample();emit('RESOURCE_SCAN',attempt=attempt,scan=scan)
        need(scan.get('boot_id')==BOOT==scan.get('boot_id_after'),'scan boot differs')
        need(scan.get('schema')=='a10-accelerator-scan-v2','scan schema')
        need(scan.get('device_holders')==[] and scan.get('device_mappings')==[],'device owner/unknown')
        if scan.get('scan_complete') is True:
            validate(scan,True,boot_id=BOOT);return scan
        need(scan.get('scan_complete') is False and type(scan.get('scan_issues')) is list and scan['scan_issues'],'unknown incomplete scan')
        for issue in scan['scan_issues']:
            reason=issue.get('reason','')
            missing=re.fullmatch(r"FileNotFoundError: \[Errno 2\] No such file or directory: '/proc/(\d+)/(?:stat|maps|fd(?:/\d+)?)'",reason)
            transient=(reason=='PROCESS_SET_CHANGED' or
                (reason=='ValueError: PROCESS_OR_FD_TABLE_CHANGED' and type(issue.get('pid')) is int and issue['pid']>0) or
                (missing is not None and issue.get('pid')==int(missing.group(1))))
            need(transient,'non-transient scan failure')
        if attempt<4:sleep(.5)
    raise RuntimeError('four incomplete scans; stop without parking or hardware action')


def validate_process(stat_text,status,cmdline,maps,children,threads,fds):
    fields=stat_text.rsplit(')',1)[1].split()
    need(int(stat_text.split(' ',1)[0])==PID and int(fields[19])==TICKS and fields[0]=='S','PID reused/not sleeping')
    info=dict(line.split(':',1) for line in status.splitlines())
    need(info['Uid'].split()==['0']*4 and info['TracerPid'].strip()=='0','uid/tracer differs')
    need(children=='' and threads==[str(PID)],'children/threads remain')
    bit=1 << (signal.SIGUSR1-1)
    need(all(not int(info[k].strip(),16)&bit for k in ('SigBlk','SigIgn','SigCgt')),'signal not default/unblocked')
    need(all(int(info[k].strip(),16)==0 for k in ('SigPnd','ShdPnd')),'pending signal')
    expected=['/usr/bin/python3','-B','-I',str(V3/'cleanup_board_v3.py'),'--execute-authorized-takeover',
        '--authorization-id','user-cleanup-only-20261023-v3-initial','--bundle-sha256',CANDIDATE]
    need(cmdline==expected,'program identity differs')
    need(not any(v in maps for v in ('/dev/','libxrt_','libsp_linear')),'native/device mapping remains')
    need(set(fds)==set('01234567'),'unexpected FD table')
    need(all(re.fullmatch(r'pipe:\[\d+\]',fds[str(i)]) for i in range(3)),'stdio differs')
    need(fds['3']==str(V3/'state/lifecycle.jsonl') and fds['4']=='socket:[39064]' and
         fds['5']=='anon_inode:[pidfd]' and fds['6']==str(CENTRAL/'deployment.lock') and
         fds['7']=='/run/lock/patient-qwen-linear.lock','unexpected FD ownership')


def execute(io):
    """Auditable sequence; failure never replays a signal or metadata mutation."""
    io.preflight()
    io.emit('SIGNAL_BEGIN',pid=PID,signal='SIGUSR1',normal_exit=False)
    io.signal_once()
    io.confirm_exit()
    io.claim_locks()
    io.verify_after_exit()
    io.prepare_record()
    io.archive_lease()
    io.commit_record()
    io.release_locks()
    io.emit('CLOSEOUT_TOOL_COMPLETE',old_supervisor_normal_exit=False,compute_runs=0,A11='NOT_PASSED')


class Closeout:
    def __init__(self):
        self.held=[];self.pidfd=None;self.phase='RESERVED';self.signalled=False
        need(os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2','platform mismatch')
        self.identity()
        for p in reversed(DEST.parent.parents):trusted(p,True)
        trusted(DEST.parent,True)
        need(not os.path.lexists(DEST),'already reserved; read-only reconciliation required')
        os.umask(0o077);DEST.mkdir(mode=0o700);sync_dir(DEST.parent)
        self.log=(DEST/'lifecycle.jsonl').open('x')
        self.emit('CLOSEOUT_RESERVED',pid=os.getpid(),target_pid=PID,target_start_ticks=TICKS,boot_id=BOOT)

    def identity(self):
        need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT,'boot changed')
        need(sha(Path('/etc/machine-id').read_bytes())=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec','machine differs')

    def emit(self,event,**data):
        row=dict(event=event,monotonic_ns=time.monotonic_ns(),**data)
        self.log.write(json.dumps(row)+'\n');self.log.flush();os.fsync(self.log.fileno())
        try:print(json.dumps({k:v for k,v in row.items() if k not in ('scan','raw','process')}),flush=True)
        except OSError:pass

    def readcmd(self,argv):
        need(argv in (['dmesg','--raw'],['systemctl','is-active','gdm.service']),'command not read-only allowlist')
        p=subprocess.run(argv,capture_output=True,timeout=3)
        need(p.returncode==0 and not p.stderr,'read-only command failed')
        return p.stdout

    def load_policy(self):
        need(sha((ROOT/'manifest.json').read_bytes())==MANIFEST,'old bundle changed')
        manifest=json.loads((ROOT/'manifest.json').read_bytes())
        for name,entry in manifest['files'].items():
            p=ROOT/name;trusted(p)
            need(p.resolve().is_relative_to(ROOT) and p.stat().st_size==entry['bytes'] and sha(p.read_bytes())==entry['sha256'],'old payload differs')
        need(sha((V3/'candidate.json').read_bytes())==CANDIDATE,'v3 manifest changed')
        for name,entry in json.loads((V3/'candidate.json').read_bytes())['files'].items():
            p=V3/name;trusted(p);need(sha(p.read_bytes())==entry['sha256'],'v3 payload differs')
        sys.path.insert(0,str(ROOT))
        from accelerator_release_gate_v2 import collect,require_no_users
        from isolated_idle_policy import LOCKS,lock_owned,BOOT_FILES,LIBRARIES
        from idle_board_trial import RESTORE
        from kernel_log_gate import KernelLogGate
        self.collect=collect;self.require=require_no_users;self.locks=LOCKS;self.owns=lock_owned
        self.pins={**BOOT_FILES,**LIBRARIES,**{str(Path('/lib/firmware/xilinx/k26-starter-kits')/n):v for n,v in RESTORE.items()}}
        raw=(V3/'state/lifecycle.jsonl').read_bytes();need(sha(raw)==JOURNAL,'v3 history changed')
        rows=[json.loads(x) for x in raw.splitlines()]
        need(rows[-1]['event']=='CONTROL_HARD_STOP' and all(rows[-1][k]==EXPECTED_STATUS[k] for k in EXPECTED_STATUS if k in rows[-1]),'wrong stop')
        need([r['step'] for r in rows if r['event']=='STEP_BEGIN']==EXPECTED_STATUS['completed_steps'],'uncommitted action')
        baseline=[r['raw_log'] for r in rows if r['event']=='KERNEL_GATE'][-1]
        need(sha(baseline.encode())==KLOG,'baseline differs')
        self.kernel=KernelLogGate();need(self.kernel.observe(BOOT,baseline,KLOG)['allowed'],'baseline gate')

    def kernel_check(self):
        self.identity();raw=self.readcmd(['dmesg','--raw']).decode()
        result=self.kernel.observe(BOOT,raw,KLOG)
        self.emit('KERNEL_CHECK',raw=raw,result=result);need(result['allowed'],'kernel changed/diagnostic')

    def health(self):
        self.identity()
        need(not Path('/sys/module/zocl').exists(),'ZOCL present')
        need(not list(Path('/dev/dri').glob('render*')),'render node remains')
        overlay={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
        need(overlay=={'k26-starter-kits_image_1':'applied'},'default PL differs')
        need(Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()=='operating','FPGA state differs')
        need(self.readcmd(['systemctl','is-active','gdm.service']).strip()==b'active','GDM differs')
        need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip()=='k26-starter-kits','default setting changed')
        for p,pin in self.pins.items():need(sha(Path(p).read_bytes())==pin,'asset changed '+p)
        temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        mem={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
        need(temps and all(0<t<55000 for t in temps),'temperature')
        need(mem['MemAvailable']>=1048576 and mem['CmaFree']>=32768,'memory reserve')
        self.emit('HEALTH',temperatures_mC=temps,memory_kib={k:mem[k] for k in ('MemAvailable','CmaFree')},overlays=overlay)

    def history(self):
        need(sha((V3/'state/lifecycle.jsonl').read_bytes())==JOURNAL,'v3 journal changed')
        need(sha((CENTRAL/'active/lease.json').read_bytes())==LEASE,'lease changed')
        need(not os.path.lexists(ARCHIVE),'archive exists')
        need(not (V3/'state/result.json').exists(),'unexpected v3 result')
        need(not list((ROOT/'outputs').iterdir()),'unexpected outputs')
        need(sorted(p.name for p in (ROOT/'permits').iterdir())==['allow-001.json','ready-001.json'],'new operation permit')
        need((ROOT/'permits/allow-001.json').read_bytes()==(ROOT/'permits/ready-001.json').read_bytes(),'permit differs')
        history_pins={
            'lifecycle.jsonl':'8d645605180920158daa83b7cc5dcadfc0f4f4759545ea461114ea3a9a19da03',
            'worker.stdout.jsonl':'13ec17f4b9b16e1348934ba4ee4d22870bee305f9639086a9a0e8c58561d46aa',
            'STOP.json':'ca4670e5a3f73439ea5b01859babc80a3a773f167eed2d5a3e822da0487654dc'}
        for name,pin in history_pins.items():need(sha((ROOT/name).read_bytes())==pin,'original history changed')
        need(not (ROOT/'worker-result.json').exists() and not (ROOT/'mlp-receipt.json').exists(),'unexpected result')

    def status(self):
        p=V3/'state/control.sock';trusted(p)
        s=p.lstat();need(stat.S_ISSOCK(s.st_mode),'not control socket')
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as c:
            c.settimeout(3);c.connect(str(p))
            peer=struct.unpack('3i',c.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))
            need(peer[:2]==(PID,0),'control peer differs')
            c.sendall(b'{"action":"status"}\n');data=b''
            while not data.endswith(b'\n') and len(data)<8192:
                chunk=c.recv(8192-len(data));need(bool(chunk),'incomplete status');data+=chunk
            need(json.loads(data)==EXPECTED_STATUS,'control status changed')
        self.socket_identity=(s.st_dev,s.st_ino)
        self.emit('CONTROL_STATUS_CONFIRMED',status=EXPECTED_STATUS)

    def process(self):
        p=Path('/proc')/str(PID)
        stat_raw=(p/'stat').read_text()
        values=dict(stat_text=stat_raw,status=(p/'status').read_text(),
            cmdline=(p/'cmdline').read_bytes().decode().rstrip('\0').split('\0'),maps=(p/'maps').read_text(),
            children=(p/'task'/str(PID)/'children').read_text(),threads=sorted(q.name for q in (p/'task').iterdir()),
            fds={q.name:os.readlink(q) for q in (p/'fd').iterdir()})
        validate_process(**values)
        need(all(self.owns(q,PID) for q in self.locks),'old lock owner differs')
        need(not select.select([self.pidfd],[],[],0)[0],'target already exited')
        self.emit('PROCESS_CONFIRMED',process=values)

    def resources(self,owner):
        def sample():
            self.kernel_check();need(all(self.owns(q,owner) for q in self.locks),'lock ownership changed')
            need(not Path('/sys/module/zocl').exists(),'module appeared')
            result=self.collect(allow_ps_display=True);self.kernel_check();return result
        bounded_scan(sample,self.require,self.emit)

    def preflight(self):
        self.load_policy()
        for p in (CENTRAL,CENTRAL/'history',CENTRAL/'active',CENTRAL/'active/lease.json',*self.locks):trusted(p)
        self.history();self.health();self.kernel_check()
        self.pidfd=os.pidfd_open(PID,0)
        self.status();self.process();self.resources(PID)
        self.history();self.process();self.kernel_check()
        self.phase='PREFLIGHT_PASSED'

    def signal_once(self):
        need(not self.signalled and self.phase=='PREFLIGHT_PASSED','signal already consumed')
        self.signalled=True;self.phase='SIGNAL_ATTEMPTED'
        signal.pidfd_send_signal(self.pidfd,signal.SIGUSR1,None,0)

    def confirm_exit(self):
        need(bool(select.select([self.pidfd],[],[],3)[0]),'exit unknown; no second signal')
        self.emit('OLD_SUPERVISOR_EXIT_CONFIRMED',pid=PID,normal_exit=False);self.phase='OLD_EXITED'

    def claim_locks(self):
        import fcntl
        self.history()
        for p in self.locks:
            fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC);self.held.append(fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        need(all(self.owns(q,os.getpid()) for q in self.locks),'new lock ownership not proven')
        self.emit('CLOSEOUT_LOCKS_ACQUIRED',pid=os.getpid());self.phase='LOCKED'

    def verify_after_exit(self):
        self.health();self.resources(os.getpid());self.history()
        need(not Path('/proc/8851').exists(),'old process still present/reused')
        s=(V3/'state/control.sock').lstat()
        need((s.st_dev,s.st_ino)==self.socket_identity and stat.S_ISSOCK(s.st_mode),'old socket identity changed')

    def prepare_record(self):
        self.result=dict(status='PREPARED_NOT_COMMITTED',boot_id=BOOT,old_supervisor_pid=PID,
            old_supervisor_normal_exit=False,old_supervisor_signal='SIGUSR1',closeout_pid=os.getpid(),
            archive=str(ARCHIVE),original_lease_sha256=LEASE,compute_runs=0,A11='NOT_PASSED',A12='NOT_ELIGIBLE',
            hardware_commands=0,locks_deleted=False,prior_journal_sha256=JOURNAL)
        write_new(DEST/'prepared.json',self.result);self.emit('ARCHIVE_PREPARED');self.phase='PREPARED'

    def archive_lease(self):
        self.history()
        need((CENTRAL/'active').resolve()==CENTRAL.resolve()/'active' and ARCHIVE.parent.resolve()==CENTRAL.resolve()/'history','archive escapes')
        self.emit('ARCHIVE_BEGIN',source=str(CENTRAL/'active'),destination=str(ARCHIVE))
        (CENTRAL/'active').rename(ARCHIVE);self.phase='ARCHIVED'
        sync_dir(CENTRAL);sync_dir(ARCHIVE.parent)
        need(sha((ARCHIVE/'lease.json').read_bytes())==LEASE and not os.path.lexists(CENTRAL/'active'),'archive readback differs')
        self.emit('ARCHIVE_COMMITTED')

    def commit_record(self):
        # Only retire the proven stale private socket; never a lock file.
        p=V3/'state/control.sock';s=p.lstat()
        need((s.st_dev,s.st_ino)==self.socket_identity and not Path('/proc/8851').exists(),'socket/process changed')
        p.unlink();sync_dir(p.parent)
        self.emit('STALE_PRIVATE_SOCKET_REMOVED',device=s.st_dev,inode=s.st_ino)
        write_new(DEST/'result.json',dict(self.result,status='CLOSEOUT_COMMITTED_REQUIRES_INDEPENDENT_READBACK'))
        self.phase='COMMITTED'

    def release_locks(self):
        for fd in reversed(self.held):os.close(fd)
        self.held.clear();self.emit('OWN_LOCK_FDS_CLOSED')

    def close(self):
        for fd in reversed(self.held):os.close(fd)
        self.held.clear()
        if self.pidfd is not None:os.close(self.pidfd)
        self.log.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--execute-authorized-final-only',action='store_true')
    a=p.parse_args()
    if not a.execute_authorized_final_only:
        print(json.dumps(dict(mode='PLAN_ONLY',target_pid=PID,compute_authorized=False)));return 0
    io=Closeout()
    # Keep transport disconnect from abandoning a metadata transaction. This
    # tool never waits indefinitely; all errors return, retaining its journal.
    signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
    try:execute(io);return 0
    except BaseException as exc:
        io.emit('STOP_RECONCILE_NO_RETRY_NO_PARK',phase=io.phase,signal_attempted=io.signalled,error=repr(exc))
        write_new(DEST/'STOP.json',dict(phase=io.phase,error=repr(exc),signal_attempted=io.signalled,
            active_exists=os.path.lexists(CENTRAL/'active'),archive_exists=os.path.lexists(ARCHIVE),no_automatic_retry=True))
        return 2
    finally:io.close()


if __name__=='__main__':raise SystemExit(main())
