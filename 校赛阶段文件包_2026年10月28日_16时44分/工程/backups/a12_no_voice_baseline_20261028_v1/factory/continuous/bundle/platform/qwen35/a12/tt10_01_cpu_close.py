"""A-private CPU failure close channel for a future, separately reviewed manager.

No PL/XRT operations, forced signals, lease removal or platform recovery here.
The inherited Window remains responsible for complete scans, default/GDM proof,
atomic lease archival and lock release. Historical managers are never patched.
"""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import time


class CloseBlocked(RuntimeError):
    pass


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()


def durable_json(path,value):
    """Failure observations are exclusive and durable before any next action."""
    path=Path(path)
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'w',encoding='utf-8',closefd=False) as f:
            json.dump(value,f,ensure_ascii=False,allow_nan=False,indent=2);f.write('\n');f.flush();os.fsync(fd)
    finally:os.close(fd)
    directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)


def record_reserve_refusal(platform,boot,mem,temps,full_resident):
    """Keep the exact sample used by the unchanged 1114112/98304 KiB gate."""
    root=Path(platform.run);index=len(list(root.glob('cpu-close-health-refusal-*.json')))+1
    sample=dict(schema='TT10_CPU_CLOSE_HEALTH_REFUSAL_V1',boot_id=boot,observed_monotonic_ns=time.monotonic_ns(),
        reason='full-model live extra reserve gate',memory_kib=dict(mem),temperatures_mC=list(temps),
        full_resident=full_resident,required_MemAvailable_kib=1114112,required_CmaFree_kib=98304,allowed=False)
    path=root/('cpu-close-health-refusal-%04d.json'%index);durable_json(path,sample)
    platform.emit('EXACT_RESERVE_REFUSAL_SAVED',path=str(path),sha256=digest(path),sample=sample)
    return sample


def process_identity(pid):
    proc=Path('/proc')/str(pid);raw=(proc/'stat').read_text();fields=raw.rsplit(')',1)[1].split()
    return dict(pid=pid,parent_pid=int(fields[1]),start_ticks=int(fields[19]),executable_sha256=digest(proc/'exe'))


def cpu_device_observation(worker,expected):
    """Read only this owned child. Incomplete/replaced FD/maps data is blocking."""
    pid=worker.process.pid;before=process_identity(pid)
    if before!=expected or before['parent_pid']!=os.getpid():raise CloseBlocked('CPU process identity differs')
    proc=Path('/proc')/str(pid);fds={}
    names=sorted(p.name for p in (proc/'fd').iterdir())
    for name in names:
        p=proc/'fd'/name;target=os.readlink(p);info=p.stat()
        if stat.S_ISBLK(info.st_mode) or (stat.S_ISCHR(info.st_mode) and not (target=='/dev/null' and (os.major(info.st_rdev),os.minor(info.st_rdev))==(1,3))):
            raise CloseBlocked('CPU child has device descriptor')
        if target.startswith(('/dev/dri/','/dev/zocl','/dev/uio','/dev/vfio/','/dev/xclmgmt','/dev/dma_heap/')):
            raise CloseBlocked('CPU child has accelerator descriptor')
        fds[name]=target
    maps=(proc/'maps').read_text()
    if any(x in maps for x in ('libxrt','libsp_linear_a12_trial','libOpenCL','/dev/dri/','/dev/zocl','/dev/uio','/dev/vfio/','/dev/dma_heap/')):
        raise CloseBlocked('CPU child has XRT/device mapping')
    if sorted(p.name for p in (proc/'fd').iterdir())!=names or process_identity(pid)!=before:
        raise CloseBlocked('CPU process or descriptor table changed')
    return dict(identity=before,descriptor_targets=fds,maps_sha256=hashlib.sha256(maps.encode()).hexdigest(),
        no_device_descriptors=True,no_XRT_or_device_mappings=True,observed_monotonic_ns=time.monotonic_ns())


