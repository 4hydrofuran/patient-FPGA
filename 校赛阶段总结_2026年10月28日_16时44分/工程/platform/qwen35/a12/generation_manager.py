"""Frozen real-model manager plus independent PC generation consumer hooks."""
import ast
import copy
import os
from pathlib import Path
import textwrap
import time
import modelpl_manager as frozen
from generation_evidence import ROOT,OUT,PARENT,read,save,sha
from generation_binding import FixtureIssuer,Slot
from request_journal_verified import digest
from plm_journal import need

# The request/Route/CPU math implementation is frozen; add one bootstrap hook.
source=ROOT/'platform/qwen35/a12/modelpl_manager.py'
pins={r['path']:r['sha256'] for r in read(PARENT/'FINAL_REVIEW.json')['source']}
need(sha(source)==pins['platform/qwen35/a12/modelpl_manager.py'],'frozen model manager changed')
tree=ast.parse(source.read_text(encoding='utf-8'));cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='ModelManager')
method=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_private_message')
original=textwrap.dedent('\n'.join(source.read_text(encoding='utf-8').splitlines()[method.lineno-1:method.end_lineno]))
derived=original.replace('return super()._private_message(q)','return frozen.base.Manager._private_message(self,q)')
anchor="self.private_sequence=q['sequence'];self.monitor.authorize(ticket,guard=self._guard)"
need(derived.count(anchor)==1,'generation bootstrap anchor differs')
derived=derived.replace(anchor,"self._generation_bind(ctx)\n        "+anchor)
scope=dict(frozen.__dict__,frozen=frozen);exec(compile(derived,str(source)+'#generation-bootstrap','exec'),scope)

class GenerationManager(frozen.ModelManager):
    _private_message=scope['_private_message']
    def _fixtures(self):
        self.issuer=FixtureIssuer(self.directory/'generation-fixture',self.page.deadline)
        self.generation=Slot(self.page,self.build['generation_writer'],self.build['generation_writer_sha256'],self.issuer)
        return super()._fixtures()
    def _generation_bind(self,ctx):
        approval=self.issuer.issue(ctx);stamp=self.issuer.consume(approval,ctx)
        self.generation.health(stamp);self.generation.bind(ctx)
        self.journal.append('GENERATION_BIND',domain='PC_GENERATION_FIXTURE_NO_DEVICE',context_sha256=ctx,
            source_identity_sha256=self.issuer.identity_sha,generation_epoch=self.issuer.epoch,Board_approval=False)
    def _observe(self):
        if self.injection=='generation_mutate' and (self.page.state()&0xffffffff)>=5:
            # Deterministic PC failure target: fifth claim is paused before start.
            p=self.issuer.directory/'identity.json'
            raw=p.read_bytes();p.write_bytes(raw.replace(b'PC_NO_DEVICE',b'PC_BADDEVICE'))
        stamp=self.issuer.observe()
        result=super()._observe();self.generation.health(stamp)
        result['generation_source_domain']='PC_GENERATION_FIXTURE_NO_DEVICE';return result
    def _fail(self,reason):
        gen=getattr(self,'generation',None)
        if gen:gen.revoke() # first; never wait for a source-reader/Python journal lock
        return super()._fail(reason)
    def native_env(self):
        result=super().native_env()
        if self.injection=='generation_mutate':result['SP_A12_MODELPL_TEST_PAUSE_JOB']='5'
        if self.injection=='generation_slot_stale':result['SP_A12_GEN_TEST_STALE_SLOT']='1'
        return result
    def ready(self):
        q=super().ready();stamp=self.issuer.observe();self.generation.health(stamp)
        self.generation.resident(digest(self.resident))
        self.journal.append('GENERATION_RESIDENT',CPU_residency=self.resident,real_BO_inventory=None,Board_approval=False)
        return q
    def run_request(self,index,**kwargs):
        self.generation.health(self.issuer.observe());return super().run_request(index,**kwargs)
    def normal_close(self):
        result=super().normal_close();self.generation.close();self.issuer.close_normal()
        result.update(generation_consumer='PC_BOUND_TEST_ONLY',Board_generation_approval=False)
        return result
