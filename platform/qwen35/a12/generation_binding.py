"""Bounded PC fixtures for a live generation issuer; NEVER Board authority.

No JSON is an approval. The issuer retains both actual flock FDs, a live pidfd,
fresh bounded file readers, boot/process identity and a one-use capability.
Synthetic driver/kernel/BO generations are explicitly PC-only. The production
factory stays closed until the original platform gates are independently wired.
"""
import ctypes as c
import fcntl
import hashlib
import os
from pathlib import Path
import re
import secrets
import select
import stat
import threading
import time
from dataclasses import dataclass
from fresh_identity_io import FreshCheckedFile
from request_journal_verified import canonical,digest
from plm_manager import ticks
from plm_journal import need
from modelpl_evidence import sha,save

PC_DOMAIN='PC_GENERATION_FIXTURE_NO_DEVICE'

@dataclass(frozen=True)
class Approval:
    issuer:object
    nonce:str
    context:str
    observed_ns:int

class FixtureIssuer:
    def __init__(self,directory,deadline):
        need(os.name=='posix','PC Linux fixture required')
        self.directory=Path(directory);self.directory.mkdir(mode=0o700)
        self.directory_pin=self.directory.lstat()
        need(stat.S_ISDIR(self.directory_pin.st_mode) and self.directory_pin.st_uid==os.geteuid() and
            not self.directory_pin.st_mode&0o077,'private generation fixture directory required')
        self.deadline=deadline;self.pid=os.getpid();self.ticks=ticks(self.pid)
        self.boot=Path('/proc/sys/kernel/random/boot_id').read_text()
        self.epoch=secrets.token_hex(32);self.blocked=False;self.used=False;self.pending=None;self.calls=0;self.closed=False
        self.mutex=threading.RLock();self.locks=[];self.lock_pins=[];self.readers=[];self.pidfd=None
        try:
            self.pidfd=os.pidfd_open(self.pid)
            for name in ('deployment.lock','linear.lock'):
                path=self.directory/name;fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
                self.locks.append((path,fd));fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
                st=os.fstat(fd);self.lock_pins.append((st.st_dev,st.st_ino))
            lease=dict(schema=PC_DOMAIN,manager_pid=self.pid,manager_ticks=self.ticks,boot_id=self.boot,epoch=self.epoch,deadline_monotonic_ns=deadline)
            identity=dict(domain=PC_DOMAIN,boot_id=self.boot,driver_generation='PC_NO_DRIVER',kernel_generation='PC_NO_KERNEL',
                device_generation='PC_NO_DEVICE',BO_generation='PC_NO_BO',mutation_serial=0,epoch=self.epoch)
            self.identity=identity;self.identity_sha=digest(identity)
            for name,data in (('lease.json',lease),('identity.json',identity)):
                p=self.directory/name;save(p,data)
                self.readers.append(FreshCheckedFile(p,sha(p),max_bytes=16384,chunk=4096))
            self.observe()
        except BaseException:
            self._test_cleanup();raise
    def observe(self):
        with self.mutex:
            need(not self.blocked and not self.closed,'generation issuer revoked/closed')
            try:
                need(time.monotonic_ns()<self.deadline,'generation lease expired')
                parent=self.directory.lstat()
                need(stat.S_ISDIR(parent.st_mode) and parent.st_uid==os.geteuid() and not parent.st_mode&0o077 and
                    (parent.st_dev,parent.st_ino)==(self.directory_pin.st_dev,self.directory_pin.st_ino),'generation fixture directory changed')
                poll=select.poll();poll.register(self.pidfd,select.POLLIN)
                need(not poll.poll(0) and os.getpid()==self.pid and ticks(self.pid)==self.ticks,'generation manager incarnation changed')
                need(Path('/proc/sys/kernel/random/boot_id').read_text()==self.boot,'generation boot changed')
                for ((path,fd),expected) in zip(self.locks,self.lock_pins):
                    a=path.lstat();b=os.fstat(fd)
                    need(stat.S_ISREG(a.st_mode) and stat.S_ISREG(b.st_mode) and a.st_nlink==b.st_nlink==1 and
                        a.st_uid==b.st_uid==os.geteuid() and not (a.st_mode|b.st_mode)&0o077 and
                        (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino)==expected,'generation canonical lock identity changed')
                    need(re.search(r'(?m)^lock:\s+\d+:\s+FLOCK\s+ADVISORY\s+WRITE\s+'+str(self.pid)+r'\s',
                        Path('/proc/self/fdinfo',str(fd)).read_text()),'generation dual flock lost')
                for reader in self.readers:reader.check()
                self.calls+=1
                return time.monotonic_ns()
            except BaseException:
                self.blocked=True;raise
    def issue(self,context):
        with self.mutex:
            need(not self.used and self.pending is None and type(context) is str and len(context)==64 and
                all(c in '0123456789abcdef' for c in context),'generation duplicate/context approval')
            stamp=self.observe();self.pending=Approval(self,secrets.token_hex(32),context,stamp);return self.pending
    def consume(self,approval,context):
        with self.mutex:
            need(type(approval) is Approval and approval is self.pending and approval.issuer is self and not self.used and
                approval.context==context and 0<=time.monotonic_ns()-approval.observed_ns<=250_000_000,'foreign/replayed/stale generation approval')
            stamp=self.observe();self.used=True;self.pending=None;return stamp
    def before_platform_mutation(self,revoke):
        # Revocation precedes locks, diagnostics or persistence. This method NEVER
        # performs a mutation, even if the current local Page looks quiescent.
        revoke();self.blocked=True
        raise RuntimeError('generation revoked; platform mutation requires separate original release gates')
    def close_normal(self):
        need(not self.blocked,'generation failure ownership retained');self._test_cleanup()
    def _test_cleanup(self):
        # Only private PC fixture FDs. Never a board lease or a device lock path.
        for reader in self.readers:reader.close()
        for _,fd in self.locks:os.close(fd)
        self.locks=[]
        if self.pidfd is not None:os.close(self.pidfd);self.pidfd=None
        self.closed=True

def board_issuer(*args,**kwargs):
    raise RuntimeError('UNBOUND: original live platform/lease/dual-lock/kernel/driver/BO gates not yet wired; Board issuer disabled')

class Slot:
    def __init__(self,page,library,expected,issuer):
        need(sha(library)==expected,'generation writer changed');self.lib=c.CDLL(str(library));self.handle=None;self.closed=False
        self.page=page
        signatures={'open':([c.c_int,c.c_char_p,c.c_char_p],c.c_void_p),'health':([c.c_void_p,c.c_uint64],c.c_int),
            'bind':([c.c_void_p,c.c_char_p],c.c_int),'resident':([c.c_void_p,c.c_char_p],c.c_int),
            'revoke':([c.c_void_p],c.c_uint64),'close':([c.c_void_p],c.c_int)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.lib,'a12_gen_'+name+'_v1');fn.argtypes=args;fn.restype=result;setattr(self,name+'_fn',fn)
        self.handle=self.open_fn(page.fd,issuer.identity_sha.encode(),issuer.epoch.encode());need(self.handle,'generation slot init refused')
    def call(self,name,*args):
        need(not self.closed and self.handle and getattr(self,name+'_fn')(self.handle,*args)==0,'generation slot '+name+' refused')
    def health(self,n):self.call('health',n)
    def bind(self,ctx):self.call('bind',ctx.encode())
    def resident(self,h):self.call('resident',h.encode())
    def revoke(self):
        if self.handle and not self.closed:return self.revoke_fn(self.handle)
    def close(self):self.call('close');self.closed=True;self.handle=None
