"""Separate CPU proof and prepared Board provider. No software fallback."""
import copy
import os
from pathlib import Path
from livegen_platform import BoardPorts,import_original_verified
from livegen_fixtures import NativeCPUPorts
from livegen_source import MutationInterlock
from livegen_binding import Binding
from modelpl_manager import ModelManager,cpu_route
from plmode_evidence import ROOT,BUNDLE,read,save,sha
from request_journal_verified import digest
from plm_journal import need
from plmode_assets import original_asset_gate

MODES={'STRICT_CONTROL':1,'BATCH_CANDIDATE':72}
CONTRACT='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'

def fpga_route(route,*,completed=False):
    need(route['execution_kind']=='FPGA_REAL' and route['a12_domain']=='BOARD' and route['backend_id']=='A_XRT_B_KERNEL_V1' and
        route['contract_sha256']==CONTRACT and route['kernel_build_id']==0xB3030002 and route['status']=='READY' and
        route['no_silent_fallback'] is True and route['retains_resources_on_poison'] is True and
        route['hardware_done_count'] is None and route['a12_hardware_global_count'] is None and
        route['a12_hardware_global_completion_counter'] is None,'FPGA identity/status/host-only counter scope differs')
    count=route['host_verified_completions'];need(type(count) is int and 0<=count<=5000,'invalid host-verified completion count')
    need(type(route['job_id']) is int and route['job_id']==count,'FPGA job/completion differs')
    if completed:need(route['output_consumable'] is True and route['last_status_code']==0 and count>0,'unverified FPGA result')
    return count

def board_residency(route):
    keys=('owned_bo_charged_bytes','weight_load_count','a11_explicit_bo_allocations_host_counter','a11_argument_groups',
        'a11_io_bo_addresses','a11_io_bo_charged_sizes','a11_live_weights')
    return dict(BO_inventory_sha256=digest({k:route[k] for k in keys}),weight_load_count=route['weight_load_count'],owned_bo_charged_bytes=route['owned_bo_charged_bytes'])

class CPUProvider:
    domain='PC_CPU_MODEL';native_domain='PC';execution_kind='CPU_REFERENCE';approval=False
    wire_execution='PC_NATIVE_MATH_NOT_FPGA';receipt_schema='PC_REAL_MODEL_PLM_RECEIPT_V1';normal_status='PASS_ACTUAL_QWEN_PLM_CPU_WINDOW_NOT_BOARD'
    def __init__(self):
        need(os.name=='posix' and os.uname().machine=='x86_64','CPU proof provider is not a Board fallback')
        self.owner=None;self.extra_fds=();self.registry=MutationInterlock()
    def authorize_mode(self,mode,build):need(mode in MODES,'unknown permission mode')
    def fixtures(self,m):
        profile=ModelManager._fixtures(m)
        self.ports=NativeCPUPorts(m.directory/'generation-fixture',m.page.deadline,profile['adapter']);self.binding=Binding(m.page,m.build,self.ports,self.registry)
        return profile
    def argv(self,m):return ModelManager.native_argv(m)
    def env(self,m):return ModelManager.native_env(m)
    def ready(self,q,m):
        need(q['type']=='ready' and q['domain']=='PC' and q['execution_kind']=='PC_MATH_DOUBLE' and q['physical_ubatch']==8,'CPU ready differs')
        r=q['bridge']['a12_route'];need(cpu_route(r)==0 and r['pc_loads']==r['weight_count']==m.loads==72,'CPU ready counts differ')
        return r
    def route_count(self,r,completed=False):return cpu_route(r)
    def residency(self,r):return {k:r[k] for k in ('weight_load_count','weight_count','owned_weight_bytes','workspace_capacity_bytes','partial_sums_capacity_bytes','partial_sums_capture_enabled')}
    def verify_last(self,r,total):need(r['pc_last_job']==r['job_id']==total and r['pc_output_consumable'] is True,'CPU last result differs')
    def control(self,r):return r['pc_plm']
    def context(self,q,m):
        self.ports.validate_context(q['facts'],m.p.pid,m.worker_ticks)
    def native_closed(self,m):self.binding.native_finished();self.binding.close()
    def owner_finished(self,m):return True

