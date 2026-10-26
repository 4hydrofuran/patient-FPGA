"""Manager owns the native atomic writer, never mutates mmap words in Python."""
import ctypes as c
import fcntl
import json
import os
import secrets
import time
from plm_evidence import sha

COUNT=0xffffffff;ACTIVE=1<<62;REVOKED=1<<63;UNKNOWN=(1<<61)|(1<<60)|(1<<59)
class Page:
    def __init__(self,library,expected):
        assert sha(library)==expected
        self.fd=os.memfd_create('A12_PLM_PC_CONTROL_ONLY',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        self.lib=c.CDLL(str(library));self.handle=None;self.closed=False;self.epoch=secrets.token_hex(16)
        self.deadline=time.monotonic_ns()+180_000_000_000
        sig={
            'writer_open':([c.c_int,c.c_uint64,c.c_uint64,c.c_uint64],c.c_void_p),
            'health':([c.c_void_p,c.c_uint64],c.c_int),'bind':([c.c_void_p,c.c_uint64,c.c_uint64,c.c_char_p],c.c_int),
            'load_end':([c.c_void_p],c.c_int),'begin':([c.c_void_p,c.c_uint64,c.c_uint64,c.c_char_p],c.c_int),
            'grant':([c.c_void_p,c.c_uint64,c.c_uint64],c.c_int),'end':([c.c_void_p,c.c_uint64],c.c_int),
            'revoke':([c.c_void_p],c.c_uint64),'state':([c.c_void_p],c.c_uint64),
            'snapshot':([c.c_void_p,c.c_char_p,c.c_uint64],c.c_int),'writer_close':([c.c_void_p],c.c_int)}
        for name,(args,result) in sig.items():
            f=getattr(self.lib,'a12_plm_'+name+'_v1');f.argtypes=args;f.restype=result;setattr(self,name+'_fn',f)
        os.ftruncate(self.fd,4096);fcntl.fcntl(self.fd,fcntl.F_ADD_SEALS,fcntl.F_SEAL_SEAL|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_GROW)
        self.handle=self.writer_open_fn(self.fd,int(self.epoch[:16],16),int(self.epoch[16:],16),self.deadline)
        if not self.handle:os.close(self.fd);raise RuntimeError('PLM atomic writer refused')
    def call(self,name,*args):
        if self.closed or getattr(self,name+'_fn')(self.handle,*args):raise RuntimeError('PLM atomic '+name+' refused')
    def health(self,n):self.call('health',n)
    def bind(self,pid,ticks,digest):self.call('bind',pid,ticks,digest.encode())
    def load_end(self):self.call('load_end')
    def begin(self,base,budget,digest):self.call('begin',base,budget,digest.encode())
    def grant(self,first,last):self.call('grant',first,last)
    def end(self,count):self.call('end',count)
    def revoke(self):return self.revoke_fn(self.handle) if not self.closed else REVOKED
    def state(self):return self.state_fn(self.handle)
    def snapshot(self):
        b=c.create_string_buffer(4096);self.call('snapshot',b,4096);return json.loads(b.value)
    def close(self):
        if not self.closed:
            self.call('writer_close');self.closed=True;self.handle=None;os.close(self.fd)
