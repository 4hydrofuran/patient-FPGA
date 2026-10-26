"""Actual model manager with typed providers and retained original Owner interface."""
import ast
import copy
import os
from pathlib import Path
import select
import textwrap
import time
import types
import threading
import modelpl_manager as frozen
import plm_page
from livegen_source import fd_identity
from plmode_evidence import ROOT,OUT,PARENT,read,save,sha
from plmode_provider import CPUProvider,BoardProvider,MODES
from request_journal_verified import canonical,digest
from plm_journal import need
from modelpl_derive import Derive

protected={r['path']:r['sha256'] for r in read(PARENT/'PRESERVATION.json')['old_source_pins']}
for name in ('modelpl_manager.py','plm_page.py'):
    path0=ROOT/'platform/qwen35/a12'/name;need(sha(path0)==protected[path0.relative_to(ROOT).as_posix()],'frozen manager/page source changed')

def method(path,cls,name):
    raw=path.read_text(encoding='utf-8');tree=ast.parse(raw);c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    n=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
    return textwrap.dedent('\n'.join(raw.splitlines()[n.lineno-1:n.end_lineno]))

# Only provider plumbing, inherited FDs and deadline selection change in ctor.
ctor_tree=ast.parse(frozen.text);c=next(n for n in ctor_tree.body if isinstance(n,ast.ClassDef) and n.name=='Manager')
n=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
constructor=textwrap.dedent('\n'.join(frozen.text.splitlines()[n.lineno-1:n.end_lineno]));d=Derive(constructor)
d.edit("need(self.build['domain']=='PC_REAL_MODEL_PLM_V1','foreign build')","need(self.build['domain'] in ('PC_REAL_MODEL_PLM_V1','A12_PREPARED_BOARD_MODEL_PLM_V1'),'foreign build')")
d.edit("self.page=Page(self.build['writer_library'],self.build['writer_sha256'])","self.page=AuthorityPage(self.build['writer_library'],self.build['writer_sha256'],deadline=self.control_deadline())")
d.edit("pass_fds=(self.child_legacy.fileno(),self.child_private.fileno(),self.page.fd,self.journal.lock)",
    "pass_fds=(self.child_legacy.fileno(),self.child_private.fileno(),self.page.fd,self.journal.lock,*self.inherited_fds())")
d.edit("domain='PC_REAL_MODEL_CPU_REFERENCE',real_device_approval=False","domain=self.provider.domain,real_device_approval=False")
d.edit('self.p=subprocess.Popen(argv,stdin=', 'self.launch_guard()\n    self.p=subprocess.Popen(argv,stdin=')
d.edit("for t in self.threads:t.start()", "for t in self.threads:t.start()\n    if self.cancel_event.is_set():self._fail('mode cancellation latched during initialization')")
constructor,CTOR_EDITS=d.finish()
page_path=ROOT/'platform/qwen35/a12/plm_page.py';d=Derive(page_path.read_text(encoding='utf-8'))
d.edit('def __init__(self,library,expected):','def __init__(self,library,expected,*,deadline=None):')
d.edit('self.deadline=time.monotonic_ns()+180_000_000_000','self.deadline=deadline if deadline is not None else time.monotonic_ns()+180_000_000_000')
page_text,PAGE_EDITS=d.finish();page_scope=dict(plm_page.__dict__);exec(compile(page_text,str(page_path)+'#owner-deadline','exec'),page_scope)
AuthorityPage=page_scope['Page']
scope=dict(frozen.base.__dict__,AuthorityPage=AuthorityPage);exec(compile(constructor,'<plmode-original-constructor>','exec'),scope)