def default_cpu_platform(owner):
    """CPU failure cleanup cannot enter a PL-mutated, staged or unknown window."""
    p=owner.platform
    if p.pl_mutation_started or p.worker is not None or p.target.exists():raise CloseBlocked('PL mutation/worker/staging present')
    if Path('/sys/module/zocl').exists() or Path('/state.txt').exists():raise CloseBlocked('driver or uncertain platform state present')
    overlays=Path('/sys/kernel/config/device-tree/overlays')
    actual={d.name:(d/'status').read_text().strip() for d in overlays.iterdir() if d.is_dir()}
    if actual!={owner.cpu_default_name+'_image_1':'applied'} or Path('/sys/class/fpga_manager/fpga0/state').read_text().strip()!='operating':
        raise CloseBlocked('exact default PL state not proven')
    return dict(overlays=actual,module_absent=True,fpga_state='operating',PL_mutation=False)


class CpuOnlyWorkerMixin:
    """CPU workers may never grant router/device/load/submit permissions."""
    cpu_only=True

    def get(self,timeout):
        # The frozen base closes its durable journal on close(). Reject before
        # consuming a late queued result or trying to append to that journal.
        if self.closed:raise CloseBlocked('closed CPU delivery is unusable')
        return super().get(timeout)

    def _permissions(self):
        with self.manager_sock.makefile('r',encoding='utf-8') as stream:
            try:
                for line in stream:
                    self.quarantined=True
                    if len(line)>4096:raise CloseBlocked('oversized CPU control request')
                    request=json.loads(line)
                    self.record(event='CPU_UNEXPECTED_PERMISSION_RETAIN_OWNER',request=request,allow=False)
                    self.manager_sock.sendall((json.dumps(dict(sequence=request.get('sequence'),allow=False))+'\n').encode())
                    self.manager_sock.shutdown(socket.SHUT_WR)
                    return
            except BaseException as exc:
                self.quarantined=True
                self.record(event='CPU_CONTROL_FAULT_RETAIN_OWNER',reason=type(exc).__name__+': '+str(exc))
                try:self.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:pass


