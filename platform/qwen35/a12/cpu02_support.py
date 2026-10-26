"""Pure immutable representations and fresh checks; no cached health decisions."""
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import re
import stat
import threading


@dataclass(frozen=True)
class Snapshot:
    text: str
    payload: bytes
    sha256: str


class SnapshotCache:
    """At most two immutable texts; identity lookup cannot accept a changed text."""
    def __init__(self):
        self.entries=[];self.hits=0;self.misses=0;self.lock=threading.Lock()

    def get(self,text):
        if type(text) is not str:raise TypeError('exact immutable str required')
        with self.lock:
            for item in self.entries:
                if item.text is text:
                    self.hits+=1;return item
            payload=text.encode('utf-8')
            item=Snapshot(text,payload,hashlib.sha256(payload).hexdigest())
            # Oversize checks remain with the original caller and its error type.
            # Never retain an oversize entry in the two-slot cache.
            if len(payload)<=8388608:self.entries=[item,*self.entries[:1]]
            self.misses+=1
            return item


CACHE=SnapshotCache()
def snapshot(text):return CACHE.get(text)
def digest(text):return snapshot(text).sha256


def owned_lock_fds(paths,fds,pid):
    """Every invocation freshly checks canonical inode, actual FD and FLOCK state."""
    if pid!=os.getpid() or len(paths)!=len(fds):return False
    pattern=r'(?m)^lock:\s+\d+:\s+FLOCK\s+ADVISORY\s+WRITE\s+'+str(pid)+r'\s'
    for path,fd in zip(paths,fds):
        canonical=Path(path).stat();current=os.fstat(fd)
        if (canonical.st_dev,canonical.st_ino)!=(current.st_dev,current.st_ino):return False
        if not re.search(pattern,Path('/proc/self/fdinfo',str(fd)).read_text()):return False
    return True


class DurableJournal:
    """One existing JSONL format, one fsync per record, identity/size checked fresh.

    The FD is reused, while path existence/inode and offset are never cached as
    decisions. New directory entry is fsynced before the first successful return.
    Any uncertain persistence latches this writer closed to further records.
    """
    def __init__(self,path):
        self.path=Path(path);self.fd=None;self.size=0;self.blocked=False;self.closed=False

    def append(self,payload):
        if self.blocked or self.closed:raise OSError('journal blocked/closed')
        try:
            created=False
            if self.fd is None:
                self.fd=os.open(self.path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_EXCL|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
                self.identity=os.fstat(self.fd);created=True
            canonical=self.path.lstat();current=os.fstat(self.fd)
            if not stat.S_ISREG(canonical.st_mode) or canonical.st_nlink!=1 or current.st_nlink!=1:
                raise OSError('journal type/link changed')
            if (canonical.st_dev,canonical.st_ino)!=(self.identity.st_dev,self.identity.st_ino) or (current.st_dev,current.st_ino)!=(self.identity.st_dev,self.identity.st_ino):
                raise OSError('journal replaced')
            if current.st_size!=self.size:raise OSError('journal truncated/extended')
            import cpu01b_observer as ob
            with ob.span('record.write'):
                pending=memoryview(payload)
                while pending:
                    count=os.write(self.fd,pending)
                    if count<=0:raise OSError('journal short write without progress')
                    pending=pending[count:]
            # Raw FD has no Python buffer. Successful write completes that stage.
            with ob.span('record.fsync'):os.fsync(self.fd)
            if created:
                directory=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
                try:os.fsync(directory)
                finally:os.close(directory)
            self.size+=len(payload)
            if os.fstat(self.fd).st_size!=self.size:raise OSError('journal append extent differs')
        except BaseException:
            self.blocked=True
            raise

    def close(self):
        if not self.closed:
            self.closed=True
            if self.fd is not None:os.close(self.fd);self.fd=None
