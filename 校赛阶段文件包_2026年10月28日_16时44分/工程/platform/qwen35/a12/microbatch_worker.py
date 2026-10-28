"""Bounded manager grants and real backend-local authority, PC only."""
import copy
import json
import re
import socket
import threading
import time
import types

from health_fence import HealthFence
from microbatch_evidence import ROOT,sha
from microbatch_page import COUNT,ACTIVE,REVOKED
from request_journal_verified import FrozenProbe,require,canonical,digest

path=ROOT/'platform/qwen35/a12/native_request_journal.py'
require(sha(path)=='7416272af99c86d6ad6418a6289c0d777e9cf1695a16605af9800c13a79ffa05','frozen native journal differs')
base=types.ModuleType('microbatch_frozen_journal');base.__file__=str(path)
exec(compile(path.read_bytes(),str(path),'exec'),base.__dict__)
base.SCHEMA='PC_NATIVE_MICROBATCH_JOURNAL_V1'


class BatchController(base.NativeRequestController):
    def __init__(self,worker,ready,identity):
        super().__init__(worker,ready,identity)
        try:self._binding(ready)
        except BaseException:worker._isolate('PC batch ready binding failed');raise

    def _binding(self,result):
        w=self.worker;b=result['bridge']['a12_route']['pc_batch']
        require(b['worker_epoch']==w.worker_epoch and b['manager_epoch']==w.page.epoch and
            b['context_sha256']==w.context_sha256 and b['bound_worker_pid']==w.process.pid and
            b['bound_worker_start_ticks']>0,'actual native batch instance/context binding differs')

    def finish(self,result):
        try:self._binding(result);return super().finish(result)
        except BaseException:self.worker._isolate('PC batch result binding/validation failed');raise

    @staticmethod
    def _cpu_route(route):
        require(route.get('pc_adapter')=='A12_NATIVE_CPU_MICROBATCH_V1','microbatch adapter identity differs')
        b=route['pc_batch']
        require(b['schema']=='PC_MICROBATCH_LOCAL_BUDGET_V3' and b['revoked'] is False and b['inflight_or_unknown'] is False and
            b['hardware_completions'] is None and b['local_claims']==b['shared_claims']==route['pc_started_calls'],
            'microbatch actual local/global claims differ')
        # Reuse all unchanged CPU math/lifecycle checks after explicitly checking
        # the NEW private identity. Never edit the real response to fake V1.
        normalized=dict(route,pc_adapter='A12_NATIVE_CPU_CONTROL_V1')
        base.NativeRequestController._cpu_route(normalized)


