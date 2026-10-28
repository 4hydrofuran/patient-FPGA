"""Private PC shared atomic gate, backed by the actual adapter's C functions."""
import ctypes as c
import fcntl
import os
import secrets
import time

COUNT=0xffffffff
ACTIVE=1<<62
REVOKED=1<<63


class BatchPage:
    def __init__(self,library,*,expires_ns=None):
        self.fd=None;self.handle=None;self.closed=False
        try:self._initialize(library,expires_ns)
        except BaseException:self.close();raise
    def _initialize(self,library,expires_ns):
        self.fd=os.memfd_create('A12_PC_BATCH_TRUSTED_WORKER',os.MFD_CLOEXEC|os.MFD_ALLOW_SEALING)
        self.lib=c.CDLL(str(library))
        signatures={
            'writer_open':([c.c_int,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64],c.c_void_p),
            'health':([c.c_void_p,c.c_uint64],c.c_int),
            'bind_worker':([c.c_void_p,c.c_uint64,c.c_uint64],c.c_int),
            'begin':([c.c_void_p,c.c_uint64,c.c_uint64,c.c_char_p],c.c_int),
            'end':([c.c_void_p,c.c_uint64],c.c_int),
            'revoke':([c.c_void_p],c.c_uint64),'gate':([c.c_void_p],c.c_uint64),
            'writer_close':([c.c_void_p],None)}
        for name,(args,result) in signatures.items():
            f=getattr(self.lib,'a12_pc_batch_'+name+'_v1');f.argtypes=args;f.restype=result;setattr(self,name+'_fn',f)
        try:
            os.ftruncate(self.fd,4096);fcntl.fcntl(self.fd,fcntl.F_ADD_SEALS,
                fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL)
            self.epoch=secrets.token_hex(16);self.deadline=time.monotonic_ns()+900_000_000_000 if expires_ns is None else expires_ns
            self.handle=self.writer_open_fn(self.fd,int(self.epoch[:16],16),int(self.epoch[16:],16),self.deadline,250_000_000)
            if not self.handle:raise RuntimeError('PC page initialization refused')
        except BaseException:self.close();raise
    def gate(self):return self.gate_fn(self.handle)
    def bind_worker(self,pid,ticks):
        if self.bind_worker_fn(self.handle,pid,ticks):raise RuntimeError('PC worker identity cannot be rebound')
    def health(self,stamp):
        if self.health_fn(self.handle,stamp):raise RuntimeError('PC health publication refused')
    def begin(self,completed,budget,digest):
        if self.begin_fn(self.handle,completed,budget,digest.encode()):raise RuntimeError('PC BEGIN transition refused')
    def end(self,completed):
        if self.end_fn(self.handle,completed):raise RuntimeError('PC END transition refused')
    def revoke(self):
        if self.handle and not self.closed:return self.revoke_fn(self.handle)
    def close(self):
        if not self.closed:
            self.closed=True
            if self.handle:self.writer_close_fn(self.handle);self.handle=None
            if self.fd is not None:os.close(self.fd);self.fd=None
