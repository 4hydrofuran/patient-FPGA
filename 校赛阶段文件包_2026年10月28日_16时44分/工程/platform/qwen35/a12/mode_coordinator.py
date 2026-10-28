"""Window-boundary PC mode changes with owned pidfds and read-only page proof.

This is local PC validation orchestration, not a Board lease/release service.
"""
import array
import os
from pathlib import Path
import platform
import re
import select
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid

from mode_evidence import ROOT,OUT,read,sha
from mode_journal import ModeJournal,ModeBlocked,need
from mode_reader import PageObservation,ProcessObservation
from mode_registry import MODES,verify
from request_journal_audit import strict_json
from request_journal_verified import digest,canonical
from microbatch_audit import audit
from mode_history import validate_history


class ModeCoordinator:
    def __init__(self,directory,capsule,*,trusted_worker=False):
        need(os.name=='posix' and platform.machine()=='x86_64','PC coordinator refuses this platform')
        need(type(trusted_worker) is bool,'trusted_worker must be an explicit boolean')
        self.capsule_path=Path(capsule);self.capsule=verify(capsule);self.capsule_sha=sha(capsule)
        self.epoch=uuid.uuid4().hex;self.trusted_worker=trusted_worker;self.mode='PC_STRICT_CONTROL'
        self.phase='IDLE';self.active=None;self.disabled=False;self.next_input=None;self.lock=threading.RLock()
        self.journal=ModeJournal(directory,self.epoch);self.used={r['input_id'] for r in self.journal.rows if r['event']=='WINDOW_BEGIN'}
        try:
            validate_history(self.journal.rows,closed_required=True)
            self.disabled=any(r['event']=='WINDOW_FAILED' for r in self.journal.rows)
            self._append('SESSION_OPEN',default_mode=self.mode,capsule_sha256=self.capsule_sha,domain='PC_ONLY',
                candidate_disabled=self.disabled,replay_allowed=False,release_allowed=False)
        except BaseException:self.journal.dispose();raise

    def _append(self,event,**data):
        try:return self.journal.append(event,**data)
        except BaseException:
            self.phase='QUARANTINED';self.cancel(log=False);raise
    def _verify(self):
        need(sha(self.capsule_path)==self.capsule_sha,'mode capsule changed during session')
        validate_history(self.journal.rows)
        return verify(self.capsule_path)

    def switch(self,mode):
        with self.lock:
            need(self.phase=='IDLE' and self.active is None,'mode change requires proven idle PC window')
            need(mode in MODES,'Board/resource/numeric/service mode is not implemented by this PC entry')
            need(mode!='PC_BATCH_CANDIDATE' or self.trusted_worker and not self.disabled,
                'candidate requires trusted worker and no latched candidate fault')
            self._verify()
            if mode!=self.mode:
                self._append('MODE_CHANGE',previous_mode=self.mode,next_mode=mode,reason='NO_ACTIVE_AUTHORIZATION')
                self.mode=mode

    def launch(self,input_id,*,fault=None):
        with self.lock:
            need(self.phase=='IDLE' and self.active is None,'new window refused while active/unknown')
            need(type(input_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',input_id),'explicit synthetic PC input ID required')
            need(input_id not in self.used and len(self.used)<8,'input replay or session bound exceeded')
            need(self.next_input is None or input_id==self.next_input,'fallback is reserved for the named new input')
            need(fault in (None,'cached_revoke','end_log'),'unknown PC fault injection')
            self._verify();self.journal.check()
            window=uuid.uuid4().hex;tag='mc-'+window[:24];cap=MODES[self.mode]
            self._append('WINDOW_BEGIN',window_id=window,input_id=input_id,mode=self.mode,grant_size=cap,
                tag=tag,capsule_sha256=self.capsule_sha,independent_test_input=True)
            self.used.add(input_id);self.next_input=None;self.phase='ACTIVE'
            parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET);parent.setblocking(False)
            log=(OUT/('manager-'+tag+'.txt')).open('xb')
            r=dict(window_id=window,input_id=input_id,tag=tag,mode=self.mode,cap=cap,socket=parent,
                log=log,process=None,manager=None,native=None,page=None,telemetry=None,cancelled=False)
            self.active=r
            argv=[sys.executable,'-B',str(ROOT/'platform/qwen35/a12/mode_child.py'),'--tag',tag,'--cap',str(cap),
                '--build',self.capsule['build'],'--notify-fd',str(child.fileno()),'--session-epoch',self.epoch,
                '--window-id',window,'--runner-sha',self.capsule['runner_sha256']]
            if fault:argv+=['--fault',fault]
            try:
                p=subprocess.Popen(argv,stdout=log,stderr=subprocess.STDOUT,pass_fds=(child.fileno(),self.journal.lock))
                r['process']=p;child.close();r['manager']=ProcessObservation(p.pid,_ticks(p.pid))
                self._append('WINDOW_MANAGER_OBSERVED',window_id=window,manager_pid=p.pid,manager_start_ticks=r['manager'].ticks)
                return dict(window_id=window,input_id=input_id,manager_pid=p.pid,mode=self.mode,phase=self.phase)
            except BaseException:
                child.close();self.phase='QUARANTINED';self.cancel(log=False);raise

    def _receive(self,r):
        if r['telemetry'] is not None:return
        try:data,anc,flags,_=r['socket'].recvmsg(4096,socket.CMSG_SPACE(16),socket.MSG_CMSG_CLOEXEC)
        except BlockingIOError:return
        if not data:return
        fds=[]
        for level,kind,raw in anc:
            if level==socket.SOL_SOCKET and kind==socket.SCM_RIGHTS:
                values=array.array('i');values.frombytes(raw[:len(raw)//values.itemsize*values.itemsize]);fds+=values.tolist()
        try:
            need(not flags&(socket.MSG_TRUNC|socket.MSG_CTRUNC) and len(fds)==1,'invalid ownership telemetry FD/message')
            q=strict_json(data)
            need(q['event']=='MODE_NATIVE_OWNED' and q['domain']=='PC_NATIVE_MATH_NOT_FPGA' and
                q['session_epoch']==self.epoch and q['window_id']==r['window_id'] and q['grant_size']==r['cap'] and
                q['manager_pid']==r['process'].pid and q['manager_start_ticks']==r['manager'].ticks,'foreign telemetry')
            reader=read(self.capsule['reader_build']);fd=fds.pop();page=PageObservation(fd,reader)
            native=None
            try:
                native=ProcessObservation(q['native_pid'],q['native_start_ticks']);snapshot=page.snapshot()
                need(snapshot['manager_pid']==q['manager_pid'] and snapshot['manager_epoch']==q['page_epoch'],'page owner differs')
            except BaseException:
                if native is not None:native.close()
                page.close();raise
            r.update(telemetry=q,page=page,native=native)
            self._append('WINDOW_NATIVE_OBSERVED',window_id=r['window_id'],native_pid=native.pid,
                native_start_ticks=native.ticks,page_epoch=q['page_epoch'],page_snapshot_sha256=digest(snapshot))
        finally:
            for fd in fds:os.close(fd)

    def observe(self):
        with self.lock:
            r=self.active
            if r is None:return dict(phase=self.phase,mode=self.mode)
            if r.get('proof'):return dict(r['proof'],phase=self.phase)
            try:self._receive(r)
            except BaseException:
                self.phase='QUARANTINED';self.cancel(log=False);raise
            p=r['process']
            if p is None or p.poll() is None:return dict(phase=self.phase,manager_live=True,window_id=r['window_id'])
            if r['manager'] is None or r['native'] is None or r['page'] is None or not r['manager'].terminal() or not r['native'].terminal():
                self.phase='QUARANTINED';return dict(phase=self.phase,reason='missing/live owned process or page proof')
            snapshot=r['page'].snapshot()
            if not snapshot['revoked']:
                self.phase='QUARANTINED';return dict(phase=self.phase,reason='old page not revoked')
            build=read(self.capsule['build']);workspace=Path(build['workspace'])/('run-'+r['tag'])/'worker'
            independent=audit(workspace,Path(self.capsule['build']))
            try:self._verify();source_valid=True
            except BaseException:source_valid=False
            directory=OUT/('run-'+r['tag']);normal=source_valid and p.returncode==0 and not r['cancelled'] and independent['status']=='COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT'
            if normal:
                meta=read(directory/'MICROBATCH.json');worker=meta['workers'][0]
                child=read(directory/'MODE_CHILD.json')
                normal=(not snapshot['active'] and not snapshot['inflight_or_unknown'] and snapshot['shared_claims']==2880 and
                    independent['grant_size']==r['cap'] and meta['owner_FDs_closed_after_observer_stop']==[True] and
                    worker['all_protocol_and_observer_threads_stopped'] is True and meta['partial_initialization']==[] and
                    child['control_thread_stopped'] is True and child['cancelled'] is False)
            result=dict(window_id=r['window_id'],input_id=r['input_id'],tag=r['tag'],mode=r['mode'],manager_exit_code=p.returncode,
                manager_pidfd_terminal=True,native_pidfd_terminal=True,page=snapshot,independent_audit=independent,
                outcome='PASS_PC_WINDOW' if normal else 'FAILED_PC_DRAINED_NO_REPLAY',BOARD='NOT_TESTED',release_allowed=False)
            result['capsule_unchanged']=source_valid
            self._append('WINDOW_END' if normal else 'WINDOW_FAILED',**result)
            r['proof']=result
            if normal:self._retire(r);self.phase='IDLE'
            else:self.disabled=True;self.phase='FAILED_DRAINED_PC'
            return dict(result,phase=self.phase)

    def wait(self,timeout_s=180):
        need(0<timeout_s<=300,'invalid bounded PC wait');until=time.monotonic()+timeout_s
        while True:
            result=self.observe()
            if result.get('outcome') or self.active is None:return result
            if time.monotonic()>=until:
                self.cancel();return dict(phase=self.phase,status='WAIT_TIMEOUT_RETAINED',replay_allowed=False)
            time.sleep(.02)

    def cancel(self,*,log=True):
        r=self.active
        if r is None:return False
        # Stop request first, before any journal or coordinator lock wait.
        r['cancelled']=True
        try:r['socket'].send(canonical(dict(event='MODE_CANCEL',session_epoch=self.epoch,window_id=r['window_id'])))
        except (OSError,BlockingIOError):
            if r.get('manager') is not None and r['manager'].fd is not None:
                try:signal.pidfd_send_signal(r['manager'].fd,signal.SIGUSR1)
                except ProcessLookupError:pass
        self.phase='QUARANTINED'
        if log:
            with self.lock:self._append('CANCEL_REQUEST',window_id=r['window_id'],no_replay=True)
        return True

    def fallback_for_new_input(self,input_id):
        with self.lock:
            r=self.active
            need(self.phase=='FAILED_DRAINED_PC' and r is not None and r.get('proof'),'no known drained failure')
            need(type(input_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',input_id) and input_id not in self.used,
                'fallback cannot replay a failed/old input')
            need(r['manager'].terminal() and r['native'].terminal() and r['page'].snapshot()['revoked'],'fallback drain proof lost')
            self._verify()
            self._append('FALLBACK_NEXT_INPUT',failed_window=r['window_id'],failed_input=r['input_id'],
                next_input=input_id,next_mode='PC_STRICT_CONTROL',old_page_not_reset=True)
            self._retire(r);self.mode='PC_STRICT_CONTROL';self.next_input=input_id;self.phase='IDLE'

    def _retire(self,r):
        for key in ('page','native','manager'):
            if r.get(key) is not None:r[key].close()
        r['socket'].close();r['log'].close();self.active=None

    def close(self):
        with self.lock:
            need(self.phase in ('IDLE','FAILED_DRAINED_PC'),'cannot close/release an unknown/live PC session')
            validate_history(self.journal.rows)
            if self.active is not None:
                r=self.active;need(r.get('proof') and r['manager'].terminal() and r['native'].terminal() and r['page'].snapshot()['revoked'],'unconfirmed close')
                self._retire(r)
            self._append('SESSION_CLOSE',candidate_disabled=self.disabled,replay_allowed=False,release_allowed=False)
            self.journal.finish();self.phase='CLOSED'

def _ticks(pid):
    text=(Path('/proc')/str(pid)/'stat').read_text();return int(text[text.rfind(')')+2:].split()[19])
