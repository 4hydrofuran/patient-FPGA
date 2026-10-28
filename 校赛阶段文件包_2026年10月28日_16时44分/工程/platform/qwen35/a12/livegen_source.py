"""Live generation capability and a revoke-first platform mutation interlock.

All observations are in-process calls on held owner/OS handles. JSON records are
evidence, never capabilities. This trusted-process protocol cannot isolate root.
"""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import secrets
import select
import stat
import threading
import time
from plm_journal import need
from request_journal_verified import digest
from plm_manager import ticks

def fail_closed(method):
    def checked(self,*args,**kwargs):
        try:return method(self,*args,**kwargs)
        except BaseException:
            self.revoke('live generation operation refused: '+method.__name__);raise
    return checked

def fd_identity(st):return st.st_dev,st.st_ino,stat.S_IFMT(st.st_mode),st.st_uid,st.st_rdev

class NodePins:
    """O_PATH never opens a DRM device. Compare current dentry AND held inode.

    A target can be recreated with identical text/UUID; the retained old dentry
    still cannot become the new inode. Directory link counts may legitimately
    change when the owned XRT context creates its CU, so they are not generations.
    """
    def __init__(self,paths):
        need(os.name=='posix' and 0<len(paths)<=32,'bounded Linux generation node set required')
        self.rows=[];self.closed=False;self.lock=threading.RLock()
        try:
            seen=set()
            for name in paths:
                p=Path(name);need(p.is_absolute() and p not in seen,'unique absolute generation node required');seen.add(p)
                st=p.lstat();link=os.readlink(p) if stat.S_ISLNK(st.st_mode) else None
                fd=os.open(p,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC);held=fd_identity(os.fstat(fd))
                self.rows.append((p,fd,held,link));need(held==fd_identity(st),'generation node changed while pinning')
                if link is not None:
                    resolved=p.resolve(strict=True)
                    if resolved not in seen:
                        seen.add(resolved);target=os.open(resolved,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC)
                        self.rows.append((resolved,target,fd_identity(os.fstat(target)),None))
            need(len(self.rows)<=64,'expanded generation node set exceeded')
            self.fingerprint=digest([dict(path=str(p),identity=list(i),link=link) for p,_,i,link in self.rows]);self.check()
        except BaseException:self.close();raise
    def check(self):
        with self.lock:
            need(not self.closed,'generation node pins closed')
            for p,fd,expected,link in self.rows:
                current=p.lstat();need(fd_identity(current)==fd_identity(os.fstat(fd))==expected,'generation node replaced/unloaded')
                need((os.readlink(p) if stat.S_ISLNK(current.st_mode) else None)==link,'generation node binding changed')
    def close(self):
        with self.lock:
            if not self.closed:
                for _,fd,_,_ in self.rows:os.close(fd)
                self.rows=[];self.closed=True

class MutationInterlock:
    def __init__(self):
        self.epoch=secrets.token_hex(32);self.serial=0;self.source=None;self.retired=False;self.lock=threading.RLock()
    def register(self,source):
        with self.lock:
            need(self.source is None and not self.retired,'platform generation cannot be rebound')
            self.source=source;return self.epoch,self.serial
    def before(self,operation,*,release_check):
        source=self.source
        # No Python lock, filesystem, log write or release observation before revoke.
        if source is not None:source.revoke('platform mutation requested: '+operation)
        with self.lock:
            self.serial+=1
            if source is not None:
                need(source.normal_terminal,'live/unknown native generation retains platform ownership')
                source.require_idle_page()
                release_check() # original fresh process/refcount/kernel gate, no bool token
                self.retired=True
            return self.serial

@dataclass(frozen=True)
class Capability:
    issuer:object
    context_sha256:str
    epoch:str
    mutation_serial:int
    observed_ns:int
    nonce:str

