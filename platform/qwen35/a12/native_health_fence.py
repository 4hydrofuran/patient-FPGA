"""Derived native PC worker. Frozen journal/permission sources stay unchanged."""
import json
import threading
import time

from health_fence import HealthFence,HealthBlocked
from native_request_journal import NativeJournalWorker


class FencedSocket:
    def __init__(self,sock,worker):self.sock=sock;self.worker=worker
    def __getattr__(self,name):return getattr(self.sock,name)
    def sendall(self,raw,*args,**kwargs):
        row=json.loads(raw)
        if row.get('allow') is True:
            # Frozen loop records before send. Recheck after that blocking I/O.
            ticket=getattr(self.worker._health_local,'ticket',None)
            context=getattr(self.worker._health_local,'context',None)
            if context is None or row.get('sequence')!=context['sequence']:
                self.worker.monitor._fault('permit reply not bound to fresh request')
                raise HealthBlocked('unbound permit reply')
            self.worker._health_boundary(ticket,closing=context['phase']=='router_close')
            self.worker._health_local.context=None
        return self.sock.sendall(raw,*args,**kwargs)


class HealthFencedNativeWorker(NativeJournalWorker):
    def __init__(self,*args,**kwargs):
        if kwargs.get('real',False):raise HealthBlocked('BOARD health fence is unbound')
        self._health_local=threading.local();self._health_ready=False;self.health_result_boundaries=[]
        observe=kwargs['health']
        def failed(reason):
            if self._health_ready:self._isolate('health monitor: '+reason)
        self.monitor=HealthFence(observe,on_fault=failed)
        def fresh():
            ticket=self.monitor.fence();self._health_local.ticket=ticket
            return dict(json.loads(ticket.observation),pc_health_fence=dict(epoch=ticket.epoch,
                serial=ticket.serial,sample=ticket.sample,requested_ns=ticket.requested_ns,
                started_ns=ticket.started_ns,ended_ns=ticket.ended_ns))
        kwargs['health']=fresh
        try:
            super().__init__(*args,**kwargs);self._health_ready=True
            if self.monitor.status()['fault']:self._isolate('health fault during worker initialization')
        except BaseException:
            self.monitor.stop();raise

    def _permissions(self):
        # Installed on the protocol thread before it can send its first reply.
        self.manager_sock=FencedSocket(self.manager_sock,self)
        return super()._permissions()

    def before_permission(self,request):
        super().before_permission(request)
        self._health_local.context=dict(request)

    def _health_boundary(self,ticket,*,closing=False):
        return self.monitor.authorize(ticket,guard=lambda:not self.quarantined and
            not self._request_failed and (closing or
                (not self.delivery_cancelled and time.monotonic()<self.expires)))

    def _finish_verified(self,*args,**kwargs):
        super()._finish_verified(*args,**kwargs)
        # Controller's fresh health precedes END+receipt. A later fault/stall
        # refuses delivery even when that earlier END already reached disk.
        try:
            stamp=self._health_boundary(getattr(self._health_local,'ticket',None))
            self.health_result_boundaries.append(dict(stamp,end_record_sha256=self._chain,
                completed_request=self._completed_ids[-1]))
        except BaseException:
            self._isolate('health fault/stale after request END')
            try:self.record(event='HEALTH_END_REFUSED_RETAIN_OWNER',reason=self._io_fault)
            except BaseException:pass
            raise

    def close(self,timeout=3):
        okay=super().close(timeout)
        stopped=self.monitor.stop()
        return okay and stopped and self.monitor.status()['fault'] is None