class BatchWorker(base.NativeJournalWorker):
    def __init__(self,*args,page,context_sha256,grant_size=72,**kw):
        require(kw.get('real',False) is False and grant_size in (1,72),'unbound PC batch worker')
        self.page=page;self.context_sha256=context_sha256;self.grant_size=grant_size
        self.worker_epoch=None;self.batch_serial=0;self.result_boundaries=[];self._health_local=threading.local()
        self.permission_metrics=dict(calls=0,owner_check_ms=0.0,health_check_ms=0.0,durable_permission_record_ms=0.0)
        self._batch_ready=False;self.requests=FrozenProbe().requests
        observe=kw['health'];owner_check=kw['owner_check']
        def sample():
            start=time.monotonic_ns();owner_check();value=observe();page.health(start);return value
        def failed(reason):
            page.revoke()
            if self._batch_ready:self._isolate('PC batch monitor: '+reason)
        self.monitor=HealthFence(sample,on_fault=failed,interval_s=0.05)
        def fresh():
            ticket=self.monitor.fence();self._health_local.ticket=ticket;return json.loads(ticket.observation)
        kw['health']=fresh
        try:super().__init__(*args,**kw);self._batch_ready=True
        except BaseException:page.revoke();self.monitor.stop();raise

    def _isolate(self,reason):
        self.page.revoke();return super()._isolate(reason)

    def _durable(self,**row):
        return super()._durable(**dict(row,batch_size=self.grant_size,
            counter_semantics='MANAGER_RESERVED_JOB_RANGES_NOT_PER_PROJECTION_IPC_OR_HARDWARE'))

    def _begin_verified(self,token,request,budget,meta):
        super()._begin_verified(token,request,budget,meta)
        frozen=next(r for r in self.requests if r['id']==request['id'])
        n=len(frozen['tokens'])-(70 if request['id']=='app_hit' else 0)
        self.plan=[min(8,n-i) for i in range(0,n,8)]+([1]*(frozen['max_tokens']-1) if frozen['op']!='cache_create' else [])
        require(len(self.plan)*72==budget,'batch work graph budget differs')
        self.page.begin(self.runs,budget,digest(request))

    def _finish_verified(self,*args,**kw):
        # Native controller already checked actual counts and quiescent state.
        # End invalidates all unused local grants before durable END/delivery.
        self.page.end(self.runs)
        super()._finish_verified(*args,**kw)
        stamp=self.monitor.authorize(getattr(self._health_local,'ticket',None),
            guard=lambda:not self.quarantined and not self.delivery_cancelled and not self._request_failed and
                time.monotonic()<self.expires and not self.page.gate()&(REVOKED|ACTIVE))
        self.result_boundaries.append(dict(stamp,request_id=self._completed_ids[-1],end_sha256=self._chain))

    def _permissions(self):
        sequences=dict(router=0,backend=0);router=False;device=False;closed=False
        try:
            with self.manager_sock.makefile('r',encoding='utf-8') as stream:
                for line in stream:
                    require(len(line)<=4096,'oversize batch request');q=json.loads(line)
                    phase=q['phase'];lane='router' if phase.startswith('router_') else 'backend'
                    require(type(q['pid']) is int and q['pid']==self.process.pid and type(q['job']) is int and
                        0<=q['job']<=5000 and type(q['batch_protocol']) is int and q['batch_protocol']==1 and
                        type(q['sequence']) is int and q['sequence']==sequences[lane]+1 and
                        q['manager_epoch']==self.page.epoch and q['context_sha256']==self.context_sha256 and not closed,
                        'foreign/replayed batch control request')
                    require(type(q['worker_epoch']) is str and re.fullmatch('[0-9a-f]{32}',q['worker_epoch']),
                        'invalid worker epoch')
                    self.worker_epoch=self.worker_epoch or q['worker_epoch']
                    require(q['worker_epoch']==self.worker_epoch,'worker restarted/changed')
                    gate_start=time.monotonic_ns();self.owner_check();owner_end=time.monotonic_ns()
                    health=self.health();health_end=time.monotonic_ns()
                    with self._request_lock:
                        require(not self.quarantined and not self._request_failed and
                            (phase=='router_close' or not self.delivery_cancelled and time.monotonic()<self.expires),
                            'cancelled/expired batch window')
                        reply=dict(sequence=q['sequence'],allow=True,worker_epoch=self.worker_epoch,
                            manager_epoch=self.page.epoch,context_sha256=self.context_sha256)
                        if phase=='router_open':
                            require(not router and q['job']==0,'duplicate router open')
                            stat=(__import__('pathlib').Path('/proc')/str(q['pid'])/'stat').read_text()
                            ticks=int(stat[stat.rfind(')')+2:].split()[19])
                            require(q['process_start_ticks']==ticks,'worker process start differs')
                            self.page.bind_worker(q['pid'],ticks);router=True
                        elif phase=='device_open':
                            require(router and not device and q['job']==0,'CPU open order');device=True
                        elif phase=='weight_load':
                            require(device and self.loads<72 and q['job']==self.loads+1 and self._active_request is None,
                                'weight load order');self.loads+=1
                        elif phase=='router_close':
                            require(router and device and self._active_request is None and len(self._completed_ids)==3 and
                                q['job']==0,'close before request completion');closed=True;self._router_close_seen=True
                        elif phase=='batch':
                            a=self._active_request;g=self.page.gate()
                            require(device and a is not None and q['job']==self.runs+1 and q['job']==(g&COUNT)+1 and
                                q['request_generation']==(g>>32)&0xffff and q['request_sha256']==digest(self._wire),
                                'batch request generation/range differs')
                            index=(self.runs-a['base'])//72
                            require(index<len(self.plan) and type(q['T']) is int and q['T']==self.plan[index],
                                'batch T/work graph differs')
                            count=min(self.grant_size,72-(self.runs-a['base'])%72)
                            require(a['permits']+count<=a['budget'] and self.runs+count<=self.max_runs,'batch budget exceeded')
                            first=self.runs+1;self.runs+=count;a['permits']+=count;self.batch_serial+=1
                            reply.update(first_job=first,last_job=self.runs,count=count,T=q['T'],
                                request_generation=q['request_generation'],request_sha256=q['request_sha256'],
                                deadline_monotonic_ns=self.page.deadline)
                            for job in range(first,self.runs+1):
                                item=dict(sequence=q['sequence'],job=job,pid=q['pid'])
                                a['digest'].update(canonical(item)+b'\n');self._recent_submits.append(item)
                            self._durable(event='MICROBATCH_GRANT',request=q,grant=reply,
                                request_id=a['id'],cumulative_reserved_jobs=self.runs,health_observation=health)
                        else:raise RuntimeError('unknown batch phase')
                        if phase!='batch':self.record(event='PERMISSION',request=q,allow=True,
                            sequence_lane=lane,health_observation=health)
                        sequences[lane]=q['sequence'];self.sequence+=1
                    record_end=time.monotonic_ns();self.permission_metrics['calls']+=1
                    self.permission_metrics['owner_check_ms']+=(owner_end-gate_start)/1e6
                    self.permission_metrics['health_check_ms']+=(health_end-owner_end)/1e6
                    self.permission_metrics['durable_permission_record_ms']+=(record_end-health_end)/1e6
                    self.monitor.authorize(getattr(self._health_local,'ticket',None),guard=lambda:
                        not self.quarantined and not self._request_failed and not self.page.gate()&REVOKED and
                        (phase=='router_close' or not self.delivery_cancelled and time.monotonic()<self.expires))
                    self.manager_sock.sendall(canonical(reply)+b'\n')
        except BaseException as exc:
            self._isolate(type(exc).__name__+': '+str(exc))
            try:self.record(event='PERMISSION_FAULT_RETAIN_OWNER',reason=self._io_fault)
            except BaseException:pass
        finally:
            if self._active_request is not None:self._isolate('batch control EOF during request')
            self._permission_done.set()

    def close(self,timeout=3):
        okay=super().close(timeout);stopped=self.monitor.stop()
        return okay and stopped and self.monitor.status()['fault'] is None