class Source:
    """Shared algorithm. BoardPorts and PC fixture ports have separate factories."""
    def __init__(self,ports,interlock,on_revoke):
        self.ports=ports;self.interlock=interlock;self.on_revoke=on_revoke;self.lock=threading.RLock()
        self.blocked=False;self.bound=False;self.resident=False;self.pending=None;self.used=False;self.context=None
        self.pidfd=None;self.worker_pid=None;self.worker_ticks=None;self.process=None;self.normal_terminal=False;self.page_observer=None
        self.epoch,self.mutation_serial=interlock.register(self)
        self.identity_sha=digest(dict(domain=ports.domain,boot=ports.boot,lease_sha256=ports.lease_sha256,
            node_fingerprint=ports.nodes.fingerprint,platform_epoch=self.epoch,mutation_serial=self.mutation_serial))
        self.last_health=None;self.checks=0;self.observe()
    def revoke(self,reason):
        try:self.on_revoke() # atomically revoke native authority before any other work
        finally:
            self.blocked=True
            self.ports.nodes.close() # only our O_PATH observers; never lease/locks/native device/BO
    def observe(self):
        with self.lock:
            need(not self.blocked and not self.normal_terminal,'live source revoked/terminal')
            try:
                started=time.monotonic_ns()
                need(self.interlock.epoch==self.epoch and self.interlock.serial==self.mutation_serial,'platform mutation generation changed')
                self.ports.owner_check();self.ports.nodes.check();self.ports.identity_check()
                record=self.ports.health() # exact original serialized kernel/temperature/memory path on Board
                need(record['closing'] is False and record['checks_skipped'] is False and record['kernel']['allowed'] is True,'original live health gate refused')
                now=time.monotonic_ns();need(started<=record['checked_monotonic_ns']<=now,'health did not run in this observation')
                h=record['live_health'];need(h is not None and h['memory_kib']['MemAvailable']>=1114112 and
                    h['memory_kib']['CmaFree']>=98304 and h['temperatures_mC'] and all(0<t<55000 for t in h['temperatures_mC']),
                    'unchanged full-model live health floor refused')
                if self.resident:need(h['full_resident'] is True and h['actual_reserve']['allowed'] is True,'original resident admission refused')
                need(now<self.ports.expires,'original lease expired')
                if self.pidfd is not None:
                    poll=select.poll();poll.register(self.pidfd,select.POLLIN);need(not poll.poll(0),'owned native generation exited')
                self.last_health=record;self.last_started_ns=started;self.checks+=1;return started
            except BaseException:
                self.revoke('source observation failed');raise
    @fail_closed
    def attach_worker(self,process,pidfd,start_ticks,page_observer):
        with self.lock:
            need(not self.blocked and not self.bound and self.pidfd is None,'duplicate/late worker generation')
            need(process.pid>0 and ticks(process.pid)==start_ticks,'owned process incarnation differs')
            text=Path('/proc/self/fdinfo',str(pidfd)).read_text()
            need(re.search(r'(?m)^Pid:\s+'+str(process.pid)+r'\s*$',text),'held pidfd does not name owned process')
            duplicate=os.dup(pidfd);poll=select.poll();poll.register(duplicate,select.POLLIN)
            if poll.poll(0):os.close(duplicate);raise RuntimeError('owned worker already terminal')
            self.pidfd=duplicate;self.worker_pid=process.pid;self.worker_ticks=start_ticks;self.process=process;self.page_observer=page_observer
    @fail_closed
    def issue(self,facts):
        with self.lock:
            need(not self.used and self.pending is None and self.pidfd is not None,'generation capability order')
            self.ports.validate_context(facts,self.worker_pid,self.worker_ticks)
            stamp=self.observe();ctx=digest(facts)
            self.context=facts;self.pending=Capability(self,ctx,self.epoch,self.mutation_serial,stamp,secrets.token_hex(32))
            return self.pending
    @fail_closed
    def consume(self,capability,context_sha256):
        with self.lock:
            need(type(capability) is Capability and capability is self.pending and capability.issuer is self and not self.used and
                capability.context_sha256==context_sha256 and capability.epoch==self.epoch and capability.mutation_serial==self.mutation_serial and
                0<=time.monotonic_ns()-capability.observed_ns<=250000000,'foreign/replayed/stale live generation capability')
            stamp=self.observe();self.used=True;self.bound=True;self.pending=None;return stamp
    @fail_closed
    def seal_resident(self,route):
        with self.lock:
            need(self.bound and not self.resident,'resident generation order')
            self.ports.validate_resident(route,self.context);self.ports.mark_resident();self.resident=True;self.observe();return digest(route)
    def require_idle_page(self):
        need(self.page_observer is not None,'held page observer absent')
        state=self.page_observer()
        need(state['revoked'] and not state['active'] and not state['unknown_io'],'active/unknown native page retains ownership')
    def finish_native(self):
        # An exited process alone NEVER authorizes platform release.
        with self.lock:
            need(self.bound and self.resident and not self.blocked and self.pidfd is not None,'generation normal finish refused')
            poll=select.poll();poll.register(self.pidfd,select.POLLIN);need(poll.poll(0),'owned native pidfd not terminal')
            need(self.process.poll()==0,'normal native exit not proven')
            self.require_idle_page();self.normal_terminal=True
            self.ports.nodes.close() # avoid self-created O_PATH holders in the UNCHANGED release gate
    def close_observers(self):
        need(self.normal_terminal,'failed generation observer ownership retained')
        if self.pidfd is not None:os.close(self.pidfd);self.pidfd=None
        self.ports.close_observers() # never closes original lease/dual lock FDs or devices
