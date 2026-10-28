"""PC-only full A11 lifecycle with real locks/child/permits and fake hardware."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import stat
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
ap=argparse.ArgumentParser();ap.add_argument('--derived',type=Path,required=True)
args,remaining=ap.parse_known_args();sys.path.insert(0,str(args.derived.resolve()))
import mlp_manager as trial
import mlp_base as base
import mlp_policy as policy
import mlp_boundary_v2 as boundary
import mlp_kernel_gate as kg
import test_idle_integration_pc as fixture

CHILD=r'''
import json,os,sys,time
from pathlib import Path
args=sys.argv;req=json.loads(args[args.index('--a11-boundary-request')+1])
source=Path(args[args.index('--source')+1]);mode=args[args.index('--mode')+1]
out=Path(args[args.index('--a11-boundary-result')+1])
fd=req['inherited_device_lock_fd'];assert os.fstat(fd).st_ino>0
plan=json.loads((source/'vectors/manifest.json').read_text())
ops=[('open',0)];current=None
for row in plan['schedule']:
    if row['weight']!=current:ops.append(('weight',row['job_id']));current=row['weight']
    ops += [('submit',row['job_id']),('completed',row['job_id'])]
ops += [('close',23)]
(source/'permits').mkdir()
for seq,(phase,job) in enumerate(ops,1):
    p=source/'permits'/f'ready-{seq:03}.json';tmp=p.with_suffix('.tmp')
    tmp.write_text(json.dumps(dict(req,sequence=seq,phase=phase,job=job)))
    os.link(tmp,p);tmp.unlink()
    limit=time.monotonic()+5
    while not (source/'permits'/f'allow-{seq:03}.json').exists():
        if (source/'STOP.json').exists():sys.exit(7)
        if time.monotonic()>limit:sys.exit(8)
        time.sleep(.005)
rows=[]
for row in plan['schedule']:
    rows.append(dict(row,numeric_pass=True,guards_intact=True,status_code=0,kernel_build_id=0xB3030002,
        output_consumable=True,completion_validated=True,host_verified_completions=row['job_id'],
        actual_output_sha256='5'*64,hardware_cycles=None,measured_AXI_bytes=None,pure_kernel_ms=None,
        input_quant_ms=1.,api_run_ms=1.,output_copy_ms=1.,report_ms=1.,service_ms=3.))
r=dict(req,worker_pid=os.getpid(),status='NORMAL_CLOSED_A11_MINIMAL',normal_handles_closed=True,
    real_submissions=23,weight_loads=5,calls=rows,PC_FIXTURE_ONLY=True)
if mode=='worker_identity':r['worker_pid']+=1
if mode=='bad_numeric':r['calls'][0]['numeric_pass']=False
if mode=='two_runs':r['real_submissions']=24
out.write_text(json.dumps(r))
'''


class Integration(fixture.ControllerIntegrationTests):
    def setUp(self):
        super().setUp()
        stack=ExitStack();self.addCleanup(stack.close)
        for module in (policy,trial,base):
            for name,val in (('CENTRAL',self.central),('LOCKS',self.locks),
                             ('trusted_file',self.pc_trusted_file),('digest',self.digest)):
                stack.enter_context(patch.object(module,name,val))
        stack.enter_context(patch.object(base,'collect',self.collect))
        stack.enter_context(patch.object(boundary,'DEVICE_LOCK',self.locks[1]))
        stack.enter_context(patch.object(fixture,'TEST_PROPERTIES',kg.TEST_PROPERTIES))
        original_stat=Path.stat
        def pc_stat(p,*a,**kw):
            result=original_stat(p,*a,**kw)
            if p==self.locks[1]:
                values=list(result);values[4]=0;return os.stat_result(values)
            return result
        stack.enter_context(patch.object(Path,'stat',pc_stat))
        self.window='a11-mlp-20261023-v9001'
        names={'mlp_worker.py','mlp_manager.py','mlp_engine.py','mlp_policy.py','mlp_boundary_v2.py',
               'a11-mlp.dtbo','a11-mlp.bit.bin','w4a8.xclbin','libsp_linear_a11_trial.so',
               'liba11_quant.so'}
        for n in names:(self.source/n).write_bytes(b'PC_ONLY_NOT_DEPLOYABLE')
        (self.source/'vectors').mkdir()
        (self.source/'vectors/manifest.json').write_text(json.dumps(dict(schedule=policy.schedule())))
        (self.source/'prior-a10-audit.json').write_text(json.dumps(dict(
            status='PASS_BOARD_SINGLE_N32_POSTCOMPUTE_RELEASE_WITH_LIMITATIONS',kernel=policy.KERNEL,
            machine_sha256=policy.MACHINE,PC_FIXTURE_ONLY=True)))
        stack.enter_context(patch.object(policy,'DRIVER_SHA',self.digest(self.source/'zocl.refcount.ko')))
        planpin=self.digest(self.source/'vectors/manifest.json')
        stack.enter_context(patch.object(policy,'PLAN_SHA',planpin))
        stack.enter_context(patch.object(trial,'PLAN_SHA',planpin))
        stack.enter_context(patch.object(trial,'ASSETS',self.fixture_assets))
        man=dict(schema='A11_MLP_BUNDLE_V1',scope=policy.SCOPE,authorization_included=False,board_accepted=False,
                 max_submissions=23,files={str(p.relative_to(self.source)):dict(bytes=p.stat().st_size,sha256=self.digest(p))
                    for p in self.source.rglob('*') if p.is_file() and p.name not in ('manifest.json','review.json')})
        man['files']['vectors/manifest.json']=dict(bytes=(self.source/'vectors/manifest.json').stat().st_size,sha256=planpin)
        (self.source/'manifest.json').write_text(json.dumps(man))
        review=dict(schema='A11_MLP_REVIEW_V1',scope=policy.SCOPE,authorized=True,compute_authorized=True,
            allow_gdm_stop_restore=True,max_submissions=23,explicit_bo_budget_bytes=4194304,
            boot_id=self.boot,kernel=policy.KERNEL,machine_sha256=policy.MACHINE,window_id=self.window,
            baseline_sha256=self.digest(self.source/'baseline.raw.txt'),bundle_sha256=self.digest(self.source/'manifest.json'),
            prior_a10_audit_sha256=self.digest(self.source/'prior-a10-audit.json'),baseline_read_uptime_ns=time.monotonic_ns())
        (self.source/'review.json').write_text(json.dumps(review));self.review_sha=self.digest(self.source/'review.json')
        self.obj=trial.MlpTrial(self.source,self.review_sha)
        self.obj.target=self.root/'firmware';self.obj.snapshot=self.snapshot;self.obj.park=self.park
    def pc_trusted_file(self,path):
        # Exact lock stat has root UID injected solely for production boundary
        # root policy. Ownership of every other test fixture remains real UID.
        if Path(path)==self.locks[1]:
            self.assertEqual(Path(path).stat().st_mode&0o022,0);return
        super().pc_trusted_file(path)
    def popen(self,argv,**kw):
        if len(argv)>4 and argv[:3]==['/usr/bin/python3','-B','-I']:
            self.calls.append(tuple(argv));self.assertEqual(argv[3],str(self.source/'mlp_worker.py'))
            self.assertEqual(kw['pass_fds'],(self.obj.held_locks[1].fileno(),))
            return self.original_popen([sys._base_executable,'-B','-I','-c',CHILD,
                '--source',str(self.source),'--mode',self.fault or 'normal',*argv[-4:]],**kw)
        return super().popen(argv,**kw)
    def execute(self):
        with patch.object(trial,'MlpTrial',return_value=self.obj):
            return trial.main(['--execute-authorized-mlp-once','--source',str(self.source),'--review-sha256',self.review_sha])
    def park(self,reason):
        from manager_support import latch_stop
        latch_stop(self.obj,reason)
        return super().park(reason)
    def test_real_logs_locks_child_exit_and_restore_wiring(self):
        self.assertEqual(self.execute(),0)
        events=self.events();names=[r['event'] for r in events]
        self.assertLess(names.index('WORKER_REAPED'),names.index('RELEASE_PRECHECK_PASSED_NOT_UNLOADED'))
        self.assertEqual(names[-1],'MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED')
        self.assertEqual(self.obj.permit_index,53)
        self.assertEqual((self.gdm,self.overlay,self.module),('active',policy.DEFAULT,False))
        self.assertFalse((self.central/'active').exists());self.assertEqual(self.obj.held_locks,[])
        receipt=json.loads((self.source/'mlp-receipt.json').read_text())
        self.assertTrue(receipt['worker_result']['PC_FIXTURE_ONLY']);self.assertEqual(receipt['compute_runs'],23)
    def test_numeric_failure_blocks_restore(self):self.assert_blocked('bad_numeric','WORKER_RESULT_UNPROVEN')
    def test_extra_submission_count_blocks_restore(self):self.assert_blocked('two_runs','WORKER_RESULT_UNPROVEN')


if __name__=='__main__':unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