# Preserve every request/content/graph-copy/fsync/receipt/fence check, using
# typed provider accessors for CPU vs the unchanged real XRT metadata fields.
path=ROOT/'platform/qwen35/a12/modelpl_manager.py';d=Derive(method(path,'ModelManager','run_request'))
d.edit("execution_kind='PC_NATIVE_MATH_NOT_FPGA'","execution_kind=self.provider.wire_execution")
d.edit('total=cpu_route(route)','total=self.provider.route_count(route,completed=True)')
d.edit("{k:route[k] for k in self.resident}==self.resident","self.provider.residency(route)==self.resident")
d.edit("result['domain']=='PC'","result['domain']==self.provider.native_domain")
d.edit("route['pc_last_job']==route['job_id']==total and route['pc_output_consumable'] is True", "self.last_verified(route,total)")
d.edit("route['pc_plm']['bound_request_sha256']=='' and route['pc_plm']['local_generation']==0", "self.provider.control(route)['bound_request_sha256']=='' and self.provider.control(route)['local_generation']==0")
d.edit('actual_CPU_calls=expected,final_job=total','verified_backend_calls=expected,execution_kind=self.provider.execution_kind,final_job=total')
d.edit("schema='PC_REAL_MODEL_PLM_RECEIPT_V1'","schema=self.provider.receipt_schema")
d.edit('summary=dict(actual_CPU_calls=expected,cumulative_CPU_calls=total','summary=dict(verified_backend_calls=expected,cumulative_backend_calls=total,execution_kind=self.provider.execution_kind')
d.edit("scope='PC_ONLY_RAW_TOKEN_NOT_USER_DELIVERY; SMALL_DESCRIPTIVE_SAMPLE_NOT_BOARD'","scope='BOUNDED_ACCEPTANCE_DELIVERY_GATE_NOT_UI_OR_SERVICE' ")
request,REQUEST_EDITS=d.finish();request_scope=dict(frozen.__dict__);exec(compile(request,str(path)+'#typed-provider','exec'),request_scope)
d=Derive(method(path,'ModelManager','normal_close'))
d.edit("need(self.monitor.stop(),'native health observer still live');self.normal_terminal_requested=True;self.page.revoke()",
    "need(self.monitor.stop(),'native health observer still live');self.normal_terminal_requested=True;self.native_close_verified.set();self.closure_barrier();self.page.revoke()")
close_text,CLOSE_EDITS=d.finish();close_scope=dict(frozen.__dict__);exec(compile(close_text,str(path)+'#closed-context-milestone','exec'),close_scope)

