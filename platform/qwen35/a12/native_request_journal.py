"""Real PC model integration for request journaling; never a BOARD binding."""
import copy
import errno
import json
import os
import sys

from request_journal_verified import (BUNDLE, FrozenProbe, VerifiedJournalMixin,
    canonical, digest, require, RequestJournalBlocked)
from request_journal_candidate import RequestJournalCandidate
from resource_probe_policy import integer, ordinary_comparison

sys.path.insert(0,str(BUNDLE/'platform/qwen35/a12'))
import cpu01b_observer as observer
observer.ENABLED=False
from cpu01b_supervisor import OwnedWorker

SCHEMA='PC_NATIVE_REQUEST_JOURNAL_V3'
DOMAIN='PC_NATIVE_MATH_NOT_FPGA'


class NativeJournalWorker(VerifiedJournalMixin,OwnedWorker):
    def __init__(self,*args,journal_mode='request',**kwargs):
        require(journal_mode in ('request','strict'),'unknown native journal mode')
        self.journal_mode=journal_mode
        super().__init__(*args,**kwargs)

    def _durable(self,**row):
        if self._persistence_failed:raise OSError(errno.EIO,'journal failure latched; no retry')
        # Keep prior error/ownership/receipt machinery; bind the new authentic
        # execution domain instead of relabelling PC results as hardware/fixtures.
        payload=dict(row,schema=SCHEMA,window_id=self._window_id,record_serial=self._serial+1,
            previous_record_sha256=self._chain,domain=DOMAIN,journal_mode=self.journal_mode)
        if 'completion_domain' in payload:payload['completion_domain']=DOMAIN
        if 'caller_asserted_cumulative_completions' in payload:
            payload['native_cpu_verified_completions']=payload.pop('caller_asserted_cumulative_completions')
        if self._verified_meta is not None and row.get('event') in ('REQUEST_BEGIN_PC_CANDIDATE','REQUEST_END_PC_CANDIDATE'):
            payload['verified_request']=copy.deepcopy(self._verified_meta)
        limit_rows=6000 if self.journal_mode=='strict' else 256
        limit_bytes=16*1024**2 if self.journal_mode=='strict' else 512*1024
        try:
            payload['record_sha256']=digest(payload);size=len(canonical(payload))+64
            require(self._serial<limit_rows and size<=32768 and
                getattr(getattr(self,'_journal',None),'size',0)+size<=limit_bytes,'bounded native journal exceeded')
            RequestJournalCandidate._durable(self,**payload)
        except BaseException as exc:
            self._persistence_failed=True;self._isolate(type(exc).__name__+': '+str(exc));raise
        self._serial+=1;self._chain=payload['record_sha256']

    def record(self,**row):
        super().record(**row)
        if row.get('event') in ('PERMISSION_FAULT_RETAIN_OWNER','BAD_WORKER_PROTOCOL'):
            self._io_fault=self._io_fault or row.get('reason',row['event'])
        if (self.journal_mode=='strict' and row.get('event')=='PERMISSION' and row.get('allow') is True
                and row.get('request',{}).get('phase')=='submit'):
            self._durable(**row)

    def _write_receipt(self,name,value):
        value=dict(value,schema=SCHEMA)
        super()._write_receipt(name,value)


