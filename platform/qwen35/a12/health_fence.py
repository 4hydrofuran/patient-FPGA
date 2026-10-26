"""PC candidate: independent bounded observation, fresh fences, fail latch.

Every fence requires a sample STARTED after the request. The idle interval is
not permission to reuse an earlier health verdict. No journal or socket I/O
runs under the condition lock. No board/release authority is provided.
"""
from collections import deque
from dataclasses import dataclass
import hashlib
import json
import threading
import time
import uuid


class HealthBlocked(RuntimeError):pass


@dataclass(frozen=True)
class Ticket:
    authority: object
    epoch: str
    serial: int
    thread: int
    sample: int
    requested_ns: int
    started_ns: int
    ended_ns: int
    observation: bytes


class HealthFence:
    def __init__(self,observe,*,on_fault=None,interval_s=0.25,timeout_s=1.0,max_age_s=0.25):
        if not callable(observe) or not all(type(x) in (int,float) and 0<x<=5
                for x in (interval_s,timeout_s,max_age_s)):
            raise ValueError('invalid bounded observer configuration')
        self.observe=observe;self.on_fault=on_fault
        self.interval_ns=int(interval_s*1e9);self.timeout_ns=int(timeout_s*1e9)
        self.max_age_ns=int(max_age_s*1e9);self.cv=threading.Condition()
        self.authority=object();self.epoch=uuid.uuid4().hex
        self.requested=0;self.covered=0;self.sequence=0;self.latest=None
        self.fault=None;self.closed=False;self.used={};self.issued={};self.waiters=0
        self.history=deque(maxlen=64);self.last_clock=time.monotonic_ns()
        self.stats=dict(samples=0,fences=0,authorizations=0,fault_callbacks=0)
        self.thread=threading.Thread(target=self._loop,name='a12-pc-health-fence',daemon=True)
        self.thread.start()

    def _now(self):
        now=time.monotonic_ns()
        if now<self.last_clock:raise HealthBlocked('monotonic clock moved backwards')
        self.last_clock=now;return now

    def _fault(self,reason):
        # Publish refusal first. A callback may never hold up other waiters.
        callback=None
        with self.cv:
            if self.fault is None:
                self.fault=str(reason)[:240];callback=self.on_fault
                self.cv.notify_all()
        if callback is not None:
            self.stats['fault_callbacks']+=1
            try:callback(self.fault)
            except BaseException:pass

    def _healthy(self):
        if self.fault is not None or self.closed or not self.thread.is_alive():
            raise HealthBlocked(self.fault or 'observer closed/not alive')

    def _loop(self):
        due=0
        try:
            while True:
                with self.cv:
                    while not self.closed and self.fault is None:
                        now=self._now()
                        if self.requested>self.covered or now>=due:break
                        self.cv.wait((due-now)/1e9)
                    if self.closed or self.fault is not None:return
                    serial=self.requested;started=self._now()
                observation=self.observe()
                if type(observation) is not dict:raise HealthBlocked('observation must be an object')
                raw=json.dumps(observation,ensure_ascii=False,sort_keys=True,separators=(',',':'),
                    allow_nan=False).encode('utf-8')
                if len(raw)>8192:raise HealthBlocked('observation exceeds 8192 bytes')
                with self.cv:
                    ended=self._now()
                    if ended-started>self.timeout_ns:raise HealthBlocked('observer sample exceeded timeout')
                    if self.closed or self.fault is not None:return
                    self.sequence+=1;self.covered=serial;self.stats['samples']+=1
                    self.latest=(self.sequence,serial,started,ended,raw)
                    self.history.append(dict(sequence=self.sequence,covered=serial,started_ns=started,
                        ended_ns=ended,sha256=hashlib.sha256(raw).hexdigest()))
                    due=ended+self.interval_ns;self.cv.notify_all()
        except BaseException as exc:self._fault(type(exc).__name__+': '+str(exc))

    def fence(self):
        try:
            with self.cv:
                self._healthy();requested_ns=self._now()
                # Two protocol threads are sufficient; reject accidental fan-out.
                if self.waiters>=2:raise HealthBlocked('observer waiter bound exceeded')
                self.waiters+=1;self.requested+=1;serial=self.requested;self.stats['fences']+=1
                self.cv.notify_all()
                try:
                    while True:
                        self._healthy();now=self._now()
                        if now-requested_ns>self.timeout_ns:raise HealthBlocked('fresh observation timed out')
                        sample=self.latest
                        if sample and sample[1]>=serial and sample[2]>=requested_ns:
                            tid=threading.get_ident()
                            if tid not in self.issued and len(self.issued)>=2:
                                raise HealthBlocked('issued ticket thread bound exceeded')
                            ticket=Ticket(self.authority,self.epoch,serial,tid,sample[0],
                                requested_ns,sample[2],sample[3],sample[4])
                            self.issued[tid]=ticket;return ticket
                        self.cv.wait(min(0.05,(self.timeout_ns-(now-requested_ns))/1e9))
                finally:self.waiters-=1
        except BaseException as exc:
            self._fault(type(exc).__name__+': '+str(exc));raise

    def authorize(self,ticket,*,guard=None):
        """Linearization just before send/return; subsequent work is in flight.

        No claim of revoking a permit already committed here, and no claim of
        cancelling DMA. The caller must not do disk I/O between here and send.
        """
        try:
            with self.cv:
                self._healthy();now=self._now();tid=threading.get_ident()
                # Optional caller predicate reads state/deadline only. It must
                # not log, wait, signal or perform any I/O under this lock.
                if guard is not None and not guard():raise HealthBlocked('caller boundary state/deadline refused')
                if not (isinstance(ticket,Ticket) and ticket is self.issued.get(tid) and ticket.authority is self.authority and
                        ticket.epoch==self.epoch and ticket.thread==tid and ticket.serial>self.used.get(tid,0)
                        and ticket.started_ns>=ticket.requested_ns and ticket.ended_ns<=now and
                        now-ticket.started_ns<=self.max_age_ns):
                    raise HealthBlocked('foreign/reused/stale health ticket')
                if tid not in self.used and len(self.used)>=2:raise HealthBlocked('authorization thread bound exceeded')
                self.used[tid]=ticket.serial;del self.issued[tid];self.stats['authorizations']+=1
                return dict(serial=ticket.serial,sample=ticket.sample,epoch=ticket.epoch,
                    requested_ns=ticket.requested_ns,started_ns=ticket.started_ns,
                    ended_ns=ticket.ended_ns,authorized_ns=now)
        except BaseException as exc:
            self._fault(type(exc).__name__+': '+str(exc));raise

    def status(self):
        with self.cv:
            return dict(schema='PC_FRESH_HEALTH_FENCE_V1',epoch=self.epoch,fault=self.fault,
                closed=self.closed,thread_alive=self.thread.is_alive(),waiters=self.waiters,
                counters=dict(self.stats),recent_samples=list(self.history),history_limit=64,
                observation_limit_bytes=8192,earlier_snapshot_reuse=False,
                max_age_ns=self.max_age_ns,timeout_ns=self.timeout_ns,BOARD='NOT_TESTED',
                release_allowed=False,production_binding=False)

    def stop(self,timeout=1.0):
        if not 0<=timeout<=5:raise ValueError('invalid stop timeout')
        with self.cv:self.closed=True;self.cv.notify_all()
        if threading.current_thread() is not self.thread:self.thread.join(timeout)
        return not self.thread.is_alive()