class BoardProvider:
    domain='BOARD_PL_MODEL';native_domain='BOARD';execution_kind='FPGA_REAL';approval=True
    wire_execution='FPGA_REAL_BOUNDED_ACCEPTANCE';receipt_schema='A12_BOARD_PLM_RECEIPT_V1';normal_status='NATIVE_BOARD_WINDOW_CLOSED_OWNER_RETAINED'
    def __init__(self,owner,build):
        # Constructor performs existing live read-only gates only on the actual
        # registered ARM64 host, and NEVER constructs Owner or obtains a lease.
        need(os.name=='posix' and os.geteuid()==0 and os.uname().machine=='aarch64','prepared Board provider requires actual root ARM64 owner')
        original=import_original_verified();need(type(owner) is original.Owner,'original actual Owner required')
        b=read(build);need(owner.review.get('plmode_build_sha256')==sha(build) and
            owner.review.get('candidate_library_sha256')==b['backend_sha256'] and
            b['asset_root']==b['native_asset_root']=='/opt/patient-qwen','fresh scoped candidate build and fixed native asset root required')
        need(original_asset_gate(original)(owner,b['base_bundle'],asset_root=Path(b['asset_root']))==Path(b['model']),
            'original model path/gate differs from prepared runtime')
        self.ports=BoardPorts(owner,original);self.owner=owner;self.original=original
        self.registry=owner.platform.generation_interlock;self.extra_fds=tuple(owner.locks)
        self.binding=None
    def authorize_mode(self,mode,build):
        need(mode in MODES and self.owner.review.get('permission_mode','STRICT_CONTROL')==mode,'Board review mode differs')
        if mode=='BATCH_CANDIDATE':
            r=self.owner.review
            need(r.get('pl_mode_candidate_approved') is True and r.get('permission_grant_size')==72 and
                r.get('candidate_library_sha256')==build['backend_sha256'],'explicit scoped Board batch approval missing')
    def fixtures(self,m):
        need(m.build['domain']=='A12_PREPARED_BOARD_MODEL_PLM_V1','not a prepared Board build')
        need(m.page.deadline<=self.owner.expires,'private control exceeds original lease')
        profile=copy.deepcopy(self.ports.profile)
        profile.update(self.owner.profile_fields(),status='A12_BOUNDED_MODEL_TRIAL_NOT_ACCEPTED',device_name=self.ports.device_name,
            trial_bo_limit_bytes=140591104,a12_max_runs=5000,a12_max_loads=72)
        save(m.directory/'profile.json',profile)
        cfg=read(BUNDLE/'config/backend.pending.json');cfg.update(allow_device_access=True,kernel_source=m.build['kernel_source'],
            deployment_profile=str(m.directory/'profile.json'),xclbin_path=m.build['xclbin'],xclbin_sha256=profile['xclbin_sha256'])
        save(m.directory/'backend.json',cfg)
        route=dict(contract_sha256=CONTRACT,fallback='disabled',fpga_required=True,scope='all',execution_kind='FPGA_REAL',
            library=m.build['backend_library'],library_sha256=m.build['backend_sha256'],backend_config=str(m.directory/'backend.json'),
            backend_config_sha256=sha(m.directory/'backend.json'),a12_private_protocol='A12_PLM_PRIVATE_V1',a12_compact_completion=True,trace_limit=4096)
        save(m.directory/'route.json',route)
        # Base identity is immutable; no state/weights/long-prefix diagnostics.
        prefix=read(m.build['prefix_template']);prefix['identity']['executable_sha256']=sha(m.build['native'])
        prefix['identity']['libraries']=m.build['prefix_libraries'];save(m.directory/'prefix.json',prefix)
        self.binding=Binding(m.page,m.build,self.ports,self.registry)
        self.owner._owned_worker=m;self.owner.platform.worker=m
        return dict(profile=profile,route=route,prefix=prefix)
    def argv(self,m):return [m.build['native'],m.build['model'],'2','1024','all','TILED','2','8']
    def env(self,m):
        return dict(SP_A12_CONFIG=str(m.directory/'route.json'),SP_TT10_CONFIG=str(m.directory/'prefix.json'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1',
            LD_LIBRARY_PATH=m.build['library_search_path'])
    def ready(self,q,m):
        need(q['type']=='ready' and q['domain']=='BOARD' and q['execution_kind']=='FPGA_REAL' and q['physical_ubatch']==8,'Board native ready differs')
        r=q['bridge']['a12_route'];need(fpga_route(r)==0 and r['weight_load_count']==m.loads==72,'Board ready counts differ');return r
    def route_count(self,r,completed=False):return fpga_route(r,completed=completed)
    def residency(self,r):return board_residency(r)
    def verify_last(self,r,total):need(fpga_route(r,completed=True)==total,'Board last verified result differs')
    def control(self,r):return r['plm_control']
    def context(self,q,m):self.ports.validate_context(q['facts'],m.p.pid,m.worker_ticks)
    def native_closed(self,m):self.binding.native_finished() # no lease/lock/source finalization here
    def owner_finished(self,m):
        need(self.owner._owned_worker is m and self.owner.finished and self.owner.locks==[],'original Owner finalization not completed')
        self.binding.close();return True
