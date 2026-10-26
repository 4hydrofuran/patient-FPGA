"""Actual Qwen CPU window exercises the shared live-source/native binding."""
import os
from pathlib import Path
import modelpl_manager
from generation_manager import GenerationManager
from livegen_source import MutationInterlock
from livegen_fixtures import NativeCPUPorts
from livegen_binding import Binding
from livegen_evidence import save
from request_journal_verified import digest

class Manager(modelpl_manager.ModelManager):
    _private_message=GenerationManager._private_message
    def _fixtures(self):
        profile=super()._fixtures()
        self.ports=NativeCPUPorts(self.directory/'generation-fixture',self.page.deadline,profile['adapter'])
        self.registry=MutationInterlock();self.binding_controller=Binding(self.page,self.build,self.ports,self.registry)
        self.generation=self.binding_controller.slot;self.source=self.binding_controller.source
        nodes=[dict(path=str(p),identity=list(i),link=link) for p,_,i,link in self.ports.nodes.rows]
        save(self.directory/'LIVE_SOURCE.json',dict(domain=self.ports.domain,epoch=self.source.epoch,mutation_serial=self.source.mutation_serial,
            boot=self.ports.boot,lease_sha256=self.ports.lease_sha256,node_fingerprint=self.ports.nodes.fingerprint,nodes=nodes,identity_sha256=self.source.identity_sha,
            real_Board_health=False,Board_approval=False))
        return profile
    def _generation_bind(self,ctx):
        actual=self.binding_controller.bind(self.p,self.pidfd,self.worker_ticks,self.facts)
        if actual!=ctx:raise RuntimeError('live binding context digest differs')
        self.journal.append('LIVE_GENERATION_BIND',domain=self.ports.domain,context_sha256=ctx,source_identity_sha256=self.source.identity_sha,
            generation_epoch=self.source.epoch,mutation_serial=self.source.mutation_serial,Board_approval=False)
    def _observe(self):
        if self.injection in ('same_uuid_reload','platform_mutation') and (self.page.state()&0xffffffff)>=5:
            if self.injection=='same_uuid_reload':
                self.ports.node.rename(self.ports.node.with_name('old-device-generation'))
                self.ports.node.mkdir();self.ports.attribute.write_text('PC_NO_DEVICE_SAME_UUID\n')
            else:self.registry.before('PC_ATTEMPTED_PL_RELOAD',release_check=lambda:(_ for _ in ()).throw(RuntimeError('MUST_NOT_EXECUTE_RELEASE')))
        stamp=self.binding_controller.observe();result=super()._observe();result['live_source_domain']=self.ports.domain;return result
    def _fail(self,reason):
        binding=getattr(self,'binding_controller',None)
        if binding:
            binding.revoke()
            if binding.source is not None:binding.source.blocked=True
        return super()._fail(reason)
    def native_env(self):
        env=super().native_env()
        if self.injection in ('same_uuid_reload','platform_mutation'):env['SP_A12_MODELPL_TEST_PAUSE_JOB']='5'
        return env
    def ready(self):
        q=super().ready();h=self.binding_controller.resident(q['bridge']['a12_route'])
        self.journal.append('LIVE_GENERATION_RESIDENT',CPU_residency=self.resident,resident_report_sha256=h,Board_BO_inventory=None,Board_approval=False)
        return q
    def run_request(self,index,**kwargs):self.binding_controller.observe();return super().run_request(index,**kwargs)
    def normal_close(self):
        result=super().normal_close();self.binding_controller.native_finished();self.binding_controller.close()
        result.update(live_source='PC_ACTUAL_CPU_NATIVE_BINDING_VALIDATED',Board_generation_approval=False,source_checks=self.source.checks)
        return result
