"""Reuse read-only handles/buffers, never cache a mutable file's verdict.

No inotify/mtime-only shortcut: every check consumes all current bytes. This is
an A-private no-board candidate, not device ownership or release authority.
"""
import codecs
import hashlib
import os
from pathlib import Path
import stat
import threading


class IdentityBlocked(RuntimeError):pass


def need(ok,reason):
    if not ok:raise IdentityBlocked(reason)


def pin(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns,st.st_uid,st.st_mode,st.st_nlink)


class FreshCheckedFile:
    """Pinned inode plus a fresh full digest/optional exact byte comparison."""
    def __init__(self,path,expected_sha256,*,expected_bytes=None,max_bytes=8*1024**2,chunk=65536):
        need(os.name=='posix' and hasattr(os,'preadv'),'POSIX preadv required')
        need(type(chunk) is int and 1<=chunk<=65536 and type(max_bytes) is int and 1<=max_bytes<=8*1024**2,'invalid read bound')
        self.path=Path(path);self.fd=None;self.parent=None;self.blocked=False;self.closed=False
        self.lock=threading.Lock();self.calls=0;self.bytes_read=0;self.opens=0
        self.buffer=bytearray(chunk);self.view=memoryview(self.buffer);self.expected_sha=expected_sha256
        self.expected=expected_bytes
        need(type(expected_sha256) is str and len(expected_sha256)==64 and all(c in '0123456789abcdef' for c in expected_sha256),'invalid digest')
        need(expected_bytes is None or type(expected_bytes) is bytes,'immutable expected bytes required')
        try:
            need(self.path.is_absolute() and not self.path.is_symlink(),'absolute no-symlink file required')
            self.parent=os.open(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
            self.parent_pin=os.fstat(self.parent)
            need(self.parent_pin.st_uid==os.geteuid() and not self.parent_pin.st_mode&0o022,'private owned parent required')
            self.fd=os.open(self.path.name,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW,dir_fd=self.parent);self.opens=1
            st=os.fstat(self.fd)
            need(stat.S_ISREG(st.st_mode) and st.st_uid==os.geteuid() and st.st_nlink==1 and not st.st_mode&0o022,
                 'owned single-link regular file required')
            need(0<st.st_size<=max_bytes and (expected_bytes is None or len(expected_bytes)==st.st_size),'size outside bound')
            self.identity=pin(st);self.check()
        except BaseException:
            self.blocked=True;self.close();raise

    def check(self):
        with self.lock:
            need(not self.blocked and not self.closed,'identity reader latched/closed')
            try:
                parent=self.path.parent.lstat()
                need(stat.S_ISDIR(parent.st_mode) and (parent.st_dev,parent.st_ino)==
                    (self.parent_pin.st_dev,self.parent_pin.st_ino),'canonical parent replaced')
                need(pin(os.fstat(self.fd))==self.identity and
                    pin(os.stat(self.path.name,dir_fd=self.parent,follow_symlinks=False))==self.identity,'file metadata/identity changed')
                h=hashlib.sha256();offset=0
                expected_view=memoryview(self.expected) if self.expected is not None else None
                while offset<self.identity[2]:
                    n=os.preadv(self.fd,[self.view[:min(len(self.view),self.identity[2]-offset)]],offset)
                    need(n>0,'file truncated during fresh read')
                    piece=self.view[:n];h.update(piece)
                    if expected_view is not None:need(piece==expected_view[offset:offset+n],'current bytes differ')
                    offset+=n;self.bytes_read+=n
                need(h.hexdigest()==self.expected_sha and not os.pread(self.fd,1,offset),'fresh digest/extent differs')
                need(pin(os.fstat(self.fd))==self.identity and pin(os.stat(self.path.name,dir_fd=self.parent,
                    follow_symlinks=False))==self.identity,'file changed during fresh read')
                self.calls+=1;return dict(sha256=h.hexdigest(),bytes=offset,content_read_fresh=True)
            except BaseException:
                self.blocked=True;raise

    def close(self):
        if not self.closed:
            self.closed=True
            if self.fd is not None:os.close(self.fd);self.fd=None
            if self.parent is not None:os.close(self.parent);self.parent=None


class FreshMaps:
    """Seek and scan current /proc/self/maps every call; no cached map decision."""
    def __init__(self,*,path='/proc/self/maps',limit=2*1024**2,chunk=65536):
        need(os.name=='posix' and 1<=chunk<=65536 and 1<=limit<=2*1024**2,'invalid maps read bound')
        self.fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW);self.pid=os.getpid()
        self.limit=limit;self.buffer=bytearray(chunk);self.view=memoryview(self.buffer)
        self.lock=threading.Lock();self.blocked=False;self.closed=False;self.calls=0;self.bytes_read=0
    def check(self):
        with self.lock:
            need(not self.blocked and not self.closed,'maps reader latched/closed')
            try:
                need(os.getpid()==self.pid,'maps FD inherited by a different manager')
                os.lseek(self.fd,0,os.SEEK_SET);decoder=codecs.getincrementaldecoder('utf-8')('strict')
                total=0;tail='';nonempty=False
                while True:
                    n=os.readv(self.fd,[self.view])
                    text=decoder.decode(self.view[:n],final=n==0)
                    need('libxrt_' not in tail+text,'manager maps XRT library')
                    tail=(tail+text)[-6:]
                    if not n:break
                    nonempty=True;total+=n;self.bytes_read+=n;need(total<=self.limit,'maps byte budget exceeded')
                need(nonempty,'empty/unreadable manager maps');self.calls+=1
                return dict(current_maps_read=True,bytes=total,XRT_mapped=False)
            except BaseException:
                self.blocked=True;raise
    def close(self):
        if not self.closed:self.closed=True;os.close(self.fd)
