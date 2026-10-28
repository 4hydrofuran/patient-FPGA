"""PC-only ports. Real Linux FDs and nodes; synthetic device/CMA values are tagged.

These ports cannot construct a BoardPorts, load a Board issuer or activate ARM.
No BO payload or tensor allocation is needed to test the original BO policy.
"""
import copy
import os
from pathlib import Path
import time
from generation_binding import FixtureIssuer
from livegen_source import NodePins
from livegen_platform import BoardPorts
from livegen_evidence import bundle_pin,read
from plm_journal import need

def context_fixture(pid,start_ticks,boot):
    p=read(bundle_pin('config/profile.pending.json'))
    return dict(schema='A12_PL_CONTEXT_UNBOUND_V1',production_enabled=False,board_generation_approval='UNBOUND',worker_pid=pid,worker_start_ticks=start_ticks,
        boot_id=boot+'\n',context_generation='PC_FIXTURE_CONTEXT_ONLY_0001',xclbin_sha256=p['xclbin_sha256'],xclbin_uuid=p['xclbin_uuid'],kernel_build_id=p['kernel_build_id'],
        device_name='PC_FIXTURE_NO_DEVICE',device_index=0,groups=[3]*6,windows=[[0,2147483648]]*6,io_addresses=[0,40960,49152,204800],io_sizes=[40960,8192,155648,8192])

def resident_fixture(context):
    cursor=sum(context['io_sizes']);weights=[];charge=119*8192
    for _ in range(72):
        weights.append(dict(addresses=[cursor,cursor+charge],charged_sizes=[charge,charge]));cursor+=charge*2
    need(cursor==140591104,'fixture geometry differs')
    return dict(owned_bo_charged_bytes=140591104,weight_load_count=72,a11_explicit_bo_allocations_host_counter=148,a11_argument_groups=[3]*6,
        a11_io_bo_addresses=context['io_addresses'],a11_io_bo_charged_sizes=context['io_sizes'],a11_live_weights=weights)

class FixturePorts:
    domain='PC_LIVE_SOURCE_PL_POLICY_FIXTURE_NO_DEVICE'
    def __init__(self,directory,expires):
        self.base=FixtureIssuer(directory,expires);self.expires=expires;self.boot=self.base.boot.strip()
        self.lease_sha256=self.base.readers[0].expected_sha;self.profile=read(bundle_pin('config/profile.pending.json'));self.device_name='PC_FIXTURE_NO_DEVICE'
        self.node=Path(directory)/'device-generation';self.node.mkdir()
        self.attribute=self.node/'identity';self.attribute.write_text('PC_NO_DEVICE_SAME_UUID\n')
        self.nodes=NodePins([self.node,self.attribute]);self.kernel_allowed=True;self.memory=1114112;self.cma=98304;self.temp=32000
        self.closing=False;self.skipped=False;self.health_calls=0;self.full_resident=False
    def owner_check(self):self.base.observe()
    def identity_check(self):need(self.attribute.read_text()=='PC_NO_DEVICE_SAME_UUID\n','PC generation attribute changed')
    def health(self):
        self.health_calls+=1
        return dict(closing=self.closing,checks_skipped=self.skipped,kernel=dict(allowed=self.kernel_allowed,sha256='PC_FIXTURE_NOT_KERNEL_LOG'),
            live_health=dict(memory_kib=dict(MemAvailable=self.memory,CmaFree=self.cma),temperatures_mC=[self.temp],
                full_resident=self.full_resident,actual_reserve=dict(allowed=True) if self.full_resident else None,
                measurement_domain='PC_SYNTHETIC_BOARD_HEALTH_NOT_A_MEASUREMENT'),checked_monotonic_ns=time.monotonic_ns())
    def validate_context(self,facts,pid,start_ticks):return BoardPorts.validate_context(self,facts,pid,start_ticks)
    def validate_resident(self,route,context):return BoardPorts.validate_resident(self,route,context)
    def mark_resident(self):self.full_resident=True
    def close_observers(self):self.nodes.close();self.base.close_normal()
    def test_cleanup(self):self.nodes.close();self.base._test_cleanup()

class NativeCPUPorts(FixturePorts):
    domain='PC_ACTUAL_CPU_MODEL_LIVE_SOURCE_FIXTURE_NO_DEVICE'
    def __init__(self,directory,expires,config):super().__init__(directory,expires);self.config=config
    def health(self):
        self.memory=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
        return super().health()
    def validate_context(self,facts,pid,start_ticks):
        cfg=self.config;r=facts['actual_CPU_fresh_report']
        need(facts['schema']=='A12_MODEL_PLM_CPU_CONTEXT_V1' and facts['execution_kind']=='CPU_REFERENCE' and
            facts['worker_pid']==pid and facts['worker_start_ticks']==start_ticks and facts['boot_id'].strip()==self.boot and facts['context_generation'] and
            facts['cpu_library_sha256']==cfg['cpu_library_sha256'] and facts['cpu_config_sha256']==cfg['cpu_config_sha256'] and
            facts['contract_sha256']==cfg['contract_sha256'] and facts['real_device_generation_approval']=='UNBOUND_PC_CPU_ONLY' and
            r['execution_kind']=='CPU_REFERENCE' and r['cpu_run_count']==r['weight_count']==0 and r['hardware_done_count'] is None,
            'independent CPU live-source context differs')
    def validate_resident(self,route,context):
        need(route['execution_kind']=='CPU_REFERENCE' and route['weight_count']==route['weight_load_count']==route['pc_loads']==72 and
            route['cpu_run_count']==0 and route['partial_sums_capture_enabled'] is False and route['kernel_build_id'] is None and
            route['hardware_done_count'] is None,'actual CPU residency differs; no synthetic BO substitution')
