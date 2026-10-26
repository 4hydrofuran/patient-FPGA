"""Bounded private PC coordinator journal with a durable live-session marker."""
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import stat
import time
from request_journal_verified import canonical,digest,ZERO
from request_journal_audit import strict_json

class ModeBlocked(RuntimeError):pass
def need(v,s):
    if not v:raise ModeBlocked(s)
def identity(st):return (st.st_dev,st.st_ino,st.st_uid,st.st_mode,st.st_nlink)
def stable(st):return (identity(st),st.st_size,st.st_mtime_ns,st.st_ctime_ns)

class ModeJournal:
    def __init__(self,directory,epoch):
        self.path=Path(directory);self.epoch=epoch;self.fd=None;self.lock=None;self.parent=None
        self.closed=False;self.blocked=False;self.size=0;self.serial=0;self.chain=ZERO;self.rows=[]
        try:
            self.path.mkdir(mode=0o700,parents=True,exist_ok=True)
            st=self.path.lstat();need(stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and not st.st_mode&0o022,'private PC state directory required')
            self.parent=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.parent_pin=identity(os.fstat(self.parent))
            need(set(os.listdir(self.parent))<={'coordinator.lock','coordinator.jsonl','DIRTY.json'},'unlisted state directory content')
            self.lock=os.open('coordinator.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.parent)
            lst=os.fstat(self.lock);need(stat.S_ISREG(lst.st_mode) and lst.st_uid==os.geteuid() and lst.st_nlink==1 and not lst.st_mode&0o022,'unsafe coordinator lock')
            fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB);self.lock_pin=identity(lst)
            need(not (self.path/'DIRTY.json').exists(),'unclean session: no restart/replay; retain PC state')
            log=self.path/'coordinator.jsonl'
            if log.exists():
                self.rows=read_journal(log);last=self.rows[-1]
                need(last['event']=='SESSION_CLOSE','unclosed history requires independent recovery')
                self.serial=last['serial'];self.chain=last['sha256'];self.size=log.stat().st_size
            self.fd=os.open('coordinator.jsonl',os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.parent)
            st=os.fstat(self.fd);need(stat.S_ISREG(st.st_mode) and st.st_uid==os.geteuid() and st.st_nlink==1 and not st.st_mode&0o022 and st.st_size==self.size,'unsafe mode journal')
            self.file_pin=identity(st)
            marker=canonical(dict(schema='PC_MODE_LIVE_SESSION_V1',epoch=epoch,replay_allowed=False))+b'\n'
            self.marker_bytes=marker
            mfd=os.open('DIRTY.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.parent)
            try:
                self.marker_pin=identity(os.fstat(mfd));self._write(mfd,marker);os.fsync(mfd);os.fsync(self.parent)
            finally:os.close(mfd)
        except BaseException:
            self.dispose();raise
    @staticmethod
    def _write(fd,raw):
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);need(n>0,'mode journal made no write progress');view=view[n:]
    def append(self,event,**data):
        need(not self.closed and not self.blocked,'coordinator persistence latched/closed')
        try:
            self.check()
            row=dict(schema='PC_MODE_COORDINATOR_V1',serial=self.serial+1,previous_sha256=self.chain,
                session_epoch=self.epoch,monotonic_ns=time.monotonic_ns(),event=event,**data)
            row['sha256']=digest(row);raw=canonical(row)+b'\n'
            need(self.serial<128 and len(raw)<=8192 and self.size+len(raw)<=512*1024,'mode journal bound')
            self._write(self.fd,raw);os.fsync(self.fd);os.fsync(self.parent)
            need(os.fstat(self.fd).st_size==self.size+len(raw),'mode journal extent after append differs')
            self.size+=len(raw);self.serial+=1;self.chain=row['sha256'];self.rows.append(row);return row
        except BaseException:self.blocked=True;raise
    def check(self):
        need(set(os.listdir(self.parent))<={'coordinator.lock','coordinator.jsonl','DIRTY.json'},'mode state inventory changed')
        need(identity(self.path.lstat())==self.parent_pin,'mode directory replaced')
        need(identity(os.fstat(self.lock))==self.lock_pin and identity(os.stat('coordinator.lock',dir_fd=self.parent,follow_symlinks=False))==self.lock_pin,'mode lock replaced')
        text=Path('/proc/self/fdinfo',str(self.lock)).read_text()
        need(re.search(r'(?m)^lock:\s+\d+:\s+FLOCK\s+ADVISORY\s+WRITE\s+'+str(os.getpid())+r'\s',text),'mode lock lost')
        for st in (os.fstat(self.fd),os.stat('coordinator.jsonl',dir_fd=self.parent,follow_symlinks=False)):
            need(identity(st)==self.file_pin and st.st_size==self.size,'mode log identity/extent changed')
        if self.size:
            rows=read_journal(self.path/'coordinator.jsonl')
            need(len(rows)==self.serial and rows[-1]['sha256']==self.chain,'current mode history differs')
        need(identity(os.stat('DIRTY.json',dir_fd=self.parent,follow_symlinks=False))==self.marker_pin,'live marker replaced')
        marker=os.open('DIRTY.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.parent)
        try:need(os.read(marker,1024)==self.marker_bytes and not os.read(marker,1),'live marker bytes differ')
        finally:os.close(marker)
    def finish(self):
        self.check();need(not self.blocked and self.rows[-1]['event']=='SESSION_CLOSE','cannot clear dirty session')
        os.unlink('DIRTY.json',dir_fd=self.parent);os.fsync(self.parent);self.dispose()
    def dispose(self):
        self.closed=True
        for name in ('fd','lock','parent'):
            value=getattr(self,name,None)
            if value is not None:os.close(value);setattr(self,name,None)

def read_journal(path):
    p=Path(path);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==os.geteuid() and not before.st_mode&0o022 and 0<before.st_size<=512*1024,'unsafe/oversize journal')
        raw=b''
        while len(raw)<before.st_size:
            part=os.read(fd,min(65536,before.st_size-len(raw)));need(part,'journal truncated');raw+=part
        need(not os.read(fd,1) and stable(os.fstat(fd))==stable(before) and stable(p.lstat())==stable(before) and raw.endswith(b'\n'),'journal changed/torn')
        rows=[];previous=ZERO
        for i,line in enumerate(raw.splitlines(),1):
            need(i<=128 and len(line)<=8192,'mode record bound');r=strict_json(line)
            need(r['schema']=='PC_MODE_COORDINATOR_V1' and r['serial']==i and r['previous_sha256']==previous and
                r['sha256']==digest({k:v for k,v in r.items() if k!='sha256'}),'mode journal chain differs')
            previous=r['sha256'];rows.append(r)
        return rows
    finally:os.close(fd)
