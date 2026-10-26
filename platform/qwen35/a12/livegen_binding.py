"""Reusable binding from a live Source to the native atomic consumer."""
import ctypes as c
import json
import os
from pathlib import Path
from plm_journal import need
from request_journal_verified import digest
from livegen_source import Source
from livegen_platform import BoardPorts
from livegen_evidence import sha

class ReadOnlyPage:
    def __init__(self,page,library,expected):
        need(sha(library)==expected,'RO page observer changed');self.lib=c.CDLL(str(library));self.fd=None
        self.fn=self.lib.a12_plm_observe_fd_v1;self.fn.argtypes=[c.c_int,c.c_char_p,c.c_uint64];self.fn.restype=c.c_int
        self.fd=os.open('/proc/self/fd/'+str(page.fd),os.O_RDONLY|os.O_CLOEXEC)
    def __call__(self):
        need(self.fd is not None,'RO page observer closed');out=c.create_string_buffer(4096)
        need(self.fn(self.fd,out,4096)==0,'held RO page observe refused');return json.loads(out.value)
    def close(self):
        if self.fd is not None:os.close(self.fd);self.fd=None

class AuthoritySlot:
    def __init__(self,page,library,expected,source):
        need(sha(library)==expected,'live generation writer changed');self.lib=c.CDLL(str(library));self.handle=None;self.closed=False
        signatures={'health':([c.c_void_p,c.c_uint64],c.c_int),'bind':([c.c_void_p,c.c_char_p],c.c_int),
            'resident':([c.c_void_p,c.c_char_p],c.c_int),'revoke':([c.c_void_p],c.c_uint64),'close':([c.c_void_p],c.c_int)}
        for name,(args,result) in signatures.items():
            fn=getattr(self.lib,'a12_gen_'+name+'_v1');fn.argtypes=args;fn.restype=result;setattr(self,name+'_fn',fn)
        name='a12_livegen_board_open_v1' if type(source.ports) is BoardPorts else 'a12_gen_open_v1'
        fn=getattr(self.lib,name);fn.argtypes=[c.c_int,c.c_char_p,c.c_char_p];fn.restype=c.c_void_p
        self.handle=fn(page.fd,source.identity_sha.encode(),source.epoch.encode());need(self.handle,'native issuer/domain initialization refused')
    def call(self,name,*args):need(not self.closed and self.handle and getattr(self,name+'_fn')(self.handle,*args)==0,'live native slot '+name+' refused')
    def revoke(self):
        if self.handle and not self.closed:self.revoke_fn(self.handle)
    def close(self):self.call('close');self.closed=True;self.handle=None

class Binding:
    def __init__(self,page,build,ports,interlock):
        self.page=page;self.slot=None;self.observer=None;self.source=None
        self.source=Source(ports,interlock,self.revoke)
        self.slot=AuthoritySlot(page,build['generation_writer'],build['generation_writer_sha256'],self.source)
        self.observer=ReadOnlyPage(page,build['observer_library'],build['observer_sha256'])
    def revoke(self):
        if self.slot is not None:self.slot.revoke()
        self.page.revoke()
        if self.source is not None:self.source.ports.nodes.close() # after atomic revocation, observer FDs only
    def bind(self,process,pidfd,start_ticks,facts):
        self.source.attach_worker(process,pidfd,start_ticks,self.observer)
        capability=self.source.issue(facts);ctx=digest(facts);stamp=self.source.consume(capability,ctx)
        self.slot.call('health',stamp);self.slot.call('bind',ctx.encode());return ctx
    def resident(self,route):
        h=self.source.seal_resident(route);self.slot.call('health',self.source.last_started_ns);self.slot.call('resident',h.encode());return h
    def observe(self):
        stamp=self.source.observe();self.page.health(stamp);self.slot.call('health',stamp);return stamp
    def native_finished(self):self.source.finish_native() # keep page/FDs for original restore/release gates
    def close(self):
        need(self.source.normal_terminal,'native generation not normally terminal')
        if type(self.source.ports) is BoardPorts:
            owner=self.source.ports.owner
            need(self.source.interlock.retired and owner.finished and owner.locks==[],
                'original restore/final release must finish before borrowed observers close')
        self.slot.close();self.source.close_observers();self.observer.close()
