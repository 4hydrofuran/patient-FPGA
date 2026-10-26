"""Actual private model protocol with a pinned facts-only PC workload.

Only workload selection, variable prefix/output accounting and bounded stdout
capacity differ. Existing health, source, local start/copy and durable delivery
checks remain in their original methods. No Board provider is accepted here.
"""
import copy
import os
from pathlib import Path
import plmode_manager as parent
from plmode_provider import CPUProvider
from livegen_fixtures import NativeCPUPorts
from livegen_binding import Binding
from modelpl_manager import ModelManager
from modelpl_derive import Derive
from promptpl_evidence import ROOT,read,sha
from promptpl_workload import PromptProbe
from plm_journal import need

d=Derive(parent.method(ROOT/'platform/qwen35/a12/modelpl_manager.py','ModelManager','_fixtures'))
d.edit("prefix=read(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02/prefix-config-PC.json')", "prefix=copy.deepcopy(self.frozen.prefix)")
fixture_text,FIXTURE_EDITS=d.finish();scope=dict(__import__('modelpl_manager').__dict__);exec(compile(fixture_text,'<facts-only-fixtures>','exec'),scope)

class PromptProvider(CPUProvider):
    def fixtures(self,m):
        profile=scope['_fixtures'](m)
        self.ports=NativeCPUPorts(m.directory/'generation-fixture',m.page.deadline,profile['adapter'])
        self.binding=Binding(m.page,m.build,self.ports,self.registry);return profile

d=Derive(parent.constructor)
d.edit('self.frozen=FrozenProbe();self.requests=copy.deepcopy(self.frozen.requests)',
    'self.frozen=PromptProbe(self.build);self.requests=copy.deepcopy(self.frozen.requests)')
constructor,CTOR_EDITS=d.finish();ctor_scope=dict(parent.scope,PromptProbe=PromptProbe);exec(compile(constructor,'<facts-only-private-constructor>','exec'),ctor_scope)
d=Derive(parent.method(ROOT/'platform/qwen35/a12/plmode_manager.py','Manager','__init__'))
d.edit("need(type(provider) in (CPUProvider,BoardProvider),'trusted typed provider required; no JSON provider selection')",
    "need(type(provider) is PromptProvider and read(build)['domain']=='PC_REAL_MODEL_PLM_V1','facts-only private experiment requires exact CPU provider/domain')")
init_text,INIT_EDITS=d.finish();init_scope=dict(parent.__dict__,PromptProvider=PromptProvider,scope=ctor_scope);exec(compile(init_text,'<facts-only-exact-PC-provider>','exec'),init_scope)

d=Derive(parent.request)
d.edit("n=len(frozen['tokens'])-(70 if frozen['id']=='app_hit' else 0)","n=self.new_tokens(frozen)")
d.edit("result['prefix_tokens']==70 and len(result['prefix_cache']['entries'])==1 and result['prefix_cache']['entries'][0]['tokens']==70",
    "result['prefix_tokens']==self.prefix_tokens and len(result['prefix_cache']['entries'])==1 and result['prefix_cache']['entries'][0]['tokens']==self.prefix_tokens")
d.edit('new=70;decode=0;content=None','self.frozen.check_warm(result);new=self.prefix_tokens;decode=0;content=None')
d.edit("new=37 if hit else 107;decode=result['decode_calls']","new=self.new_tokens(frozen);decode=result['decode_calls']")
d.edit("cache['reused_tokens']==(70 if hit else 0) and result['prompt_tokens']==107", "cache['reused_tokens']==(self.prefix_tokens if hit else 0) and result['prompt_tokens']==len(frozen['tokens'])")
d.edit("0<=decode<=7 and result['eos']", "0<=decode<frozen['max_tokens'] and result['eos']")
d.edit("0<len(tokens)<=8", "0<len(tokens)<=frozen['max_tokens']")
request,REQUEST_EDITS=d.finish();request_scope=dict(parent.request_scope);exec(compile(request,'<facts-only-private-request>','exec'),request_scope)
d=Derive(parent.method(ROOT/'platform/qwen35/a12/modelpl_manager.py','ModelManager','_stdout'))
d.edit('packets<=32',"packets<=5+sum(r['max_tokens'] for r in self.requests if r['op']=='generate')")
stdout_text,STDOUT_EDITS=d.finish();stdout_scope=dict(__import__('modelpl_manager').__dict__);exec(compile(stdout_text,'<facts-only-bounded-stream>','exec'),stdout_scope)
d=Derive(parent.close_text);d.edit("state['claims']==2880", "state['claims']==self.claims")
close_text,CLOSE_EDITS=d.finish();close_scope=dict(parent.close_scope);exec(compile(close_text,'<facts-only-counted-close>','exec'),close_scope)

class Manager(parent.Manager):
    def __init__(self,build,directory,*,cap=72,fault=None):
        need(os.name=='posix' and os.uname().machine=='x86_64','facts-only private experiment is PC only')
        self.prefix_tokens=read(build)['prefix_tokens']
        init_scope['__init__'](self,build,directory,provider=PromptProvider(),cap=cap,fault=fault)
    def new_tokens(self,request):
        n=len(request['tokens'])-(self.prefix_tokens if request['id']=='app_hit' else 0)
        need(type(n) is int and 0<n<=128,'invalid new-token accounting');return n
    def _stdout(self):return stdout_scope['_stdout'](self)
    def run_request(self,index,**kwargs):
        self.binding_controller.observe();return request_scope['run_request'](self,index,**kwargs)
    def normal_close(self):
        result=close_scope['normal_close'](self);self.provider.native_closed(self);self.closed=self.finalized=True
        result.update(provider_domain='PC_CPU_MODEL',actual_FPGA_calls=None,release_allowed=False);return result
