"""Bounded resident manager: warm once, at most eight requests, no quota reset."""
import copy
import math
import os
import threading
import time
import ctypes
from pathlib import Path
import promptpl_manager as parent
import plmode_manager as base
from plmode_provider import BoardProvider
from modelpl_derive import Derive
from resident_evidence import ROOT,read,save,sha
from resident_policy import Probe,IDS
from resident_journal import Journal
from request_journal_verified import canonical,digest
from plm_journal import need

class AdmissionDenied(RuntimeError):pass
class CPUProvider(parent.PromptProvider):
    def ready(self,q,m):
        route=super().ready(q,m);need(route['pc_plm']['request_limit']==9,'resident backend control revision differs');return route

class ResidentPage(base.AuthorityPage):
    def __init__(self,library,expected,**kwargs):
        need(sha(library)==expected,'resident writer changed');lib=ctypes.CDLL(str(library))
        fn=lib.a12_resident_request_limit_v1;fn.argtypes=[];fn.restype=ctypes.c_int
        need(fn()==9,'resident writer control revision differs');super().__init__(library,expected,**kwargs)

d=Derive(parent.constructor)
d.edit('self.frozen=PromptProbe(self.build);self.requests=copy.deepcopy(self.frozen.requests)',
    'self.frozen=Probe(self.build);self.requests=copy.deepcopy(self.frozen.requests)')
constructor,CTOR_EDITS=d.finish();ctor_scope=dict(parent.ctor_scope,Probe=Probe,Journal=Journal,AuthorityPage=ResidentPage);exec(compile(constructor,'<resident-constructor>','exec'),ctor_scope)
d=Derive(parent.init_text)
d.edit("type(provider) is PromptProvider and read(build)['domain']=='PC_REAL_MODEL_PLM_V1'", "type(provider) is CPUProvider and read(build)['domain']=='PC_REAL_MODEL_PLM_V1'")
init_text,INIT_EDITS=d.finish();init_scope=dict(parent.init_scope,CPUProvider=CPUProvider,scope=ctor_scope);exec(compile(init_text,'<resident-exact-provider>','exec'),init_scope)
d=Derive(parent.request)
d.edit("index==len(self.completed)<3", "index==len(self.completed)==len(self.requests)-1 and index<len(IDS)")
d.edit("hit=frozen['id']=='app_hit'", "hit=frozen['op']=='generate' and frozen['cache_policy']=='TT10_REQUIRE_HIT'")
d.edit('if hit:ordinary_comparison(self.reference,result)',"need(hit,'resident generation must restore neutral prefix')")
request,REQUEST_EDITS=d.finish();request_scope=dict(parent.request_scope,IDS=IDS);exec(compile(request,'<resident-private-request>','exec'),request_scope)
d=Derive(parent.legacy_text)
d.edit("len(self.completed)==3", "self.closeable()")
legacy_text,LEGACY_EDITS=d.finish();legacy_scope=dict(parent.legacy_scope);exec(compile(legacy_text,'<resident-idle-close-permission>','exec'),legacy_scope)
d=Derive(parent.close_text)
d.edit('len(self.completed)==3','self.closeable()')
d.edit('model_requests=3,validated_answers=2','model_requests=len(self.completed),validated_answers=len(self.completed)-1')
close_text,CLOSE_EDITS=d.finish();close_scope=dict(parent.close_scope);exec(compile(close_text,'<resident-normal-close>','exec'),close_scope)
d=Derive(parent.stdout_text)
d.edit("packets<=5+sum(r['max_tokens'] for r in self.requests if r['op']=='generate')",'packets<=228')
d.edit("('ready','token','result','cache_created','error','private_closed')","('ready','token','result','cache_created','error','private_closed','tokens')")
d.edit('capture.write(data);capture.flush();q=strict_json(data)',
    "capture.write(data);capture.flush();q=strict_json(data)\n                if q.get('type')=='tokens':need(len(data)<=8192,'resident vocab packet bound')\n                self.stream_bytes=used;self.stream_packets=packets")
stdout_text,STDOUT_EDITS=d.finish();stdout_scope=dict(parent.stdout_scope);exec(compile(stdout_text,'<resident-bounded-vocabulary-stream>','exec'),stdout_scope)

