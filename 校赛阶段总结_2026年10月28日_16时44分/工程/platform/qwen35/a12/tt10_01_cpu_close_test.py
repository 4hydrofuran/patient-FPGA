"""PC-only close/finalization tests: real Linux children/flocks; platform fixtures.

Real source04 model runs cover CPU cooperation only. No FPGA/GDM/kernel/module
operations execute: those observations are explicit fixtures, never BOARD proof.
"""
import argparse
import ast
import contextlib
import copy
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
sys.dont_write_bytecode=True
import threading
import time
import types
import unittest
from unittest.mock import patch
from tt10_01_common import ROOT,OUT,WORK,j,sha,save

BASE=OUT/'cpu-close-20261025-v1';PARENT=OUT/'candidate/bundle-v2';CANDIDATE=BASE/'manager-source-03'
sys.path[:0]=[str(CANDIDATE),str(PARENT/'platform/qwen35/a12'),str(PARENT/'control/support')]
import tt10_01_cpu_close as close
import cpu01b_window as window
import cpu01b_observer as ob
from cpu01b_supervisor import OwnedWorker as ParentCPUWorker
from cpu01b_health import HealthSchedule,HealthBlocked
from accelerator_release_gate_v2 import SCHEMA

ob.ENABLED=False
source=(CANDIDATE/'tt10_01_manager.py').read_text()
tree=ast.parse(source)
namespace=dict(CpuCloseOwnerMixin=close.CpuCloseOwnerMixin,CpuOnlyWorkerMixin=close.CpuOnlyWorkerMixin,
    ParentCPUWorker=ParentCPUWorker,Window=window.Window,DEFAULT='pc-default',Path=Path,time=time,ob=ob,
    HealthBlocked=HealthBlocked,record_reserve_refusal=close.record_reserve_refusal,
    IsolatedIdleTrial=object,SPEC=dict(compact_health_journal=False))
for name in ('CPUWorker','Owner','Platform'):
    node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(CANDIDATE/'tt10_01_manager.py'),'exec'),namespace)
CPUWorker=namespace['CPUWorker'];Owner=namespace['Owner'];Platform=namespace['Platform']
DEFAULT_CPU_CHECK=close.default_cpu_platform


def failure_entry(owner,platform,run):
    # Execute the exact derived manager exception-handler AST in a CPU fixture.
    main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    handler=copy.deepcopy(next(n for n in main.body if isinstance(n,ast.Try)).handlers[0])
    wrapper=ast.parse("def entry(owner,p,run):\n    try:\n        raise RuntimeError('synthetic manager CPU failure')\n    except BaseException as exc:\n        pass\n")
    wrapper.body[0].body[0].handlers[0]=handler;ast.fix_missing_locations(wrapper)
    scope=dict(save=save,SystemExit=SystemExit,RuntimeError=RuntimeError,BaseException=BaseException)
    exec(compile(wrapper,'derived-manager-exception-handler','exec'),scope)
    return scope['entry'](owner,platform,run)


def scan(boot):
    return dict(schema=SCHEMA,scan_complete=True,boot_id=boot,boot_id_after=boot,scan_issues=[],device_holders=[],device_mappings=[],inspected_processes=[str(os.getpid())])


class FixturePlatform:
    def __init__(self,root,boot):
        self.run=root;self.boot=boot;self.target=root/'not-staged';self.worker=None
        self.pl_mutation_started=False;self.gdm_isolated=True;self.gate_lock=threading.RLock()
        self.health_schedule=HealthSchedule(self.gate_lock);self.latest_kernel={};self.latest_health={}
        self.kernel_bad=False;self.reserve_bad=False;self.default_bad=False;self.service_bad=False
        self.scan_bad=False;self.collect_calls=0;self.service_calls=[];self.kmsg_reader=None;self.events=[]
    def emit(self,event,**data):self.events.append(dict(event=event,**data))
    def kernel_checkpoint(self,phase):
        if self.kernel_bad:raise HealthBlocked('synthetic unreviewed kernel')
        self.latest_kernel=dict(allowed=True,observation_monotonic_ns=time.monotonic_ns(),synthetic_platform_fixture=True)
    def live_health(self,boot,full):
        if self.reserve_bad:
            close.record_reserve_refusal(self,boot,dict(MemAvailable=2987932,CmaFree=52816,CmaTotal=524288),[42000],full)
            raise HealthBlocked('full-model live extra reserve gate')
        return dict(memory_kib=dict(MemAvailable=2987932,CmaFree=196608),synthetic_platform_fixture=True)
    def no_users(self,*,module_loaded):
        assert module_loaded is False
        window.require_no_users(self.collect(),True,boot_id=self.boot)
    def collect(self,**kw):
        self.collect_calls+=1;s=scan(self.boot)
        if self.scan_bad:s.update(scan_complete=False,scan_issues=[dict(reason='PERMISSION_DENIED_SYNTHETIC')])
        return s
    def service(self,action):
        assert action=='start'
        self.service_calls.append(action)
        if self.service_bad:raise RuntimeError('synthetic GDM start failure')
        self.gdm_isolated=False


