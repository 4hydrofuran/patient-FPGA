"""A12 single-projection owner: independent DSO sequence lanes, strict phase order."""
import json
import socket
import time
from supervisor import OwnedWorker as BaseWorker


class PermissionOrder:
    def __init__(self):
        self.sequence={'router':0,'backend':0};self.router=False;self.device=False
        self.closed=False;self.weights=0;self.last_job=0

    def check(self,r,pid):
        phase=r['phase']
        if phase not in ('router_open','device_open','weight_load','submit','router_close'):
            raise ValueError('unknown phase')
        lane='router' if phase.startswith('router_') else 'backend'
        if r['pid']!=pid or type(r['sequence']) is not int or r['sequence']!=self.sequence[lane]+1:
            raise ValueError('stale/foreign per-DSO permit')
        if self.closed:raise ValueError('permit after router close')
        if phase=='router_open' and (self.router or r['job']!=0):raise ValueError('duplicate router open')
        if phase!='router_open' and not self.router:raise ValueError('router not opened')
        if phase=='device_open' and (self.device or r['job']!=0):raise ValueError('duplicate device open')
        if phase in ('weight_load','submit') and not self.device:raise ValueError('device not opened')
        if phase=='weight_load' and r['job']!=self.weights+1:raise ValueError('weight order')
        if phase=='submit' and (not self.weights or r['job']<=self.last_job):raise ValueError('job replay/order')
        if phase=='router_close' and r['job']!=0:raise ValueError('close job')
        self.sequence[lane]+=1
        return lane

    def commit(self,r):
        phase=r['phase']
        if phase=='router_open':self.router=True
        elif phase=='device_open':self.device=True
        elif phase=='weight_load':self.weights+=1
        elif phase=='submit':self.last_job=r['job']
        elif phase=='router_close':self.closed=True


class OwnedWorker(BaseWorker):
    def _permissions(self):
        order=PermissionOrder()
        with self.manager_sock.makefile('r',encoding='utf-8') as stream:
            try:
                for line in stream:
                    if len(line)>4096:raise ValueError('oversized permit')
                    r=json.loads(line);lane=order.check(r,self.process.pid);self.sequence+=1
                    if self.owner_check:self.owner_check()
                    self.health();phase=r['phase'];closing=phase=='router_close'
                    hook=getattr(self,'before_permission',None)
                    if hook:hook(r)
                    allowed=not self.quarantined and (closing or (not self.delivery_cancelled and time.monotonic()<self.expires))
                    if phase=='submit':
                        allowed=allowed and self.runs<self.max_runs
                        if allowed:self.runs+=1
                    if phase=='weight_load':
                        allowed=allowed and self.loads<self.max_loads
                        if allowed:self.loads+=1
                    if allowed:order.commit(r)
                    self.record(event='PERMISSION',request=r,allow=allowed,sequence_lane=lane,
                                observed_global_messages=self.sequence)
                    self.manager_sock.sendall((json.dumps(dict(sequence=r['sequence'],allow=allowed))+'\n').encode())
            except BaseException as exc:
                self.quarantined=True
                self.record(event='PERMISSION_FAULT_RETAIN_OWNER',reason=type(exc).__name__+': '+str(exc))
                try:self.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:pass
