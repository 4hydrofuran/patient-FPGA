"""PC-only second journal candidate: result-gated commits and fail-closed I/O.

No board binding, recovery, permit batching, cached health or release authority.
The frozen permission loop is delegated unchanged; its OS error exit is fenced.
"""
import ast
import copy
import errno
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import threading
import types
import uuid

from request_journal_candidate import RequestJournalCandidate, RequestJournalBlocked
from resource_probe_policy import integer, ordinary_comparison, validate_plan

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2'
MANIFEST_SHA = '4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f'
SCHEMA = 'PC_REQUEST_JOURNAL_V2'
MAX_RECORD = 32768
MAX_LOG = 512 * 1024
MAX_RECORDS = 256
ZERO = '0' * 64


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def require(value, reason):
    if not value:raise RequestJournalBlocked(reason)


class FrozenProbe:
    """Load only pinned config and pure checker/BO helpers, never a manager."""
    def __init__(self):
        raw=(BUNDLE/'manifest.json').read_bytes()
        require(hashlib.sha256(raw).hexdigest()==MANIFEST_SHA, 'frozen manifest differs')
        pins={r['path']:r for r in json.loads(raw)['files']}
        def pinned(name):
            raw=(BUNDLE/name).read_bytes();pin=pins[name]
            require(len(raw)==pin['bytes'] and hashlib.sha256(raw).hexdigest()==pin['sha256'],
                    'frozen dependency differs: '+name)
            return raw
        self.requests=json.loads(pinned('control/requests.json'))
        self.spec=json.loads(pinned('control/window-spec.json'))
        validate_plan(self.requests,self.spec)
        self.template=pinned('control/chat_template.jinja').decode()
        manager=pinned('control/resource_probe_manager.py').decode()
        node=next(n for n in ast.parse(manager).body if isinstance(n,ast.FunctionDef) and n.name=='validate_bo')
        scope={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'pinned_validate_bo','exec'),scope)
        self.bo=scope['validate_bo']
        prefix='_a12_journal_pinned_application'
        for name,path in ((prefix,'application/system_qwen35'),(prefix+'.app','application/system_qwen35/app')):
            if name not in sys.modules:
                package=types.ModuleType(name);package.__path__=[str(BUNDLE/path)];sys.modules[name]=package
        for short in ('domain','planning','checking'):
            name=prefix+'.app.'+short;path='application/system_qwen35/app/'+short+'.py'
            raw=pinned(path)
            if name not in sys.modules:
                module=types.ModuleType(name);module.__file__=str(BUNDLE/path)
                module.__package__=prefix+'.app';sys.modules[name]=module
                exec(compile(raw,module.__file__,'exec'),module.__dict__)
        self.domain=sys.modules[prefix+'.app.domain']
        self.planning=sys.modules[prefix+'.app.planning']
        self.checking=sys.modules[prefix+'.app.checking']
        for name in ('SYN_CP_01','SYN_CP_02','SYN_CP_03'):pinned('application/system_qwen35/cases/'+name+'.json')

    def check_answer(self, request, result):
        item=request['application'];case=self.domain.load_case(item['case_id'])
        transcript=self.domain.Transcript.parse(dict(request_id=request['id'],text=item['question'],source='typed',final=True))
        plan=self.planning.plan(case,transcript,())
        require(case.sha256==item['case_sha256'] and digest(plan.to_dict())==digest(item['plan']),
                'frozen application facts differ')
        check=self.checking.check(plan,result['text'])
        require(check['status']=='pass','original content checker rejected model text')
        return check