class Manager(base.Manager):
    def __init__(self,build,directory,*,cap=72,fault=None):
        need(os.name=='posix' and os.uname().machine=='x86_64','resident CPU factory requires x86_64; Board factory is separate')
        self.prefix_tokens=34;self.stream_bytes=self.stream_packets=0;self.vocab_queries=0;self.last_private_status=None
        self.current_deadline=None;self.warm_preparing=False
        init_scope['__init__'](self,build,directory,provider=CPUProvider(),cap=cap,fault=fault)
    def _guard(self):return super()._guard() and (self.current_deadline is None or time.monotonic_ns()<self.current_deadline)
    def _observe(self):
        need(self.current_deadline is None or time.monotonic_ns()<self.current_deadline,'resident application deadline expired')
        record=super()._observe()
        if self.warm_preparing:
            mem=self.source.last_health['live_health']['memory_kib']
            need(mem['MemAvailable']>=1114112+192*1024 and mem['CmaFree']>=98304,'unchanged extra prefix preparation reserve refused')
        return record
    def get(self,timeout=60):
        if self.current_deadline is not None:
            remaining=(self.current_deadline-time.monotonic_ns())/1e9
            if remaining<=0:raise TimeoutError('resident application deadline expired')
            timeout=min(timeout,remaining)
        try:return super().get(timeout)
        except __import__('queue').Empty:raise TimeoutError('resident bounded native response deadline')
    def new_tokens(self,r):
        n=len(r['tokens'])-(34 if r['cache_policy']=='TT10_REQUIRE_HIT' else 0)
        need(type(n) is int and 0<n<=128,'resident new-token bound');return n
    def _stdout(self):return stdout_scope['_stdout'](self)
    def _legacy_message(self,q):return legacy_scope['_legacy_message'](self,q)
    def closeable(self):
        return bool(self.closing and self.active is None and self.completed and self.completed==list(IDS[:len(self.completed)]))
    def admission(self,r):
        need(self._guard() and self.active is None,'resident inactive/fault gate')
        blocks=math.ceil(self.new_tokens(r)/8)+(r['max_tokens']-1 if r['op']=='generate' else 0);budget=72*blocks
        grants=math.ceil(budget/self.cap)
        if self.claims+budget>5000:raise AdmissionDenied('resident original 5000-call window budget exhausted')
        if self.journal.serial+grants+4>4096 or self.journal.size+grants*1024+4*8192>4*1024*1024:
            raise AdmissionDenied('resident original bounded journal capacity exhausted')
        if self.stream_bytes+131072+24*512+16384>1024*1024 or self.stream_packets+26>228:
            raise AdmissionDenied('resident original stdout capacity exhausted')
        return budget
    def execute(self,request):
        index=len(self.completed);need(index<len(IDS) and request['id']==IDS[index],'resident unique request order')
        self.admission(request)
        if index==0:need(request==self.requests[0],'resident warm changed')
        else:
            need(request['op']=='generate' and request['cache_policy']=='TT10_REQUIRE_HIT' and len(self.requests)==index,'resident request duplicate/operation')
            self.requests.append(copy.deepcopy(request))
        try:
            self.binding_controller.observe();result=request_scope['run_request'](self,index)
            self.last_private_status=copy.deepcopy(result['bridge']['a12_route']['a12_private_control']);return result
        except BaseException as exc:self._fail('resident request: '+str(exc));raise
    def tokenize(self,prompt):
        try:return self._tokenize(prompt)
        except AdmissionDenied:raise
        except BaseException as exc:self._fail('resident tokenizer: '+str(exc));raise
    def _tokenize(self,prompt):
        need(self._guard() and self.active is None and type(prompt) is str and 0<len(prompt.encode())<=4096 and self.vocab_queries<25,'resident pure tokenizer gate')
        before=self.page.snapshot();need(not before['active'] and not before['unknown_io'],'resident tokenizer requires idle authority')
        if self.stream_bytes+8192+16384>1024*1024 or self.stream_packets+2>228:raise AdmissionDenied('resident vocabulary stream capacity exhausted')
        request_id='vocab_'+str(self.vocab_queries);self.vocab_queries+=1
        # Vocabulary is already loaded and verified at startup. This operation
        # grants no compute; the unchanged fresh artifact gate still runs before
        # every actual model BEGIN. Avoid an additional DSO scan for tokenization.
        ticket=self.monitor.fence();wire=dict(op='tokenize',id=request_id,prompt=prompt)
        self.monitor.authorize(ticket,guard=self._guard);self.p.stdin.write(canonical(wire).decode()+'\n');self.p.stdin.flush();q=self.get(30)
        after=self.page.snapshot()
        need(q['type']=='tokens' and q['id']==request_id and q['domain']==self.provider.native_domain and q['execution_kind']=='VOCAB_ONLY_NO_BACKEND_CALL' and
            type(q['tokens']) is list and 0<len(q['tokens'])<=128 and all(type(t) is int and 0<=t<248320 for t in q['tokens']),'resident vocabulary response differs')
        for field in ('claims','request_serial','generation','grant_limit','request_sha256','context_sha256','state'):
            need(before[field]==after[field],'vocab-only operation changed compute authority')
        state=q['private_control'];need(state['enabled'] is True and state['request_active'] is state['failed'] is state['closed'] is False,'vocab-only route not idle')
        if self.last_private_status is not None:need(state==self.last_private_status,'vocab-only operation changed private route counters')
        save(self.directory/(request_id+'-TOKENS.json'),dict(request=wire,response=q,before=before,after=after))
        return q['tokens']
    def run_warm(self):
        self.warm_preparing=True
        try:
            self.tokenize(self.frozen.policy['neutral_text'])
            tokens=read(self.directory/'vocab_0-TOKENS.json')['response']['tokens'];need(tokens==self.frozen.prefix_tokens,'resident actual neutral tokenization differs')
            q=self.execute(self.requests[0]);self.last_private_status=q['bridge']['a12_route']['a12_private_control'];return q
        finally:self.warm_preparing=False
    def normal_close(self):
        self.closing=True
        result=close_scope['normal_close'](self);self.provider.native_closed(self);self.closed=self.finalized=True
        result.update(provider_domain='PC_CPU_MODEL',release_allowed=False,actual_FPGA_calls=None);return result
