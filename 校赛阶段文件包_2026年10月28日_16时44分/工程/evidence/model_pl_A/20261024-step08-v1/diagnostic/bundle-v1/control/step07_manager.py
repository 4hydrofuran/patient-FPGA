"""One reviewed l00 gate model window. No retries, forced exits or scope growth."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time

BUNDLE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BUNDLE/'platform/qwen35/a12'))
sys.path.insert(0,str(BUNDLE/'control/support'))
from common import sha,save
from window import Window
from supervisor import OwnedWorker as CPUWorker
from mlp_base import IsolatedIdleTrial,check_topology
from mlp_kernel_gate import MinimalGate
from isolated_idle_policy import BOOT_FILES,LIBRARIES,MACHINE,DEFAULT,trusted_file
from idle_board_trial import RESTORE,active_handle,check_loaded,check_removed
from accelerator_release_gate_v2 import require_release

WINDOW='a12-single-gate-20261023-v1'


class Platform(IsolatedIdleTrial):
    def __init__(self,run,boot):
        self.source=BUNDLE/'hardware';self.boot=boot;self.package=WINDOW
        self.target=Path('/lib/firmware/xilinx')/WINDOW
        self.driver=self.source/'zocl.refcount.ko'
        self.driver_sha256='388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c'
        self.log=(run/'lifecycle.jsonl').open('x');self.kernel_gate=MinimalGate()
        self.worker=None;self.release_checked=False;self.gdm_isolated=False;self.pl_mutation_started=False
        self.owner=None;self.gate_lock=threading.RLock()

    def guard(self,identity=None):
        if self.owner:self.owner.owner_check()
        if self.gdm_isolated:
            r=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,timeout=3)
            assert r.stdout.strip()==b'inactive','GDM isolation lost'
        self.snapshot('identity_health_guard');return True

    def remove(self,package):
        if package==self.package:
            assert self.release_checked and self.worker.closed and self.worker.process.returncode==0
            self.release_checked=False
        else:assert package==DEFAULT and self.worker is None
        handle=active_handle(self.command(['dfx-mgr-client','-listPackage']),package)
        self.command(['dfx-mgr-client','-remove',handle],True)


class Owner(Window):
    def __init__(self,platform,review,evidence):
        self.platform=platform
        super().__init__(review,evidence=evidence)
        platform.owner=self

    def health(self,*,closing=False):
        with self.platform.gate_lock:
            assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.boot
            self.platform.kernel_checkpoint('a12_serialized_health')
            if not closing:self.platform.snapshot('a12_health')


def receive(worker,owner,run,timeout=65):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        owner.owner_check();owner.health()
        try:r=worker.messages.get(timeout=.25)
        except queue.Empty:continue
        assert r is not None,'unexpected worker EOF'
        return r
    worker.cancel('bounded_model_deadline')
    raise RuntimeError('deadline: delivery cancelled, no kill or resource release')


def run_case(worker,owner,path,*,real):
    ready=receive(worker,owner,path);save(path/'ready.json',ready)
    assert ready['type']=='ready'
    if real:assert ready['execution_kind']=='FPGA_REAL' and ready['bridge']['a12_route']['weight_load_count']==1
    else:assert ready['execution_kind']=='CPU_REFERENCE' and ready['bridge']['weight_load_count']==72
    request=json.loads((BUNDLE/'control/request.json').read_text())
    request.update(diagnostic_dir=str(path/'diag'),diagnostic_all_layers=False,diagnostic_nodes=True,
                   diagnostic_report=True,state_fingerprint=True,dump_state=True,a12_consumer_trace=True)
    save(path/'request.json',request);worker.send(request)
    while True:
        r=receive(worker,owner,path)
        if r['type'] in ('result','error'):break
    save(path/'result.json',r)
    assert r['type']=='result' and r['status']=='OK' and r['gpu_layers']==0,r
    assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
    if real:
        route=r['bridge']['a12_route'];trace=route['a12_trace']
        assert trace and len(trace)==worker.runs==route['host_verified_completions']==3
        assert route['a12_route_scope']=='l0_gate' and route['weight_load_count']==1
        for row in trace:
            c=row['backend_completion']
            assert row['layer']==0 and row['op']=='gate' and row['consumer_verified']
            assert row['execution_kind']==c['execution_kind']=='FPGA_REAL'
            assert c['output_consumable'] and c['last_status_code']==0 and c['job_id']==row['job_id']
            assert c['a12_observed_ert_state']==4 and c['kernel_build_id']==0xB3030002
            assert len(c['a12_raw_meta_hex'])==128
    assert worker.close(timeout=10),'normal exit not proven; retain owner'
    save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,
         host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
    return r


def main():
    assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2'
    assert sha('/etc/machine-id')==MACHINE
    os.umask(0o077);run=BUNDLE/'run-v1';run.mkdir(mode=0o700)
    pins=json.loads((BUNDLE/'manifest.json').read_text())
    for row in pins['files']:
        p=BUNDLE/row['path'];trusted_file(p);assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
    assets=json.loads((BUNDLE/'control/asset-pins.json').read_text())
    for name,pin in assets.items():assert sha('/opt/patient-qwen/'+name)==pin
    for name,pin in {**BOOT_FILES,**LIBRARIES}.items():assert sha(name)==pin
    for name,pin in RESTORE.items():assert sha(Path('/lib/firmware/xilinx')/DEFAULT/name)==pin
    assert Path('/etc/dfx-mgrd/default_firmware').read_text().strip()==DEFAULT
    assert not Path('/state.txt').exists() and not Path('/sys/module/zocl').exists()
    assert not Path('/var/lock/kv260-a1/active').exists()
    assert not os.path.lexists(Path('/lib/firmware/xilinx')/WINDOW)
    for name in ('a11-mlp.bit.bin','a11-mlp.dtbo'):assert not os.path.lexists('/lib/firmware/'+name)
    for k in list(os.environ):
        if k.startswith(('SP_A12','LD_','GGML_','OMP_')):os.environ.pop(k)
    os.environ.update(LD_LIBRARY_PATH=str(BUNDLE/'bin'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='1')
    os.chmod(BUNDLE/'bin/qwen35-a12',0o700)
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    prior=json.loads((BUNDLE/'control/preflight.json').read_text());assert boot==prior['boot_id']
    p=Platform(run,boot);raw=subprocess.check_output(['dmesg','--raw']);stamp=time.monotonic_ns()
    assert raw.decode()==prior['kernel_raw'],'kernel changed after reviewed preflight'
    (run/'baseline.raw.txt').write_bytes(raw)
    assert p.kernel_gate.observe_action(boot,raw.decode(),sha(run/'baseline.raw.txt'),'none')['allowed']
    initial=p.snapshot('initial')
    assert initial['overlays']=={DEFAULT+'_image_1':'applied'} and initial['module_refcount'] is None
    assert not initial['zocl_bound'] and not initial['render_nodes'] and not initial['device_holders']
    # Admission is for ONLY l00 gate: preserve the full-range capacity limitation.
    assert initial['memory_kib']['CmaFree']-2112>=32768+65536
    assert initial['memory_kib']['MemAvailable']-2112>=1048576+65536
    review=dict(schema='A12_FRESH_WINDOW_V1',authorized_compute=True,machine_sha256=MACHINE,boot_id=boot,
        window_id=WINDOW,scope='l0_gate',max_runs=17,max_loads=1,explicit_bo_budget_bytes=2162688,
        max_session_seconds=120,bundle_sha256=sha(BUNDLE/'manifest.json'),kernel_baseline_file=str(run/'baseline.raw.txt'),
        kernel_baseline_sha256=sha(run/'baseline.raw.txt'),baseline_read_monotonic_ns=stamp)
    save(run/'review.json',review)
    s2=run/'s2';s2.mkdir();owner=None
    try:
        owner=Owner(p,review,s2)
        s1=run/'s1';s1.mkdir()
        args=[str(BUNDLE/'bin/qwen35-a12'),'/opt/patient-qwen/artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf','2','1024','all','TILED','2','8']
        cpu=CPUWorker(args,directory=s1/'worker',env=os.environ,health=owner.health,
                      max_runs=1,max_loads=1,expires=owner.expires/1e9,owner_check=owner.owner_check)
        save(s1/'identity.json',dict(pid=cpu.process.pid,argv=args,binary_sha256=sha(BUNDLE/'bin/qwen35-a12'),physical_domain='BOARD'))
        run_case(cpu,owner,s1,real=False);p.no_users(module_loaded=False)
        p.service('stop');p.wait_prepl_quiet();p.target.mkdir(mode=0o755)
        for name in ('a11-mlp.bit.bin','a11-mlp.dtbo','shell.json'):
            with (p.source/name).open('rb') as src,(p.target/name).open('xb') as dst:shutil.copyfileobj(src,dst)
            assert sha(p.target/name)==sha(p.source/name)
        p.remove(DEFAULT);check_removed(p.snapshot('default_removed'),False)
        p.command(['insmod',str(p.driver)],True);check_removed(p.snapshot('driver_unbound'),True)
        assert Path('/sys/module/zocl/srcversion').read_text().strip()=='15F2AC2306CB3CB7257CFCB'
        p.command(['dfx-mgr-client','-load',WINDOW],True);check_loaded(p.snapshot('test_loaded'),WINDOW)
        p.no_users(module_loaded=True)
        pl=owner.start_worker(BUNDLE);p.worker=pl
        save(s2/'identity.json',dict(pid=pl.process.pid,argv=pl.process.args,binary_sha256=sha(BUNDLE/'bin/qwen35-a12'),physical_domain='BOARD'))
        result=run_case(pl,owner,s2,real=True)
        check_topology(p.snapshot('worker_exited'),WINDOW)
        scan,refs,allowed=p.observation();require_release(scan,refs,allowed,boot_id=boot)
        save(run/'release-precheck.json',dict(scan=scan,refcount=refs,kernel_allowed=allowed))
        p.release_checked=True;p.remove(WINDOW);check_removed(p.snapshot('test_removed'),True)
        p.no_users(module_loaded=True);p.command(['rmmod','zocl'],True);check_removed(p.snapshot('driver_removed'),False)
        p.command(['dfx-mgr-client','-load',DEFAULT],True)
        final=p.snapshot('default_restored');assert final['overlays']==initial['overlays'] and final['vart_sha256']==initial['vart_sha256']
        p.service('start');p.snapshot('gdm_restored');owner.finish(pl)
        save(run/'result.json',dict(status='SINGLE_GATE_MODEL_EXECUTION_AND_NORMAL_RESTORE_PENDING_INDEPENDENT_AUDIT',
            physical_domain='BOARD',worker_exit_code=0,permission_submissions=pl.runs,backend_host_verified_completions=result['bridge']['a12_route']['host_verified_completions'],
            hardware_global_count=None,scope='l0_gate',lease_archived=True,step07_MLP='NOT_TESTED',step08='NOT_STARTED',board_speedup=None))
    except BaseException as exc:
        reason=type(exc).__name__+': '+str(exc)
        if owner:owner.retain_until_finished(reason)
        raise
    print(json.dumps(dict(status='SINGLE_GATE_NORMAL_EXIT',scope='l0_gate')),flush=True)


if __name__=='__main__':main()
