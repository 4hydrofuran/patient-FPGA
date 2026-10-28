"""A11 worker protocol on the unchanged A10 no-kill/release boundary.

This is a component, not a board entry. A reviewed manager must hold both locks,
verify a fresh lease/boot/kernel and continuously observe thermal/kernel health.
The parent lends (never transfers/unlocks) only its device lock descriptor.
"""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

A10=Path(__file__).resolve().parent.parent/'a10'
sys.path.insert(0,str(A10))
from accelerator_release_gate_v2 import start_ticks
from isolated_idle_policy import lock_owned
from xrt_worker_boundary import IdleWorkerBoundary
from mlp_policy import schedule

PROTOCOL='a11-minimal-mlp-worker-v1'
DEVICE_LOCK=Path('/run/lock/patient-qwen-linear.lock')
TIMINGS=('input_quant_ms','service_ms','api_run_ms','report_ms','output_copy_ms')


def need(condition,reason):
    if not condition:raise ValueError(reason)


from compute_result import validate_result


class MlpBoundary(IdleWorkerBoundary):
    def __init__(self,request,result_path,**kwargs):
        extra={k:request[k] for k in ('plan_sha256','worker_baseline_sha256') if k in request}
        need(len(extra)==2 and all(type(v) is str and re.fullmatch(r'[0-9a-f]{64}',v) for v in extra.values()),
             'fresh plan and worker baseline pins required')
        super().__init__({k:v for k,v in request.items() if k not in extra},result_path,**kwargs)
        self.identity.update(protocol=PROTOCOL,**extra)

    def start(self,reviewed_argv,*,device_lock_fd,stdout_path,stderr_path,cwd=None):
        if self.state!='NEW':self.block('WORKER_REPLAY_FORBIDDEN')
        self.state='START_RESERVED'
        self.checked_guard()
        try:
            need(type(device_lock_fd) is int and device_lock_fd>=3,'explicit device lock fd required')
            named,actual=DEVICE_LOCK.stat(),os.fstat(device_lock_fd)
            need(not DEVICE_LOCK.is_symlink() and named.st_uid==os.geteuid() and not named.st_mode&0o022,
                 'untrusted device lock')
            need((named.st_dev,named.st_ino)==(actual.st_dev,actual.st_ino) and
                 lock_owned(DEVICE_LOCK,os.getpid()),'manager does not own this lock')
            need(reviewed_argv and all(type(v) is str for v in reviewed_argv),'reviewed argv required')
            need(not os.path.lexists(self.result_path),'consumed result path')
            self.identity.update(inherited_device_lock_fd=device_lock_fd,
                                 manager_start_ticks=start_ticks(Path('/proc/self')))
            for path in (stdout_path,stderr_path):self.logs.append(Path(path).open('xb'))
            argv=list(reviewed_argv)+['--a11-boundary-request',json.dumps(self.identity),
                                     '--a11-boundary-result',str(self.result_path.resolve())]
            self.process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=self.logs[0],stderr=self.logs[1],
                                          close_fds=True,pass_fds=(device_lock_fd,),cwd=cwd,shell=False)
            self.state='RUNNING'
        except Exception as exc:self.block('WORKER_START_UNKNOWN: '+str(exc))
        self.event('A11_WORKER_STARTED',worker_pid=self.process.pid,identity=self.identity,
                   parent_retains_both_locks=True,child_must_never_unlock=True)

    def wait_normal(self,timeout_s):
        if self.state!='RUNNING':self.block('WORKER_NOT_RUNNING')
        if type(timeout_s) not in (int,float) or not math.isfinite(timeout_s) or not 0<timeout_s<=300:
            self.block('INVALID_A11_SOFT_DEADLINE')
        self.checked_guard()
        try:
            deadline=time.monotonic()+timeout_s
            while True:
                self.pulse()
                remaining=deadline-time.monotonic()
                if remaining<=0:raise subprocess.TimeoutExpired('A11_worker',timeout_s)
                try:
                    code=self.process.wait(timeout=min(.1,remaining))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=deadline:raise
        except subprocess.TimeoutExpired:self.block('WORKER_TIMEOUT_NO_KILL_NO_UNLOAD')
        except Exception as exc:self.block('WORKER_WAIT_UNKNOWN: '+str(exc))
        self.exited_ns=time.monotonic_ns()
        self.event('WORKER_REAPED',worker_pid=self.process.pid,exit_code=code,monotonic_ns=self.exited_ns)
        try:
            for stream in self.logs:stream.close()
        except OSError as exc:self.block('EVIDENCE_CLOSE_FAILED: '+str(exc))
        if code!=0:self.block('WORKER_ABNORMAL_EXIT')
        self.checked_guard()
        try:
            need(not self.result_path.is_symlink() and self.result_path.stat().st_size<=262144,'invalid result file')
            result=json.loads(self.result_path.read_text(encoding='utf-8'))
            validate_result(result,self.identity,self.process.pid)
        except Exception as exc:self.block('WORKER_RESULT_UNPROVEN: '+str(exc))
        self.state='EXITED_NORMAL'
        return result

    # check_release is deliberately inherited unchanged: only after actual
    # waitpid(normal), fresh complete FD/VMA scan, refcount=0 and kernel gate.