class CpuCloseOwnerMixin:
    """Registered CPU ownership and fresh closing observations, no compute unlatch."""
    def start_cpu_worker(self,factory,*args,**kwargs):
        with self.platform.gate_lock:
            if getattr(self,'_cpu_failure_latched',False) or getattr(self,'_cpu_launch_pending',False) or getattr(self,'_owned_worker',None) is not None:
                raise CloseBlocked('CPU launch after failure/pending/owned worker')
            self.owner_check();self.health()
            self._cpu_launch_pending=True;self._cpu_phase='CPU_LAUNCHING'
            self._finalize_record('CPU_LAUNCH_RESERVED',normal_exit_proven=False)
        try:
            kwargs['inherited_fds']=tuple(self.locks)
            worker=factory(*args,**kwargs)
            # Register before further reads can fail; an uncertain launch remains owned.
            self._owned_worker=worker;self._cpu_worker=worker
            if worker.real is not False or getattr(worker,'cpu_only',False) is not True:
                raise CloseBlocked('CPU factory did not return a CPU-only worker')
            self._cpu_identity=process_identity(worker.process.pid)
            if self._cpu_identity['parent_pid']!=os.getpid():raise CloseBlocked('CPU worker is not our child')
            self._cpu_launch_pending=False;self._cpu_phase='CPU'
            self._finalize_record('CPU_WORKER_REGISTERED',identity=self._cpu_identity,real=False,inherited_lock_count=len(self.locks))
            return worker
        except BaseException as exc:
            self._finalize_record('CPU_LAUNCH_UNCERTAIN_RETAIN_OWNER',reason=type(exc).__name__+': '+str(exc))
            raise

    def start_worker(self,*args,**kwargs):
        cpu=getattr(self,'_cpu_worker',None)
        if getattr(self,'_cpu_failure_latched',False) or getattr(self,'_cpu_launch_pending',False) or cpu is None or not cpu.closed or cpu.process.returncode!=0:
            raise CloseBlocked('PL launch requires normally closed CPU phase without failure')
        self._cpu_phase='PL'  # A failed PL constructor may not be treated as CPU-only.
        return super().start_worker(*args,**kwargs)

    def cpu_close_health(self,*,closing=False,compute=None):
        if not closing:
            if getattr(self,'_cpu_failure_latched',False):raise CloseBlocked('CPU failure compute latch')
            return compute()
        worker=getattr(self,'_owned_worker',None)
        if getattr(self,'_cpu_launch_pending',False) or worker is None or not worker.closed or worker.process.returncode!=0 or worker.quarantined:
            raise CloseBlocked('fresh closing check requires known normal worker exit')
        with self.platform.gate_lock:
            self.owner_check();begin=time.monotonic_ns()
            schedule=self.platform.health_schedule;latched=schedule.blocked;last=schedule.last_success_ns
            observation=self._health_observation(closing=True)
            end=time.monotonic_ns();kernel=observation.get('kernel',{})
            if (observation.get('closing') is not True or observation.get('checks_skipped') is not False or
                not begin<=observation.get('checked_monotonic_ns',0)<=end or kernel.get('allowed') is not True or
                not begin<=kernel.get('observation_monotonic_ns',0)<=end or
                schedule.blocked!=latched or schedule.last_success_ns!=last):
                raise CloseBlocked('closing observation stale/incomplete or changed compute schedule')
            self._finalize_record('FRESH_CLOSING_ONLY_OBSERVATION',observation=observation,compute_latch_unchanged=latched,last_compute_success_ns=last)
            return observation

    def finish(self,worker):
        if worker is not getattr(self,'_owned_worker',None) or getattr(self,'_cpu_launch_pending',False):
            raise CloseBlocked('foreign worker or uncertain launch cannot finalize')
        cpu=getattr(self,'_cpu_worker',None)
        if cpu is None or not cpu.closed or cpu.process.returncode!=0 or cpu.quarantined or cpu.permission_thread.is_alive() or cpu.reader_thread.is_alive():
            raise CloseBlocked('CPU normal exit without quarantine not proven')
        return super().finish(worker)

    def handle_cpu_failure(self,reason,*,timeout=45):
        """Future manager exception path. False means retain locks/lease; never kill."""
        with self.platform.gate_lock:
            self._cpu_failure_latched=True;self.platform.health_schedule.blocked=True
        self._finalize_record('COMPUTE_FAILURE_LATCHED',reason=reason,phase=getattr(self,'_cpu_phase','UNKNOWN'),normal_exit_proven=False)
        try:
            worker=getattr(self,'_cpu_worker',None)
            if getattr(self,'_cpu_phase',None)!='CPU' or getattr(self,'_cpu_launch_pending',False) or worker is None or worker is not getattr(self,'_owned_worker',None):
                raise CloseBlocked('not a registered certain CPU-only phase')
            self.owner_check();platform=default_cpu_platform(self)
            if worker.real is not False or worker.runs!=0 or worker.loads!=0 or worker.sequence!=0 or worker.quarantined:
                raise CloseBlocked('CPU device permissions/quarantine present')
            if not worker.closed:
                if worker.process.poll() is None:
                    scan=cpu_device_observation(worker,self._cpu_identity)
                    self._finalize_record('CPU_COOPERATIVE_CLOSE_RESERVED',scan=scan,platform=platform,shutdown='stdin JSON',cooperative_signal='SIGUSR1',forced_termination=False)
                    if not worker.delivery_cancelled:worker.cancel('CPU_FAILURE_CLOSE_DISCARD_DELIVERY')
                if not worker.close(timeout=timeout):raise CloseBlocked('CPU close timeout or bad exit; retain owner')
            if not worker.closed or worker.process.returncode!=0 or worker.quarantined or worker.runs!=0 or worker.loads!=0 or worker.sequence!=0 or worker.permission_thread.is_alive() or worker.reader_thread.is_alive():
                raise CloseBlocked('CPU normal exit/readers not proven')
            self._finalize_record('CPU_NORMAL_EXIT_PROVEN',exit_code=0,delivery_discarded=worker.delivery_cancelled,forced_termination=False)
            self.health(closing=True)
            default_cpu_platform(self);self.platform.no_users(module_loaded=False)
            if self.platform.gdm_isolated:self.platform.service('start')
            self.finish(worker)  # Existing full scan/default/GDM/archive/lock rules.
            self._finalize_record('CPU_FAILURE_NORMAL_FINALIZED',original_failure=reason,worker_exit_code=0,manager_exit_code=1,new_PL_calls=0,compute_pass=False)
            return True
        except Exception as exc:
            self._finalize_record('CPU_CLOSE_BLOCKED_OWNER_RETAINED',original_failure=reason,reason=type(exc).__name__+': '+str(exc),forced_termination=False)
            return False