class Manager(frozen.ModelManager):
    run_request_verified=request_scope['run_request']
    close_verified_base=close_scope['normal_close']
    def __init__(self,build,directory,*,provider,cap=1,fault=None,coordinator_lock=None,cancel_event=None):
        need(not getattr(self,'_plmode_initialized',False),'a manager/context cannot be reinitialized or replayed')
        self._plmode_initialized=True;self.launch_attempted=False
        self.native_close_verified=threading.Event()
        need(type(provider) in (CPUProvider,BoardProvider),'trusted typed provider required; no JSON provider selection')
        self.provider=provider;self.coordinator_lock=coordinator_lock;self.closed=False;self.finalized=False;self.cancel_event=cancel_event or threading.Event()
        self.current_mode=next((k for k,v in MODES.items() if v==cap),None);need(self.current_mode is not None,'invalid grant mode')
        provider.authorize_mode(self.current_mode,read(build));scope['__init__'](self,build,directory,cap=cap,fault=fault)
        self.process=self.p # original Owner expects the exact owned Popen, not a PID/file substitute
    def control_deadline(self):
        return None if self.provider.owner is None else self.provider.owner.expires
    def inherited_fds(self):return tuple(self.provider.extra_fds)+(() if self.coordinator_lock is None else (self.coordinator_lock,))
    def launch_guard(self):
        need(not self.cancel_event.is_set(),'mode cancelled before native launch');self.launch_attempted=True
    def _guard(self):return not self.cancel_event.is_set() and super()._guard()
    def _fixtures(self):
        profile=self.provider.fixtures(self);self.binding_controller=self.provider.binding;self.source=self.binding_controller.source
        ports=self.provider.ports;nodes=[dict(path=str(p),identity=list(i),link=link) for p,_,i,link in ports.nodes.rows]
        save(self.directory/'LIVE_SOURCE.json',dict(domain=ports.domain,epoch=self.source.epoch,mutation_serial=self.source.mutation_serial,
            boot=ports.boot,lease_sha256=ports.lease_sha256,node_fingerprint=ports.nodes.fingerprint,nodes=nodes,identity_sha256=self.source.identity_sha,
            real_Board_health=type(self.provider) is BoardProvider,Board_approval=self.provider.approval))
        return profile
    def native_argv(self):return self.provider.argv(self)
    def native_env(self):
        env=self.provider.env(self)
        if self.injection in ('same_uuid_reload','cancel_claim'):env['SP_A12_MODELPL_TEST_PAUSE_JOB']='5'
        return env
    def _private_message(self,q):
        if q.get('phase')!='bind':return frozen.base.Manager._private_message(self,q)
        with self.lock:
            self._valid(q,self.private_sequence);need(q['schema']=='PC_PLM_BACKEND_WIRE_V1' and q['worker_start_ticks']==self.worker_ticks,'private worker incarnation differs')
            need(self.router and self.device and not self.bound and self.loads==0 and not self.active,'private bootstrap order')
            ticket=self.monitor.fence();self.provider.context(q,self);facts=q['facts'];ctx=digest(facts)
            need(q['context_sha256']==ctx,'private context digest differs')
            self.journal.append('CONTEXT_BIND',facts=facts,context_sha256=ctx,independent_board_approval=False,live_approval_pending=True)
            self.page.bind(self.p.pid,self.worker_ticks,ctx);self.context_sha=ctx;self.bound=True;self.facts=facts
            need(self.binding_controller.bind(self.p,self.pidfd,self.worker_ticks,facts)==ctx,'independent source context differs')
            self.journal.append('LIVE_GENERATION_BIND',domain=self.provider.ports.domain,context_sha256=ctx,
                source_identity_sha256=self.source.identity_sha,generation_epoch=self.source.epoch,mutation_serial=self.source.mutation_serial,Board_approval=self.provider.approval)
            self.private_sequence=q['sequence'];self.monitor.authorize(ticket,guard=self._guard)
            self.private.sendall(canonical(dict(schema=q['schema'],sequence=q['sequence'],allow=True,context_sha256=ctx)))
    def _observe(self):
        self._owned();self.journal.owner_check()
        if self.injection in ('same_uuid_reload','cancel_claim') and (self.page.state()&0xffffffff)>=5:
            if self.injection=='same_uuid_reload':
                p=self.provider.ports;p.node.rename(p.node.with_name('old-device-generation'));p.node.mkdir();p.attribute.write_text('PC_NO_DEVICE_SAME_UUID\n')
            else:raise RuntimeError('PC explicit fifth-claim cancellation')
        stamp=self.binding_controller.observe()
        return dict(domain=self.provider.domain,checked_monotonic_ns=stamp,real_Board_health=self.provider.approval)
    def _fail(self,reason):
        binding=getattr(self,'binding_controller',None)
        if binding:
            binding.revoke()
            if binding.source is not None:binding.source.blocked=True
        return super()._fail(reason)
    def cancel_authorization(self):
        if self.native_close_verified.is_set():
            # Actual closed packet was validated and observer stopped. Continue
            # the exit ACK; the coordinator still withholds a cancelled outcome.
            self.binding_controller.revoke()
        else:self._fail('explicit mode cancellation')
    def closure_barrier(self):
        callback=getattr(self,'PC_after_native_closed',None)
        if callback is not None:
            need(type(self.provider) is CPUProvider,'test closure callback refuses Board provider');callback()
    def ready(self):
        q=self.get(timeout=120);route=self.provider.ready(q,self)
        need(q['bridge']['cpu_run_count']==q['bridge']['weight_count']==0,'unselected CPU fallback at ready')
        pc=route['a12_private_control'];need(pc['enabled'] is True and pc['request_active'] is False and pc['closed'] is False and pc['failed'] is False,'Route private hooks not ready')
        self.resident=self.provider.residency(route);self.binding=q['prefix_cache']['binding_sha256']
        need(q['prefix_cache']['enabled'] is True and len(self.binding)==64 and
            q['prefix_cache']['identity']['verified_loaded_libraries']==self.profile['prefix']['identity']['libraries'],'loaded prefix/libraries differ')
        self.loaded_identity();self.page.load_end();self.journal.append('READY',native_sha256=digest(q),weights=72,execution_kind=self.provider.execution_kind,hardware_completions=None)
        h=self.binding_controller.resident(route)
        self.journal.append('LIVE_GENERATION_RESIDENT',resident_signature=self.resident,resident_report_sha256=h,Board_approval=self.provider.approval)
        save(self.directory/'READY.json',q);self.ready_packet=q;self.reference=None;self.raw_first_tokens={};return q
    def last_verified(self,route,total):self.provider.verify_last(route,total);return True
    def run_request(self,index,**kwargs):self.binding_controller.observe();return self.run_request_verified(index,**kwargs)
    def normal_close(self):
        result=self.close_verified_base();self.provider.native_closed(self);self.closed=True
        result.update(status=self.provider.normal_status,provider_domain=self.provider.domain,actual_FPGA_calls=None,release_allowed=False)
        # Board source/lease remains live until the original restore and finish.
        self.finalized=type(self.provider) is CPUProvider;return result
    def finish_original_owner(self):
        need(self.closed and self.process.returncode==0,'normal native exit/interface not proven')
        self.provider.owner_finished(self);self.finalized=True
    def retain_board_failure(self,reason):
        need(type(self.provider) is BoardProvider,'only an actual Board owner can park')
        self._fail(reason);self.provider.owner._owned_worker=self
        self.provider.owner.retain_until_finished(reason)