class VerifiedJournalMixin(RequestJournalCandidate):
    """Only instantiate with a no-device PC fixture; real/ARM remain refused."""
    def __init__(self,*args,**kwargs):
        self._window_id=uuid.uuid4().hex
        self._serial=0;self._chain=ZERO
        self._persistence_failed=False;self._io_fault=None
        self._permission_done=threading.Event();self._half_closed=False
        self._verified_meta=None;self._wire=None;self._sent=False
        self._controller_token=None;self._completed_ids=[]
        self._normal_receipt_written=False;self._router_close_seen=False
        super().__init__(*args,**kwargs)

    def _isolate(self, reason):
        # Keep all counters, process/FD ownership and unknown request state.
        self._request_failed=True;self.quarantined=True;self.delivery_cancelled=True
        self._io_fault=self._io_fault or str(reason)[:240]
        if not self._half_closed and hasattr(self,'manager_sock'):
            self._half_closed=True
            try:self.manager_sock.shutdown(socket.SHUT_WR)
            except OSError:pass

    def _durable(self,**row):
        if self._persistence_failed:raise OSError(errno.EIO,'journal failure latched; no retry')
        payload=dict(row,schema=SCHEMA,window_id=self._window_id,record_serial=self._serial+1,
                     previous_record_sha256=self._chain,domain='PC_CONTROL_FIXTURE_NOT_HARDWARE')
        if self._verified_meta is not None and row.get('event') in ('REQUEST_BEGIN_PC_CANDIDATE','REQUEST_END_PC_CANDIDATE'):
            payload['verified_request']=copy.deepcopy(self._verified_meta)
        payload['record_sha256']=digest(payload)
        try:
            require(self._serial<MAX_RECORDS and len(canonical(payload))+64<=MAX_RECORD and
                    getattr(getattr(self,'_journal',None),'size',0)+len(canonical(payload))+64<=MAX_LOG,
                    'bounded journal capacity exceeded')
            super()._durable(**payload)
        except BaseException as exc:
            self._persistence_failed=True;self._isolate(type(exc).__name__+': '+str(exc));raise
        self._serial+=1;self._chain=payload['record_sha256']

    def _permissions(self):
        try:
            super()._permissions()
        except BaseException as exc:
            # The inherited handler may itself fail while recording its fault.
            self._isolate('permission handler: '+type(exc).__name__+': '+str(exc))
        finally:
            if self._active_request is not None:self._isolate('permission EOF during request')
            self._permission_done.set()

    def _reader(self):
        try:super()._reader()
        except BaseException as exc:
            self._isolate('reader handler: '+type(exc).__name__+': '+str(exc))
            self.messages.put(None)

    def record(self,**row):
        super().record(**row)
        if row.get('event')=='PERMISSION' and row.get('allow') is True and row.get('request',{}).get('phase')=='router_close':
            self._router_close_seen=True

    def _attach(self, gate):
        require(self._controller_token is None and self._active_request is None,'duplicate controller binding')
        self._controller_token=gate

    def begin_request(self,*args,**kwargs):
        self._fail('scalar request start disabled; use verified controller')

    def end_request(self,*args,**kwargs):
        self._fail('scalar completion assertions disabled; use result validation')

    def _begin_verified(self,token,request,budget,meta):
        require(token is self._controller_token,'foreign controller')
        self._verified_meta=copy.deepcopy(meta);self._wire=copy.deepcopy(request);self._sent=False
        RequestJournalCandidate.begin_request(self,request['id'],budget)

    def send(self,request):
        with self._request_lock:
            if (self._active_request is None or self._sent or digest(request)!=digest(self._wire)):
                self._fail('foreign, changed or duplicate request send')
            super().send(request);self._sent=True

    def _write_receipt(self,name,value):
        require('/' not in name and '\\' not in name,'unsafe receipt name')
        raw=canonical(value)+b'\n';require(len(raw)<=8192,'receipt too large')
        fd=None;parent=None
        try:
            parent=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent)
            pending=memoryview(raw)
            while pending:
                n=os.write(fd,pending);require(n>0,'receipt short write without progress');pending=pending[n:]
            os.fsync(fd);os.fsync(parent)
        except BaseException as exc:
            self._isolate('receipt persistence: '+type(exc).__name__+': '+str(exc))
            # An END line alone must never be interpreted as a successful commit.
            try:self.record(event='RECEIPT_PERSISTENCE_FAULT_RETAIN_OWNER',reason=self._io_fault)
            except BaseException:pass
            raise
        finally:
            if fd is not None:os.close(fd)
            if parent is not None:os.close(parent)

    def _finish_verified(self,token,result,summary):
        require(token is self._controller_token and self._sent,'foreign/unsent result')
        request_id=self._active_request['id']
        self._verified_meta.update(result_sha256=digest(result),validation_sha256=digest(summary))
        RequestJournalCandidate.end_request(self,request_id,cumulative_completions=self.runs,
                                            pending=0,state_cleared=True,outcome='VALIDATED')
        self._write_receipt('COMMIT-'+request_id+'.json',dict(schema=SCHEMA,window_id=self._window_id,
            request_id=request_id,end_record_sha256=self._chain,verified_request=self._verified_meta,
            replay_allowed=False,release_allowed=False,scope='PC_FORMAT_RECEIPT_NOT_RELEASE_PROOF'))
        self._completed_ids.append(request_id)
        self._verified_meta=None;self._wire=None

    def close(self,timeout=3):
        with self._request_lock:
            if self.closed and self._normal_receipt_written and not self._request_failed:return True
            if self._request_failed or self._active_request is not None or len(self._completed_ids)!=3:
                self._isolate('close refused: incomplete/failed window')
                try:self.record(event='V2_CLOSE_REFUSED_RETAIN_OWNER',reason=self._io_fault)
                except BaseException:pass
                return False
        try:
            if not super().close(timeout):return False
            require(self._router_close_seen and self._permission_done.is_set() and
                    not self.permission_thread.is_alive() and not self.reader_thread.is_alive(),
                    'normal exit lacks confirmed router close or stopped protocol threads')
            self._write_receipt('NORMAL_CLOSE.json',dict(schema=SCHEMA,window_id=self._window_id,
                last_record_sha256=self._chain,exit_code=0,request_ids=self._completed_ids,
                cumulative_permits=self.runs,release_allowed=False,replay_allowed=False))
            self._normal_receipt_written=True
            return True
        except BaseException as exc:
            self._isolate('close persistence: '+type(exc).__name__+': '+str(exc));return False