class Tests(unittest.TestCase):
    def setUp(self):
        self.root=RUN/self._testMethodName;self.root.mkdir()
        (self.root/'active').mkdir();(self.root/'active/lease.json').write_text('{"fixture":"PC_ONLY"}\n')
        self.paths=(self.root/'deployment.lock',self.root/'device.lock');self.fds=[];self.workers=[]
        for path in self.paths:
            fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_CLOEXEC,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.fds.append(fd)
        o=Owner.__new__(Owner);self.owner=o
        o.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();o.evidence=self.root/'evidence';o.evidence.mkdir()
        o.locks=list(self.fds);o.lease_hash=sha(self.root/'active/lease.json');o.finished=False
        o.review=dict(window_id='pc-only-'+self._testMethodName);o.expires=time.monotonic_ns()+300_000_000_000
        o.platform=FixturePlatform(self.root,o.boot)
        o._verify_default=self.verify_default
        self.patches=[patch.object(window,'CENTRAL',self.root),patch.object(window,'LOCKS',self.paths),
            patch.object(window,'collect',side_effect=o.platform.collect),patch.object(close,'default_cpu_platform',side_effect=self.default_cpu_platform)]
        for p in self.patches:p.start()
    def tearDown(self):
        # Test-only fixture cleanup after assertions; never a production release.
        pending=getattr(self.owner,'_cpu_worker',None)
        if pending is not None and pending not in self.workers:self.workers.append(pending)
        for w in self.workers:
            if w.process.poll() is None:
                (self.root/'release').touch()
                try:w.process.stdin.write('{"op":"shutdown"}\n');w.process.stdin.flush()
                except (OSError,ValueError):pass
                try:w.process.wait(timeout=20)
                except subprocess.TimeoutExpired:raise AssertionError('PC fixture did not cooperate; no forced kill')
            w.permission_thread.join(2);w.reader_thread.join(2)
            if not w.closed:
                for f in (w.stderr,w.process.stdin,w.process.stdout,w.manager_sock):
                    try:f.close()
                    except (OSError,ValueError):pass
        for p in reversed(self.patches):p.stop()
        for fd in self.fds:
            try:os.close(fd)
            except OSError:pass
    def verify_default(self):
        if self.owner.platform.default_bad or self.owner.platform.gdm_isolated:raise RuntimeError('synthetic default/GDM not proven')
    def default_cpu_platform(self,owner):
        self.assertIs(owner,self.owner);p=owner.platform
        if p.pl_mutation_started or p.worker is not None or p.default_bad or p.target.exists():raise close.CloseBlocked('synthetic nondefault/PL/staging')
        return dict(synthetic_platform_fixture=True,module_absent=True,PL_mutation=False)
    def held(self):
        self.assertTrue((self.root/'active/lease.json').exists());self.assertFalse(self.owner.finished)
        for path in self.paths:
            with path.open('a+') as f:
                with self.assertRaises(BlockingIOError):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def archived(self):
        self.assertTrue(self.owner.finished);self.assertFalse((self.root/'active').exists())
        self.assertEqual(sha(self.root/'history'/self.owner.review['window_id']/'lease.json'),self.owner.lease_hash)
        for path in self.paths:
            with path.open('a+') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.assertTrue(self.owner.platform.health_schedule.blocked)
        with self.assertRaises(close.CloseBlocked):self.owner.health()
        with self.assertRaises(close.CloseBlocked):self.owner.start_worker(PARENT)
    def worker(self,mode='idle',native=False):
        if native:
            from tt10_01_pc import environment
            env=environment();env['SP_TT10_CONFIG']=str(OUT/'pc-diagnostic-04/config.json')
            args=[str(WORK/'pc04/qwen35-a12'),str(ROOT/'artifacts/qwen35-0.8b/qwen35-text-Q4_K_M.gguf'),'2','1024','all','TILED','2','8']
        else:
            env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_','GGML_','OMP_'))}
            args=[sys.executable,str(ROOT/'platform/qwen35/a12/tt10_01_cpu_close_fixture.py'),mode,str(self.root/'release')]
        w=self.owner.start_cpu_worker(CPUWorker,args,directory=self.root/'worker',env=env,health=self.owner.health,
            max_runs=1,max_loads=1,expires=time.monotonic()+180,owner_check=self.owner.owner_check)
        self.workers.append(w);r=w.get(120);self.assertEqual(r['type'],'ready');save(self.root/'ready.json',r)
        self.assertIs(self.owner._owned_worker,w)
        return w,r
    def fail_health(self):
        self.owner.platform.reserve_bad=True
        with self.assertRaises(HealthBlocked):self.owner.health()
        self.assertTrue(self.owner.platform.health_schedule.blocked)
    def events(self):return [json.loads(s) for s in (self.owner.evidence/'finalization-events.jsonl').read_text().splitlines()]
    def test_idle_reserve_failure_closes_then_scans_archives_and_latch_stays(self):
        w,_=self.worker();self.fail_health()
        self.assertTrue(self.owner.handle_cpu_failure('HealthBlocked: full-model live extra reserve gate'))
        self.archived();self.assertEqual(w.process.returncode,0);self.assertTrue(w.delivery_cancelled)
        events=[r['event'] for r in self.events()]
        self.assertLess(events.index('CPU_NORMAL_EXIT_PROVEN'),events.index('FRESH_CLOSING_ONLY_OBSERVATION'))
        self.assertLess(events.index('FRESH_CLOSING_ONLY_OBSERVATION'),events.index('FINALIZATION_PREPARED_FOR_ATOMIC_ARCHIVE'))
        sample=j(next(self.root.glob('cpu-close-health-refusal-*.json')))
        self.assertEqual(sample['memory_kib']['CmaFree'],52816);self.assertEqual(sample['required_CmaFree_kib'],98304)
    def test_active_cooperation_discards_late_result_and_clears_state(self):
        w,_=self.worker('active');w.send(dict(id='fixture-active',op='generate'));self.assertEqual(w.get(10)['type'],'token')
        self.assertTrue(self.owner.handle_cpu_failure('synthetic active CPU failure'));self.archived()
        wire=[json.loads(s) for s in (w.directory/'stdout.jsonl').read_text().splitlines()]
        r=next(x for x in wire if x.get('status')=='CANCELLED');self.assertFalse(r['partial_output_usable']);self.assertTrue(r['state_cleared_before_response'])
        with self.assertRaises(RuntimeError):w.get(.1)
    def test_timeout_retains_lease_locks_and_no_fresh_scan_or_restart(self):
        w,_=self.worker('timeout');self.assertFalse(self.owner.handle_cpu_failure('synthetic timeout',timeout=.1));self.held()
        self.assertTrue(w.quarantined);self.assertIsNone(w.process.poll());self.assertEqual(self.owner.platform.collect_calls,0)
        self.assertEqual(self.owner.platform.service_calls,[]);self.assertNotIn('FRESH_CLOSING_ONLY_OBSERVATION',[x['event'] for x in self.events()])
    def test_bad_exit_retains_lease_and_records_actual_exit(self):
        w,_=self.worker('bad_exit');self.assertFalse(self.owner.handle_cpu_failure('synthetic bad exit'));self.held()
        self.assertEqual(w.process.returncode,7);self.assertEqual(self.owner.platform.collect_calls,0)
    def test_unexpected_CPU_device_permission_is_durable_denial_and_retained(self):
        w,_=self.worker('permission');r=w.get(10);self.assertFalse(r['allow'])
        self.assertFalse(self.owner.handle_cpu_failure('unexpected CPU permission'));self.held()
        self.assertEqual((w.runs,w.loads), (0,0));self.assertTrue(w.quarantined)
    def test_device_descriptor_refuses_cancel_and_keeps_owner(self):
        w,_=self.worker('device');self.assertFalse(self.owner.handle_cpu_failure('synthetic CPU device FD'));self.held()
        self.assertFalse(w.delivery_cancelled);self.assertIsNone(w.process.poll())
    def test_wrong_worker_identity_refuses_signal_and_close(self):
        w,_=self.worker();self.owner._cpu_identity['start_ticks']+=1
        self.assertFalse(self.owner.handle_cpu_failure('wrong start identity'));self.held();self.assertFalse(w.delivery_cancelled)
    def test_kernel_failure_after_normal_CPU_exit_retains_owner(self):
        w,_=self.worker();self.owner.platform.kernel_bad=True
        self.assertFalse(self.owner.handle_cpu_failure('synthetic kernel fault'));self.held()
        self.assertEqual(w.process.returncode,0);self.assertEqual(self.owner.platform.service_calls,[])
    def test_incomplete_scan_after_normal_CPU_exit_retains_owner(self):
        w,_=self.worker();self.owner.platform.scan_bad=True
        self.assertFalse(self.owner.handle_cpu_failure('synthetic unreadable scan'));self.held()
        self.assertEqual(w.process.returncode,0);self.assertEqual(self.owner.platform.service_calls,[])
    def test_GDM_start_failure_preserves_owner_after_CPU_exit(self):
        w,_=self.worker();self.owner.platform.service_bad=True
        self.assertFalse(self.owner.handle_cpu_failure('synthetic GDM failure'));self.held();self.assertEqual(w.process.returncode,0)
    def test_default_changed_blocks_before_CPU_signal(self):
        w,_=self.worker();self.owner.platform.default_bad=True
        self.assertFalse(self.owner.handle_cpu_failure('synthetic default mismatch'));self.held();self.assertFalse(w.delivery_cancelled)
    def test_PL_mutation_or_PL_worker_never_uses_CPU_close_path(self):
        w,_=self.worker()
        for attr,value in [('pl_mutation_started',True),('worker',object())]:
            old=getattr(self.owner.platform,attr);setattr(self.owner.platform,attr,value)
            self.assertFalse(self.owner.handle_cpu_failure('synthetic PL/unknown DMA'));self.held();self.assertFalse(w.delivery_cancelled)
            setattr(self.owner.platform,attr,old)
    def test_uncertain_constructor_does_not_guess_that_no_child_exists(self):
        def factory(*a,**kw):raise RuntimeError('synthetic constructor failure')
        with self.assertRaises(RuntimeError):self.owner.start_cpu_worker(factory)
        self.assertTrue(self.owner._cpu_launch_pending)
        self.assertFalse(self.owner.handle_cpu_failure('launch uncertain'));self.held()
    def test_closing_check_rejects_live_foreign_and_stale_observations(self):
        w,_=self.worker()
        with self.assertRaises(close.CloseBlocked):self.owner.health(closing=True)
        with self.assertRaises(close.CloseBlocked):self.owner.finish(types.SimpleNamespace(closed=True,process=types.SimpleNamespace(returncode=0)))
        self.assertTrue(w.close(10));self.owner.platform.health_schedule.blocked=True
        self.owner._health_observation=lambda **kw:dict(closing=True,checks_skipped=False,checked_monotonic_ns=1,kernel=dict(allowed=True,observation_monotonic_ns=1))
        with self.assertRaises(close.CloseBlocked):self.owner.health(closing=True)
        self.held()
    def test_actual_source04_idle_checkpoint_closes_normally(self):
        w,ready=self.worker(native=True);binding=ready['prefix_cache']['binding_sha256']
        prefix=j(OUT/'pc-diagnostic-04/config.json')['allowed_prefixes'][0]
        w.send(dict(id='native-warm',op='cache_create',tokens=prefix,max_tokens=1,cache_id='neutral',confirmed_prefix=True,cache_binding_sha256=binding,cache_policy='R0'))
        created=w.get(180);save(self.root/'cache-created.json',created);self.assertEqual(created['type'],'cache_created');self.assertTrue(created['state_cleared_before_response'])
        self.fail_health();self.assertTrue(self.owner.handle_cpu_failure('actual native idle CPU fault'));self.archived()
        self.assertEqual((w.process.returncode,w.runs,w.loads,w.sequence),(0,0,0,0))
    def test_actual_source04_active_cancel_normal_exit_and_private_clear(self):
        w,ready=self.worker(native=True);binding=ready['prefix_cache']['binding_sha256']
        prefix=j(OUT/'pc-diagnostic-04/config.json')['allowed_prefixes'][0]
        owner=dict(kind='case_session',case_id='SYN_CP_01',case_sha256='1'*64,session_id='cpu-close-PC-only',epoch=0)
        for cid,who in [('public',dict(kind='public_neutral')),('private',owner)]:
            w.send(dict(id='native-'+cid,op='cache_create',tokens=prefix,max_tokens=1,cache_id=cid,cache_owner=who,confirmed_prefix=True,cache_binding_sha256=binding,cache_policy='R0'))
            created=w.get(180);save(self.root/(cid+'-created.json'),created);self.assertEqual(created['type'],'cache_created')
        w.send(dict(id='native-active',op='generate',tokens=prefix+[100]*100,max_tokens=64,teacher_tokens=[10]*64,
            cache_policy='TT10_REQUIRE_HIT',cache_id='private',cache_owner=owner,cache_binding_sha256=binding,profile=False))
        first=w.get(180);self.assertEqual(first['type'],'token');save(self.root/'first-token.json',first)
        self.assertTrue(self.owner.handle_cpu_failure('actual native active CPU fault'));self.archived()
        wire=[json.loads(s) for s in (w.directory/'stdout.jsonl').read_text().splitlines()]
        r=next(x for x in wire if x.get('id')=='native-active' and x['type']=='result');save(self.root/'cancelled-native-result.json',r)
        self.assertEqual(r['status'],'CANCELLED');self.assertFalse(r['partial_output_usable']);self.assertTrue(r['state_cleared_before_response']);self.assertEqual(r['state_position_after_clear'],-1)
        self.assertEqual([x['id'] for x in r['prefix_cache']['entries']],['public']);self.assertEqual((w.runs,w.loads,w.sequence),(0,0,0))

    def test_exact_live_health_threshold_sample_is_saved_before_rejection(self):
        p=Platform.__new__(Platform);p.run=self.root;p.stable_temperatures=types.SimpleNamespace(read=lambda:[42000],verify_topology=lambda:None)
        p.topology_checked_ns=time.monotonic_ns();p.health_parts=dict(temperature_memory_ms=0.0);p.emit=lambda *a,**kw:None
        bootfile=self.root/'boot-fixture';bootfile.write_text(self.owner.boot);memfile=self.root/'mem-fixture'
        previous=namespace['Path']
        namespace['Path']=lambda name:bootfile if str(name)=='/proc/sys/kernel/random/boot_id' else memfile if str(name)=='/proc/meminfo' else Path(name)
        try:
            for available,cma,allowed in [(2987932,52816,False),(1114111,98304,False),(1114112,98304,True)]:
                memfile.write_text('MemAvailable: %d kB\nCmaFree: %d kB\nCmaTotal: 524288 kB\n'%(available,cma))
                if allowed:self.assertEqual(p.live_health(self.owner.boot,False)['memory_kib']['CmaFree'],cma)
                else:
                    with self.assertRaises(HealthBlocked):p.live_health(self.owner.boot,False)
            samples=[j(x) for x in sorted(self.root.glob('cpu-close-health-refusal-*.json'))]
            self.assertEqual(len(samples),2);self.assertEqual(samples[0]['memory_kib']['CmaFree'],52816)
            self.assertEqual(samples[1]['memory_kib']['MemAvailable'],1114111)
            self.assertTrue(all(x['required_CmaFree_kib']==98304 and x['required_MemAvailable_kib']==1114112 for x in samples))
        finally:namespace['Path']=previous

    def test_production_default_gate_requires_exact_overlay_driver_and_no_staging(self):
        fake=self.root/'fake-sys';over=fake/'sys/kernel/config/device-tree/overlays';(over/'pc-default_image_1').mkdir(parents=True)
        (over/'pc-default_image_1/status').write_text('applied');state=fake/'sys/class/fpga_manager/fpga0/state';state.parent.mkdir(parents=True);state.write_text('operating')
        def redirect(name):
            name=str(name)
            return fake/name.lstrip('/') if name.startswith(('/sys/','/state.txt')) else Path(name)
        with patch.object(close,'Path',side_effect=redirect):
            self.assertTrue(DEFAULT_CPU_CHECK(self.owner)['module_absent'])
            (over/'other').mkdir();(over/'other/status').write_text('applied')
            with self.assertRaises(close.CloseBlocked):DEFAULT_CPU_CHECK(self.owner)
            (over/'other/status').rename(fake/'other-status-retained');(over/'other').rmdir()
            module=fake/'sys/module/zocl';module.mkdir(parents=True)
            with self.assertRaises(close.CloseBlocked):DEFAULT_CPU_CHECK(self.owner)
            module.rename(module.with_name('zocl-not-active-fixture'))
            state.write_text('unknown')
            with self.assertRaises(close.CloseBlocked):DEFAULT_CPU_CHECK(self.owner)
            state.write_text('operating');self.owner.platform.target.mkdir()
            with self.assertRaises(close.CloseBlocked):DEFAULT_CPU_CHECK(self.owner)

    def ticket(self,**override):
        self.ticket_index=getattr(self,'ticket_index',0)+1
        request=dict(schema='A12_FINALIZE_ONLY_V2',op='finish_only',boot_id=self.owner.boot,window_id=self.owner.review['window_id'],
            manager_pid=os.getpid(),manager_start_ticks=window.start_ticks(Path('/proc/self')),lease_sha256=self.owner.lease_hash,
            expires_monotonic_ns=time.monotonic_ns()+20_000_000_000)
        request.update(override);path=self.owner.evidence/('finalize-request-%04d.json'%self.ticket_index)
        close.durable_json(path,request);return path

    def test_finalize_ticket_after_normal_CPU_exit_uses_fresh_closing_and_archives(self):
        w,_=self.worker();self.assertTrue(w.close(10));self.owner._cpu_failure_latched=True
        self.owner.platform.health_schedule.blocked=True;self.owner.platform.gdm_isolated=False
        ticket=self.ticket()
        with patch.object(window,'trusted_file',lambda p:None):self.assertTrue(self.owner._apply_finalize_ticket(ticket))
        self.archived();self.assertTrue(ticket.with_name('consumed-'+ticket.name).exists())

    def test_finalize_ticket_cannot_close_live_CPU_or_widen_or_ignore_identity(self):
        w,_=self.worker()
        for override in [{},{'op':'compute'},{'lease_sha256':'wrong'},{'manager_start_ticks':0},{'expires_monotonic_ns':0}]:
            ticket=self.ticket(**override)
            with patch.object(window,'trusted_file',lambda p:None),self.assertRaises(RuntimeError):self.owner._apply_finalize_ticket(ticket)
            self.assertTrue(ticket.exists());self.assertFalse(w.delivery_cancelled);self.held()

    def test_transient_final_scan_is_preserved_then_complete_scan_allows_archive(self):
        self.worker();bad=scan(self.owner.boot);bad.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        with patch.object(window,'collect',side_effect=[bad,scan(self.owner.boot)]):self.assertTrue(self.owner.handle_cpu_failure('synthetic scan churn'))
        self.archived();records=[r for r in self.events() if r['event']=='FULL_PROCESS_OBSERVATION']
        self.assertEqual(len(records),2);self.assertFalse(records[0]['scan']['scan_complete']);self.assertTrue(records[1]['scan']['scan_complete'])

    def test_persistent_final_scan_churn_retains_all_failures_and_owner(self):
        w,_=self.worker();bad=scan(self.owner.boot);bad.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        with patch.object(window,'collect',return_value=bad):self.assertFalse(self.owner.handle_cpu_failure('synthetic persistent scan churn'))
        self.held();self.assertEqual(w.process.returncode,0)
        records=[r for r in self.events() if r['event']=='FULL_PROCESS_OBSERVATION'];self.assertEqual(len(records),4)
        self.assertTrue(all(not r['scan']['scan_complete'] for r in records))

    def test_PL_constructor_failure_never_falls_back_to_CPU_cleanup(self):
        w,_=self.worker();self.assertTrue(w.close(10))
        with patch.object(window.Window,'start_worker',side_effect=RuntimeError('synthetic PL constructor failure')):
            with self.assertRaises(RuntimeError):self.owner.start_worker(PARENT)
        self.assertEqual(self.owner._cpu_phase,'PL');self.assertFalse(self.owner.handle_cpu_failure('PL launch uncertain'));self.held()

    def test_changed_lease_blocks_CPU_cancel_and_archive(self):
        w,_=self.worker();self.owner.lease_hash='0'*64
        self.assertFalse(self.owner.handle_cpu_failure('synthetic changed lease'));self.held();self.assertFalse(w.delivery_cancelled)

    def test_derived_manager_failure_handler_process_exits_one_after_archive(self):
        root=self.root/'manager-probe'
        argv=[sys.executable,str(ROOT/'platform/qwen35/a12/tt10_01_cpu_close_test.py'),'--run','manager-probe','--exit-probe-root',str(root)]
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=30)
        save(self.root/'manager-process-receipt.json',dict(argv=argv,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,platform='PC_SYNTHETIC'))
        self.assertEqual(result.returncode,1,result.stderr)
        evidence=root/'test_idle_reserve_failure_closes_then_scans_archives_and_latch_stays'
        value=j(evidence/'result.json');self.assertEqual(value['status'],'FAIL_CPU_STAGE_NORMAL_FINALIZED')
        self.assertFalse(value['compute_pass']);self.assertEqual(value['new_PL_calls'],0);self.assertIsNone(value['TTFT_app_s'])
        self.assertFalse((evidence/'active').exists());self.assertTrue(list((evidence/'history').glob('*/lease.json')))

    def test_quarantine_arriving_during_close_blocks_fresh_check_and_archive(self):
        w,_=self.worker();original=w.close
        def close_then_quarantine(*a,**kw):
            result=original(*a,**kw);w.quarantined=True;return result
        w.close=close_then_quarantine
        self.assertFalse(self.owner.handle_cpu_failure('synthetic concurrent control fault during close'));self.held()
        self.assertEqual(w.process.returncode,0);self.assertTrue(w.closed)
        self.assertNotIn('FRESH_CLOSING_ONLY_OBSERVATION',[r['event'] for r in self.events()])
        with self.assertRaises(close.CloseBlocked):self.owner.health(closing=True)
        with self.assertRaises(close.CloseBlocked):self.owner.finish(w)