class NativeRequestController:
    """One real PC R0/warm/hit sequence. Final result cannot precede durable END."""
    def __init__(self,worker,ready,identity):
        self.worker=worker;self.frozen=FrozenProbe();self.next=0;self.active=None;self.pending=None
        self._tokens=[]
        self.previous=0;self.reference=None;self.identity=copy.deepcopy(identity)
        try:
            require(worker.real is False and worker.max_runs==5000 and worker.max_loads==72,
                    'native controller requires bounded PC worker')
            require(ready.get('type')=='ready' and ready.get('domain')=='PC' and
                    ready.get('execution_kind')=='PC_MATH_DOUBLE' and ready.get('physical_ubatch')==8,
                    'expected authentic PC_MATH_DOUBLE ready')
            require(ready['bridge']['cpu_run_count']==0 and ready['bridge']['weight_count']==0,
                    'unrouted CPU context is not empty')
            route=ready['bridge']['a12_route'];self._cpu_route(route)
            require(route['cpu_run_count']==route['pc_verified_completions']==worker.runs==0
                    and worker.loads==route['pc_loads']==72,'ready CPU counts differ')
            self.resident={k:route[k] for k in ('weight_load_count','weight_count','owned_weight_bytes',
                'workspace_capacity_bytes','partial_sums_capacity_bytes','partial_sums_capture_enabled')}
            self.binding=ready['prefix_cache']['binding_sha256'];self.ready_sha=digest(ready)
            require(type(self.binding) is str and len(self.binding)==64 and ready['prefix_cache']['enabled'] is True,
                    'PC prefix not ready')
            loaded=ready['prefix_cache']['identity']['verified_loaded_libraries']
            require(loaded.get('liba12_native_cpu_control.so')==identity['adapter_sha256'] and
                    loaded.get('libsp_linear_cpu.so')==identity['cpu_library_sha256'],'native loaded identity differs')
            worker._attach(self)
        except BaseException as exc:
            worker._isolate('native ready: '+type(exc).__name__+': '+str(exc));raise

    @staticmethod
    def _cpu_route(route):
        require(route.get('execution_kind')=='CPU_REFERENCE' and route.get('a12_domain')=='PC_MATH_DOUBLE'
            and route.get('pc_domain')==DOMAIN and route.get('pc_adapter')=='A12_NATIVE_CPU_CONTROL_V1'
            and route.get('a12_route_scope')=='all' and route.get('hardware_done_count') is None
            and route.get('kernel_build_id') is None and route.get('a12_hardware_global_count') is None,
            'CPU adapter identity/hardware distinction differs')
        require(route.get('status')=='READY' and route.get('cpu_quiescent') is True and
            route.get('pc_poisoned') is False and route.get('pc_closing') is False,'CPU route not healthy/quiescent')
        for key in ('pc_attempted_calls','pc_started_calls','pc_verified_completions','pc_failed_calls','cpu_run_count','pc_loads'):
            require(integer(route.get(key)),'invalid native CPU counter: '+key)
        require(route['pc_failed_calls']==0 and route['pc_attempted_calls']==route['pc_started_calls']==
                route['pc_verified_completions']==route['cpu_run_count'],'actual CPU lifecycle counters differ')

    def wire(self,frozen):
        # Application requests use production prompt input. Neutral warm must
        # retain its token list; dropping it was invisible to old ID-only fixtures.
        request={k:copy.deepcopy(v) for k,v in frozen.items()
                 if 'application' not in frozen or k not in ('application','tokens')}
        if request['op']=='cache_create' or request['cache_policy']!='R0':request['cache_binding_sha256']=self.binding
        return request

    def arm(self,request_id):
        with self.worker._request_lock:
            try:
                require(not self.worker._request_failed and not self.worker.quarantined and not self.worker.delivery_cancelled
                    and self.pending is None and self.active is None and self.next<3,'prior native request active/failed/complete')
                frozen=copy.deepcopy(self.frozen.requests[self.next]);require(frozen['id']==request_id,'native order differs')
                self.pending=frozen
                bound=copy.deepcopy(frozen)
                if bound['op']=='cache_create' or bound['cache_policy']!='R0':bound['cache_binding_sha256']=self.binding
                return bound
            except BaseException as exc:
                self.worker._isolate('native arm: '+type(exc).__name__+': '+str(exc));raise

    def send(self,wire):
        w=self.worker
        with w._request_lock:
            try:
                require(self.pending is not None and digest(wire)==digest(self.wire(self.pending)),
                        'changed/duplicate native wire request')
                frozen=self.pending;n=len(frozen['tokens'])-(70 if frozen['id']=='app_hit' else 0)
                budget=72*((n+7)//8+(0 if frozen['op']=='cache_create' else frozen['max_tokens']-1))
                w._begin_verified(self,wire,budget,dict(request_sha256=digest(wire),frozen_request_sha256=digest(frozen),
                    ready_sha256=self.ready_sha,binding_sha256=self.binding,base_completions=self.previous,
                    native_identity_sha256=digest(self.identity)))
                self.active=frozen;self.pending=None;self._tokens=[];w.send(wire)
            except BaseException as exc:
                w._isolate('native send: '+type(exc).__name__+': '+str(exc));raise

    def accept_token(self,event):
        w=self.worker
        with w._request_lock:
            try:
                require(self.active is not None and not w._request_failed and not w.quarantined and
                    self.active['op']=='generate' and event.get('type')=='token' and
                    event.get('id')==self.active['id'] and type(event.get('index')) is int and
                    event['index']==len(self._tokens)<self.active['max_tokens'] and
                    integer(event.get('token'),0,248319),'native token stream invalid/foreign/oversize')
                self._tokens.append(event['token'])
            except BaseException as exc:
                w._isolate('native token: '+type(exc).__name__+': '+str(exc));raise

    def finish(self,result):
        w=self.worker
        with w._request_lock:
            try:
                request=self.active
                require(request is not None and not w._request_failed and not w.quarantined and
                        not w.delivery_cancelled,'no healthy native request')
                require('fixture_domain' not in result and result.get('id')==request['id'] and result.get('status')=='OK' and
                    result.get('type')==('cache_created' if request['op']=='cache_create' else 'result'),
                    'native terminal status/identity differs')
                require(result.get('state_cleared_before_response') is True and
                    type(result.get('state_position_after_clear')) is int and result['state_position_after_clear']==-1,
                    'native state not cleared')
                require(result['prefix_cache']['binding_sha256']==self.binding,'native prefix binding changed')
                bridge=result['bridge'];route=bridge['a12_route'];self._cpu_route(route)
                require(bridge['execution_kind']=='CPU_REFERENCE' and bridge['cpu_run_count']==0 and
                        bridge['weight_count']==0 and bridge['error']=='','unselected CPU fallback observed')
                require(digest({k:route[k] for k in self.resident})==digest(self.resident),
                        'CPU weight/workspace residency changed')
                if request['op']=='cache_create':
                    entries=result['prefix_cache']['entries'];require(len(entries)==1 and entries[0]['tokens']==70
                        and result.get('prefix_tokens')==70 and not self._tokens,'native warm prefix differs')
                    new,decode,content=70,0,None
                else:
                    cache=result['prefix_cache_request'];hit=request['id']=='app_hit';new=37 if hit else 107
                    require(cache['hit'] is hit and type(cache['new_tokens']) is int and cache['new_tokens']==new
                        and type(cache['reused_tokens']) is int and cache['reused_tokens']==(70 if hit else 0),
                        'actual native R0/hit work differs')
                    decode=result['decode_calls'];require(integer(decode,0,7) and result['eos'] is True and
                        result['teacher_forced'] is False and type(result['gpu_layers']) is int and result['gpu_layers']==0
                        and result['prompt_tokens']==107 and result['domain']=='PC' and
                        type(result['output_tokens']) is list and result['output_tokens']==self._tokens and
                        0<len(self._tokens)<=request['max_tokens'],'natural native generation differs')
                    content=self.frozen.check_answer(request,result);ordinary_comparison(result,result)
                    if hit:ordinary_comparison(self.reference,result)
                expected=72*((new+7)//8+decode)
                require(route['pc_verified_completions']==w.runs==self.previous+expected and
                    route['pc_last_job']==route['job_id']==w.runs and route['pc_output_consumable'] is True
                    and route['last_status_code']==0 and w.loads==72,'native CPU permit/completion reconciliation failed')
                w.owner_check();w.health()
                summary=dict(domain=DOMAIN,content=content,new_prefill_tokens=new,decode_calls=decode,
                    actual_cpu_calls=expected,cumulative_cpu_calls=w.runs,hardware_completions=None,
                    state_cleared=True,native_resident_sha256=digest(self.resident))
                w._finish_verified(self,result,summary)
                if request['id']=='app_R0':self.reference=copy.deepcopy(result)
                self.previous=w.runs;self.active=None;self.next+=1
                return summary
            except BaseException as exc:
                w._isolate('native result: '+type(exc).__name__+': '+str(exc))
                try:w.record(event='NATIVE_RESULT_REJECTED_RETAIN_OWNER',reason=w._io_fault)
                except BaseException:pass
                raise