class VerifiedRequestController:
    """Bounded R0/warm/hit result gate, PC-only. No scalar completion bypass."""
    def __init__(self,worker,ready):
        try:self._initialize(worker,ready)
        except BaseException as exc:
            worker._isolate('controller initialization: '+type(exc).__name__+': '+str(exc))
            try:worker.record(event='CONTROLLER_REFUSED_RETAIN_OWNER',reason=worker._io_fault)
            except BaseException:pass
            raise

    def _initialize(self,worker,ready):
        require(worker.real is False,'BOARD controller unbound')
        require(callable(worker.owner_check) and callable(worker.health),'fresh owner/health callbacks required')
        self.worker=worker;self.frozen=FrozenProbe();self.next=0;self.active=None;self.previous=0;self.reference=None
        route=ready['bridge']['a12_route']
        require(ready.get('type')=='ready' and ready.get('execution_kind')=='FPGA_REAL' and
                ready.get('physical_ubatch')==8 and ready.get('fixture_domain')=='PC_CONTROL_FIXTURE',
                'requires explicitly labelled PC protocol fixture')
        self._route_identity(route)
        require(worker.loads==72 and worker.runs==0 and type(route['host_verified_completions']) is int
                and route['host_verified_completions']==0,'ready count/load mismatch')
        self.spans=self.frozen.bo(route);self.weights=copy.deepcopy(route['a11_live_weights'])
        require(all(type(a) is int and type(n) is int and a%8192==0 for a,n in self.spans),
                'BO address/size type or alignment differs')
        self.binding=ready['prefix_cache']['binding_sha256']
        require(ready['prefix_cache'].get('enabled') is True and type(self.binding) is str and
                len(self.binding)==64 and all(c in '0123456789abcdef' for c in self.binding),'invalid prefix binding')
        self.ready_sha=digest(ready);worker._attach(self)

    @staticmethod
    def _route_identity(route):
        require(route.get('execution_kind')=='FPGA_REAL' and type(route.get('kernel_build_id')) is int
                and route['kernel_build_id']==0xB3030002,'native backend/build differs')

    def begin(self,request_id):
        w=self.worker
        with w._request_lock:
            try:
                require(self.active is None and self.next<3,'request window complete/active')
                frozen=copy.deepcopy(self.frozen.requests[self.next])
                require(request_id==frozen['id'],'frozen request order differs')
                wire={k:v for k,v in frozen.items() if k not in ('application','tokens')}
                if wire['op']=='cache_create' or wire['cache_policy']!='R0':wire['cache_binding_sha256']=self.binding
                n=len(frozen['tokens'])-(70 if request_id=='app_hit' else 0)
                budget=72*((n+7)//8+(0 if wire['op']=='cache_create' else wire['max_tokens']-1))
                w._begin_verified(self,wire,budget,dict(request_sha256=digest(wire),
                    frozen_request_sha256=digest(frozen),ready_sha256=self.ready_sha,binding_sha256=self.binding,
                    base_completions=self.previous))
                self.active=frozen;w.send(wire)
                return copy.deepcopy(wire)
            except BaseException:
                w._isolate('request begin failed');raise

    def finish(self,result):
        w=self.worker
        with w._request_lock:
            try:
                request=self.active;require(request is not None and not w._request_failed and not w.quarantined
                    and not w.delivery_cancelled,'no healthy active request')
                require(result.get('id')==request['id'] and result.get('status')=='OK' and
                    result.get('type')==('cache_created' if request['op']=='cache_create' else 'result'),
                    'wrong native terminal result')
                require(result.get('fixture_domain')=='PC_CONTROL_FIXTURE','result lacks PC fixture label')
                require(result.get('state_cleared_before_response') is True and
                    type(result.get('state_position_after_clear')) is int and result['state_position_after_clear']==-1,
                    'active state clear missing')
                require(result['prefix_cache']['binding_sha256']==self.binding,'cache binding drift')
                route=result['bridge']['a12_route'];self._route_identity(route)
                require(digest(self.frozen.bo(route))==digest(self.spans) and
                        digest(route['a11_live_weights'])==digest(self.weights),
                        'BO/residency inventory differs')
                if request['op']=='cache_create':
                    entries=result['prefix_cache']['entries']
                    require(len(entries)==1 and type(entries[0]['tokens']) is int and entries[0]['tokens']==70,
                            'captured prefix differs')
                    new,decode=70,0;content=None
                else:
                    cache=result['prefix_cache_request'];hit=request['id']=='app_hit'
                    require(cache['hit'] is hit and type(cache['reused_tokens']) is int and
                        cache['reused_tokens']==(70 if hit else 0),'actual cache path differs')
                    new=len(request['tokens'])-(70 if hit else 0);decode=result['decode_calls']
                    require(type(cache['new_tokens']) is int and cache['new_tokens']==new and
                        integer(decode,0,request['max_tokens']-1),'work/token bounds differ')
                    require(result.get('eos') is True and type(result.get('gpu_layers')) is int and result['gpu_layers']==0 and
                        type(result.get('prompt_tokens')) is int and result['prompt_tokens']==len(request['tokens'])
                        and type(result.get('output_tokens')) is list and 0<len(result['output_tokens'])<=8
                        and all(integer(t,0,248319) for t in result['output_tokens']), 'EOS/output evidence differs')
                    content=self.frozen.check_answer(request,result)
                    ordinary_comparison(result,result)  # Original required evidence shape/digest.
                    if hit:ordinary_comparison(self.reference,result)
                expected=72*((new+7)//8+decode)
                require(type(route['host_verified_completions']) is int and
                    route['host_verified_completions']==w.runs==self.previous+expected and
                    w.loads==72,'permission/host-verified completion reconciliation failed')
                # This reuses the protected native producer's per-run completion/meta verification.
                # It does not turn fixture counters into hardware evidence.
                w.owner_check();w.health()
                summary=dict(content=content,request_permits=expected,cumulative_permits=w.runs,
                             state_cleared=True,cache_binding_sha256=self.binding,BO_spans_unchanged=True,
                             domain='PC_CONTROL_FIXTURE_NOT_HARDWARE')
                w._finish_verified(self,result,summary)
                if request['id']=='app_R0':self.reference=copy.deepcopy(result)
                self.previous=w.runs;self.active=None;self.next+=1
                return summary
            except BaseException as exc:
                w._isolate('result validation: '+type(exc).__name__+': '+str(exc))
                try:w.record(event='RESULT_REJECTED_RETAIN_OWNER',reason=w._io_fault)
                except BaseException:pass
                raise