def main():
    global RUN
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--exit-probe-root',type=Path);a=ap.parse_args()
    if not a.run.replace('-','').isalnum():raise ValueError('invalid fresh run name')
    if a.exit_probe_root:
        RUN=a.exit_probe_root;RUN.mkdir()
        test=Tests('test_idle_reserve_failure_closes_then_scans_archives_and_latch_stays');test.setUp()
        try:
            test.worker();test.fail_health();failure_entry(test.owner,test.owner.platform,test.root)
        finally:test.tearDown()
        raise AssertionError('manager handler did not exit')
    evidence=BASE/a.run;evidence.mkdir()
    # DrvFS fdinfo does not establish native FLOCK ownership. Keep the unchanged
    # production check and run all temporary leases/locks on native WSL storage.
    RUN=WORK/'cpu-close-tests'/a.run;RUN.mkdir(parents=True)
    (evidence/'tools').mkdir()
    for name in ('tt10_01_cpu_close_test.py','tt10_01_cpu_close_fixture.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,evidence/'tools'/name)
    # Linux tests execute the exact candidate snapshot, not an unpinned live edit.
    assert sha(CANDIDATE/'tt10_01_cpu_close.py')==sha(ROOT/'platform/qwen35/a12/tt10_01_cpu_close.py')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    failed={str(t).split()[0] for t,s in result.failures+result.errors}
    actual_cases=sum(name not in failed for name in ('test_actual_source04_idle_checkpoint_closes_normally','test_actual_source04_active_cancel_normal_exit_and_private_clear'))
    report=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        failures=[(str(t),s) for t,s in result.failures],errors=[(str(t),s) for t,s in result.errors],
        platform_observations='SYNTHETIC_PC_FIXTURES',real_source04_CPU_cases_passed=actual_cases,BOARD='NOT_TESTED',new_PL_calls=0,
        native_workspace=str(RUN),candidate_sources=j(BASE/'DERIVATION-03.json')['sources'])
    save(RUN/'RESULT.json',report);shutil.copytree(RUN,evidence/'files');save(evidence/'RESULT.json',report)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__=='__main__':main()
