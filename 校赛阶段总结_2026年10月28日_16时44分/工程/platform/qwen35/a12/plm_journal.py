"""Small bounded request/grant log, durable dirty marker, no board release authority."""
import fcntl
import os
from pathlib import Path
import stat
import time
from request_journal_verified import canonical,digest,ZERO
from request_journal_audit import strict_json

def need(v,s):
    if not v:raise RuntimeError(s)
def ident(st):return st.st_dev,st.st_ino,st.st_uid,st.st_mode,st.st_nlink
class Journal:
    def __init__(self,path,epoch,on_fault,fault=None):
        self.path=Path(path);self.path.mkdir(mode=0o700);self.epoch=epoch;self.on_fault=on_fault;self.fault=fault
        self.serial=0;self.chain=ZERO;self.size=0;self.blocked=False;self.receipts=[];self.boundary_read_bytes=0
        self.root=os.open(self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        st=os.fstat(self.root);need(stat.S_ISDIR(st.st_mode) and st.st_uid==os.geteuid() and not st.st_mode&0o022,'private PLM state required');self.root_pin=ident(st)
        self.lock=os.open('control.lock',os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
        fcntl.flock(self.lock,fcntl.LOCK_EX|fcntl.LOCK_NB);self.lock_pin=ident(os.fstat(self.lock))
        self.fd=os.open('control.jsonl',os.O_RDWR|os.O_APPEND|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root);self.fd_pin=ident(os.fstat(self.fd))
        self.marker=canonical(dict(schema='PC_PLM_DIRTY_V1',epoch=epoch,replay_allowed=False))+b'\n'
        m=os.open('DIRTY.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root)
        try:self.marker_pin=ident(os.fstat(m));self.write(m,self.marker);os.fsync(m);os.fsync(self.root)
        finally:os.close(m)
    @staticmethod
    def write(fd,raw):
        view=memoryview(raw)
        while view:
            n=os.write(fd,view);need(n>0,'PLM zero-progress write');view=view[n:]
    def check(self):
        self.owner_check()
        need(not self.blocked and ident(self.path.lstat())==self.root_pin,'PLM journal blocked/replaced')
        need(set(os.listdir(self.root))=={'control.lock','control.jsonl','DIRTY.json',*self.receipts},'PLM state inventory differs')
        for fd,name,pin in ((self.fd,'control.jsonl',self.fd_pin),(self.lock,'control.lock',self.lock_pin)):
            need(ident(os.fstat(fd))==pin and ident(os.stat(name,dir_fd=self.root,follow_symlinks=False))==pin,'PLM owned FD changed')
        need(os.fstat(self.fd).st_size==self.size,'PLM journal extent changed')
        m=os.open('DIRTY.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.root)
        try:need(ident(os.fstat(m))==self.marker_pin and os.read(m,1024)==self.marker and not os.read(m,1),'PLM dirty marker changed')
        finally:os.close(m)
    def owner_check(self):
        # Observer-safe while append/receipt I/O is in progress: no changing extent/inventory verdict.
        need(not self.blocked and ident(self.path.lstat())==self.root_pin,'PLM journal blocked/replaced')
        for fd,name,pin in ((self.fd,'control.jsonl',self.fd_pin),(self.lock,'control.lock',self.lock_pin)):
            need(ident(os.fstat(fd))==pin and ident(os.stat(name,dir_fd=self.root,follow_symlinks=False))==pin,'PLM live owner FD changed')
        info=Path('/proc/self/fdinfo',str(self.lock)).read_text();need('FLOCK' in info and str(os.getpid()) in info,'PLM owner lock lost')
        m=os.open('DIRTY.json',os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=self.root)
        try:need(ident(os.fstat(m))==self.marker_pin and os.read(m,1024)==self.marker and not os.read(m,1),'PLM marker changed')
        finally:os.close(m)
    def append(self,event,**data):
        try:
            self.check();row=dict(schema='PC_PLM_JOURNAL_V1',serial=self.serial+1,previous_sha256=self.chain,
                epoch=self.epoch,event=event,monotonic_ns=time.monotonic_ns(),**data);row['sha256']=digest(row);raw=canonical(row)+b'\n'
            need(self.serial<4096 and len(raw)<=8192 and self.size+len(raw)<=4*1024*1024,'PLM journal capacity exceeded')
            self.write(self.fd,raw)
            victim={'begin_fsync':'BEGIN','grant_fsync':'GRANT','end_fsync':'END'}.get(self.fault)
            if event==victim:self.fault=None;raise OSError('injected complete-record fsync failure')
            if (self.fault,event) in (('grant_slow','GRANT'),('end_slow','END')):self.fault=None;time.sleep(.35)
            os.fsync(self.fd)
            need(os.pread(self.fd,len(raw),self.size)==raw and os.fstat(self.fd).st_size==self.size+len(raw),'PLM appended bytes differ')
            self.size+=len(raw);self.serial+=1;self.chain=row['sha256'];return row
        except BaseException as exc:self.blocked=True;self.on_fault('journal: '+str(exc));raise
    def check_all(self):
        self.check();chain=ZERO;serial=0;used=0
        # Requests only: bounded stream read, never a whole-log scan per projection/grant.
        with os.fdopen(os.dup(self.fd),'rb') as f:
            f.seek(0)
            while True:
                raw=f.readline(8193)
                if not raw:break
                need(len(raw)<=8192 and raw.endswith(b'\n'),'PLM malformed history');r=strict_json(raw);h=r.pop('sha256')
                need(r['serial']==serial+1 and r['previous_sha256']==chain and r['epoch']==self.epoch and h==digest(r),'PLM history chain changed')
                serial+=1;chain=h;used+=len(raw)
        self.boundary_read_bytes+=used;need(serial==self.serial and chain==self.chain and used==self.size,'PLM history extent/chain mismatch')
    def receipt(self,name,value):
        need(name in ('app_R0','warm_prefix','app_hit'),'unknown PLM receipt ID');name+='-receipt.json';raw=canonical(value)+b'\n';need(len(raw)<=8192,'PLM receipt bound')
        fd=None
        try:
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=self.root);self.write(fd,raw)
            if self.fault=='receipt_fsync':self.fault=None;raise OSError('injected receipt fsync failure')
            os.fsync(fd);os.fsync(self.root);self.receipts.append(name)
        except BaseException as exc:self.blocked=True;self.on_fault('receipt: '+str(exc));raise
        finally:
            if fd is not None:os.close(fd)
    def normal_close(self):
        self.check_all();self.append('WINDOW_CLOSE',release_allowed=False,replay_allowed=False);self.check_all()
        os.unlink('DIRTY.json',dir_fd=self.root);os.fsync(self.root)
        for fd in (self.fd,self.lock,self.root):os.close(fd)
