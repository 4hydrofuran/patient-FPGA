"""Window mode coordinator runs in the ORIGINAL owning manager process.

No Board recovery/mutation/lease acquisition. CPU proof and Board retention have
different failure dispositions; a CPU drain is never a Board release witness.
"""
import os
from pathlib import Path
import re
import select
import threading
import uuid
from plmode_evidence import ROOT,read,sha,save
from plmode_journal import ModeJournal
from plmode_history import validate
from plmode_provider import CPUProvider,BoardProvider,MODES
from plmode_manager import Manager
from livegen_binding import ReadOnlyPage
from plm_journal import need
from plm_manager import ticks

def terminal(fd):
    poll=select.poll();poll.register(fd,select.POLLIN);return bool(poll.poll(0))

class Coordinator:
    def __init__(self,directory,build,*,board_owner=None,trusted_candidate=False):
        need(os.name=='posix','Linux owning coordinator required');self.build_path=Path(build);self.build=read(build);self.build_sha=sha(build)
        need(type(trusted_candidate) is bool,'trusted candidate selection must be explicit')
        self.board_owner=board_owner;self.domain='PC_CPU_MODEL' if board_owner is None else 'BOARD_PL_MODEL'
        need(self.build['domain']==('PC_REAL_MODEL_PLM_V1' if board_owner is None else 'A12_PREPARED_BOARD_MODEL_PLM_V1'),'provider/build domain mismatch')
        self.epoch=uuid.uuid4().hex;self.lock=threading.RLock();self.phase='IDLE';self.mode='STRICT_CONTROL';self.active=None;self.retained=[]
        self.trusted_candidate=trusted_candidate;self.reserved=None;self.prepared_provider=None;self.needs_new_owner=False;self.journal=ModeJournal(directory,self.epoch)
        self.manager_pidfd=None
        try:
            history=validate(self.journal.rows,closed_required=True);self.disabled=history['candidate_disabled'];self.used=set(history['used'])
            need(all(r.get('domain')==self.domain for r in self.journal.rows if r['event']=='SESSION_OPEN'),'history cannot change physical provider domain')
            self.manager_pidfd=os.pidfd_open(os.getpid());self.manager_ticks=ticks(os.getpid())
            self._append('SESSION_OPEN',default_mode=self.mode,domain=self.domain,candidate_disabled=self.disabled,build_sha256=self.build_sha,
                manager_pid=os.getpid(),manager_start_ticks=self.manager_ticks,release_allowed=False)
        except BaseException:
            # No native/provider exists here. Close this constructor's local
            # observers only; DIRTY and all failed history bytes stay intact.
            if self.manager_pidfd is not None:os.close(self.manager_pidfd);self.manager_pidfd=None
            self.journal.dispose();raise
    def _verify(self):
        need(sha(self.build_path)==self.build_sha,'mode build manifest changed')
        for row in self.build['runtime_artifacts']:need(sha(row['path'])==row['sha256'],'pinned runtime changed')
        self.journal.check();validate(self.journal.rows)
    def _append(self,event,**data):
        try:
            with self.lock:return self.journal.append(event,**data)
        except BaseException:
            self.cancel(log=False);self.phase='QUARANTINED';raise
    def switch(self,mode):
        with self.lock:
            need(self.phase=='IDLE' and self.active is None,'mode change requires proven idle window')
            need(mode in MODES,'unimplemented mode; SERVICE is not a 3-request acceptance window')
            need(mode!='BATCH_CANDIDATE' or self.trusted_candidate and not self.disabled,'candidate not trusted or fault-latched')
            self._verify()
            if self.mode!=mode:self._append('MODE_CHANGE',previous=self.mode,next=mode);self.mode=mode
    def start(self,input_id,*,fault=None):
        with self.lock:
            need(self.phase=='IDLE' and self.active is None,'active/unknown window cannot be replaced')
            need(fault in (None,'same_uuid_reload','cancel_claim','cancel_before_launch','begin_fsync','grant_fsync','end_fsync','receipt_fsync','drop_copy','request_digest'),'unknown fault seam')
            need(self.domain=='PC_CPU_MODEL' or fault is None,'PC test injection is never a Board operation')
            need(type(input_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',input_id) and input_id not in self.used and len(self.used)<8,'replayed/invalid/bounded input ID')
            need(self.reserved is None or self.reserved==input_id,'strict fallback reserved for explicit new input')
            need(not self.needs_new_owner,'a finished Board lease cannot be reused; bind another original Owner')
            self._verify();window=uuid.uuid4().hex;cap=MODES[self.mode]
            # A complete record failing fsync is still uncertain: no Popen follows.
            self._append('WINDOW_BEGIN',input_id=input_id,window_id=window,mode=self.mode,cap=cap,domain=self.domain)
            self.used.add(input_id);self.reserved=None;self.phase='ACTIVE'
            entry=dict(input_id=input_id,window_id=window,cap=cap,cancel=threading.Event(),manager=None,pidfd=None,page=None,next_request=0,proof=None)
            self.active=entry
        try:
            provider=self.prepared_provider or (CPUProvider() if self.domain=='PC_CPU_MODEL' else BoardProvider(self.board_owner,self.build_path))
            self.prepared_provider=None
            m=Manager.__new__(Manager);m.page=None;m.p=None;m.fault=None;entry['manager']=m
            if fault=='cancel_before_launch':
                need(self.domain=='PC_CPU_MODEL','test-only early cancel cannot select Board behavior');entry['cancel'].set();fault=None
            directory=Path(self.build['workspace'])/('window-'+window)
            m.__init__(self.build_path,directory,provider=provider,cap=cap,fault=fault,coordinator_lock=self.journal.lock,cancel_event=entry['cancel'])
            entry['pidfd']=os.dup(m.pidfd);entry['page']=ReadOnlyPage(m.page,self.build['observer_library'],self.build['observer_sha256'])
            snapshot=entry['page']()
            need(snapshot['manager_pid']==os.getpid() and snapshot['manager_start_ticks']==self.manager_ticks and
                snapshot['manager_epoch']==m.page.epoch,'independent page owner binding differs')
            self._append('NATIVE_OWNED',window_id=window,native_pid=m.p.pid,native_start_ticks=m.worker_ticks,page_epoch=m.page.epoch)
            m.ready();return dict(window_id=window,input_id=input_id,phase=self.phase,mode=self.mode)
        except BaseException as exc:self._failure(exc);raise
    def request_next(self):
        entry=self.active;need(self.phase=='ACTIVE' and entry is not None and entry['next_request']<3,'no active bounded request')
        try:
            result=entry['manager'].run_request(entry['next_request']);entry['next_request']+=1;return result
        except BaseException as exc:self._failure(exc);raise
    def finish_native(self):
        entry=self.active;need(self.phase=='ACTIVE' and entry and entry['next_request']==3,'acceptance requests incomplete')
        try:
            result=entry['manager'].normal_close();self._verify();page=entry['page']()
            need(terminal(entry['pidfd']) and not terminal(self.manager_pidfd) and page['revoked'] and not page['active'] and not page['unknown_io'],'normal process/page proof lost')
            proof=dict(window_id=entry['window_id'],input_id=entry['input_id'],native_pidfd_terminal=True,
                worker_exit_code=result['worker_exit_code'],page=page,release_allowed=False,replay_allowed=False)
            with self.lock:
                need(not entry['cancel'].is_set(),'cancelled result cannot complete mode window')
                self._append('WINDOW_END',**proof);entry['proof']=proof
                if self.domain=='PC_CPU_MODEL':self._retire();self.phase='IDLE'
                else:self.phase='AWAITING_ORIGINAL_OWNER_FINISH'
            return proof
        except BaseException as exc:self._failure(exc);raise
    def finish_original_owner(self):
        entry=self.active;failed=self.phase=='QUARANTINED'
        need(self.phase in ('AWAITING_ORIGINAL_OWNER_FINISH','QUARANTINED') and entry and entry['manager'].closed and
            terminal(entry['pidfd']) and not entry['page']()['unknown_io'],'original Owner finish not proven/pending')
        entry['manager'].finish_original_owner()
        self._append('FAILED_OWNER_FINALIZED' if failed else 'OWNER_FINALIZED',window_id=entry['window_id'],original_owner_finished=True,
            native_pidfd_terminal=True,page=entry['page'](),next_mode='STRICT_CONTROL' if failed else self.mode)
        if failed:self.mode='STRICT_CONTROL'
        self._retire();self.phase='IDLE';self.needs_new_owner=True
    def bind_new_owner(self,owner):
        with self.lock:
            need(self.domain=='BOARD_PL_MODEL' and self.phase=='IDLE' and self.active is None and self.needs_new_owner,'new Board owner not expected')
            need(owner is not self.board_owner and owner.lease_hash!=self.board_owner.lease_hash,'finished/old Board lease cannot be reused')
            provider=BoardProvider(owner,self.build_path);provider.authorize_mode(self.mode,self.build)
            self._append('NEXT_OWNER_BOUND',owner_window=owner.review['window_id'],lease_sha256=owner.lease_hash)
            self.board_owner=owner;self.prepared_provider=provider;self.needs_new_owner=False
    def _failure(self,exc):
        entry=self.active;self.disabled=True;self.phase='QUARANTINED'
        if entry is None:self.phase='QUARANTINED';return
        m=entry['manager']
        if m is not None and hasattr(m,'_fail'):
            m._fail(type(exc).__name__+': '+str(exc)) # atomic revoke precedes journal/locks
        if m is not None and entry['pidfd'] is None and getattr(m,'pidfd',None) is not None:
            entry['pidfd']=os.dup(m.pidfd);entry['page']=ReadOnlyPage(m.page,self.build['observer_library'],self.build['observer_sha256'])
            self._append('NATIVE_OWNED',window_id=entry['window_id'],native_pid=m.p.pid,native_start_ticks=m.worker_ticks,page_epoch=m.page.epoch)
        observation=(dict(worker_exit_code=m.p.returncode,reason=m.fault or str(exc)) if m is not None and m.page is not None and m.page.closed else
            m.failed_observation(str(exc)) if m is not None and hasattr(m,'monitor') else {})
        page=entry['page']() if entry['page'] is not None else (m.page.snapshot() if m is not None and m.page is not None else None)
        done=entry['pidfd'] is not None and terminal(entry['pidfd'])
        proof=dict(window_id=entry['window_id'],input_id=entry['input_id'],native_pidfd_terminal=done,
            worker_exit_code=observation.get('worker_exit_code'),page=page,release_allowed=False,replay_allowed=False,
            native_not_launched=self.domain=='PC_CPU_MODEL' and m is not None and m.p is None and not m.launch_attempted,
            reason=observation.get('reason',str(exc))[:400])
        with self.lock:
            entry['proof']=proof
            if not self.journal.blocked:
                self._append('WINDOW_FAILED',**proof)
                self.phase='FAILED_DRAINED_PC' if (self.domain=='PC_CPU_MODEL' and m is not None and type(m.provider) is CPUProvider and
                    done and page and page['revoked'] and page['source_slot']['domain']==1) else 'QUARANTINED'
                if proof['native_not_launched']:self.phase='FAILED_NO_NATIVE_PC'
    def observe(self):
        entry=self.active
        if entry is None:return dict(phase=self.phase)
        if self.phase=='QUARANTINED' and entry['cancel'].is_set() and entry.get('proof') is None:
            self._failure(RuntimeError('explicit mode cancellation reconciled from owned handles'))
        done=entry['pidfd'] is not None and terminal(entry['pidfd'])
        page=entry['page']() if entry['page'] is not None else None
        if self.phase=='QUARANTINED' and self.domain=='PC_CPU_MODEL' and entry.get('proof') and done and page and page['revoked'] and not self.journal.blocked:
            self._append('PC_NATIVE_DRAINED',window_id=entry['window_id'],native_pidfd_terminal=True,page=page,old_page_not_reset=True)
            self.phase='FAILED_DRAINED_PC'
        return dict(phase=self.phase,native_pidfd_terminal=done,page=page)
    def cancel(self,*,log=True):
        entry=self.active
        if entry is None:return False
        entry['cancel'].set();m=entry.get('manager')
        if m is not None and getattr(m,'page',None) is not None:m.cancel_authorization()
        if self.phase!='AWAITING_ORIGINAL_OWNER_FINISH':self.phase='QUARANTINED'
        if log:self._append('CANCEL_REQUEST',window_id=entry['window_id'])
        return True
    def fallback_for_new_input(self,input_id):
        with self.lock:
            entry=self.active
            need(self.domain=='PC_CPU_MODEL' and self.phase=='FAILED_DRAINED_PC' and entry and entry['proof'],'Board recovery is external; CPU drain cannot release a Board window')
            need(type(entry['manager'].provider) is CPUProvider and entry['page']()['source_slot']['domain']==1,'PC drain proof cannot substitute for a Board provider')
            need(type(input_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',input_id) and input_id not in self.used,'fallback cannot replay old input')
            need(terminal(entry['pidfd']) and entry['page']()['revoked'],'owned old native/page proof lost')
            self._verify();self._append('FALLBACK_NEW_INPUT',failed_input=entry['input_id'],next_input=input_id,next_mode='STRICT_CONTROL',
                native_pidfd_terminal=True,old_page_revoked=True,old_page_not_reset=True)
            self.retained.append(entry);self.active=None;self.mode='STRICT_CONTROL';self.reserved=input_id;self.phase='IDLE'
    def accept_recovered_owner(self,owner,input_id):
        """Recognize EXTERNAL recovery with a new already-owned live lease.

        Performs no recovery, takeover, reboot, mutation or old-page reset.
        A plain release JSON or a dead old PID is insufficient.
        """
        with self.lock:
            entry=self.active
            need(self.domain=='BOARD_PL_MODEL' and self.phase=='QUARANTINED' and entry and entry.get('proof'),'no quarantined Board window')
            need(type(entry['manager'].provider) is BoardProvider and entry['page']()['source_slot']['domain']==2,'actual Board source/provider required for recovery recognition')
            need(entry['pidfd'] is not None and terminal(entry['pidfd']) and entry['page']()['revoked'],'old owned native/page is not terminal/revoked')
            need(type(input_id) is str and re.fullmatch('[A-Za-z0-9_-]{1,48}',input_id) and input_id not in self.used,'recovery cannot replay an input')
            need(owner is not self.board_owner and owner.lease_hash!=self.board_owner.lease_hash and
                owner.review.get('permission_mode','STRICT_CONTROL')=='STRICT_CONTROL' and
                owner.review.get('recovery_for_window')==entry['window_id'],'new scoped original recovery Owner required')
            provider=BoardProvider(owner,self.build_path) # exact actual root ARM64 source, fresh original full gates
            provider.authorize_mode('STRICT_CONTROL',self.build);self._verify()
            self._append('BOARD_RECOVERY_NEW_INPUT',failed_window=entry['window_id'],failed_input=entry['input_id'],next_input=input_id,
                next_mode='STRICT_CONTROL',native_pidfd_terminal=True,old_page_revoked=True,old_page_not_reset=True,
                old_lease_sha256=self.board_owner.lease_hash,new_lease_sha256=owner.lease_hash,new_owner_window=owner.review['window_id'])
            self.retained.append(entry);self.active=None;self.board_owner=owner;self.prepared_provider=provider
            self.mode='STRICT_CONTROL';self.reserved=input_id;self.phase='IDLE';self.disabled=True;self.needs_new_owner=False
    def _retire(self):
        entry=self.active
        if entry['pidfd'] is not None:os.close(entry['pidfd'])
        if entry['page'] is not None:entry['page'].close()
        self.active=None
    def close(self):
        with self.lock:
            need(self.phase in ('IDLE','FAILED_DRAINED_PC','FAILED_NO_NATIVE_PC'),'unknown/live/unfinished Board mode cannot close')
            native_done=self.active is None or self.active['pidfd'] is not None and terminal(self.active['pidfd'])
            not_started=bool(self.active and self.active.get('proof') and self.active['proof'].get('native_not_launched'))
            need(native_done or not_started,'owned native still live')
            self._append('SESSION_CLOSE',candidate_disabled=self.disabled,failed_PC_native_terminal=native_done,native_not_launched=not_started,release_allowed=False)
            validate(self.journal.rows,closed_required=True);self.journal.finish();self.phase='CLOSED';os.close(self.manager_pidfd)
            # Failed PC authority pages remain unchanged/retained until this test
            # owning process exits. No Board or physical release is inferred.
