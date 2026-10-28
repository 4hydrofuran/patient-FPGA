"""Actual CPU-array ABI and native-permit failure tests; no model/PL/device."""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from native_cpu_build import ROOT,OUT,WORK,read,save
from native_request_journal import OwnedWorker

EVIDENCE=None
BUILD=None


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a12-native-abi-');self.root=Path(self.temp.name);self.workers=[]
    def tearDown(self):
        for w in self.workers:
            if not w.process.stdin.closed:w.process.stdin.close()
            if w.process.poll() is None:
                try:w.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:pass
                w.process.wait(timeout=5)
            w.permission_thread.join(2);w.reader_thread.join(2)
            for f in (w.stderr,w.process.stdout,w.manager_sock):f.close()
            if hasattr(w,'_journal'):w._journal.close()
        self.temp.cleanup()

    def launch(self,damage=None):
        build=BUILD;workspace=Path(build['workspace']);base=read(workspace/'adapter-config.json')
        if damage=='hash':base['cpu_library_sha256']='0'*64
        if damage=='device':base['allow_device_access']=True
        ap=self.root/('adapter-'+str(len(self.workers))+'.json');save(ap,base)
        cfg=dict(adapter=build['library'],adapter_config=str(ap),cpu=build['existing_cpu_library'],cpu_config=base['cpu_config'])
        path=self.root/('probe-'+str(len(self.workers))+'.json');save(path,cfg)
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_'))}
        w=OwnedWorker([sys.executable,'-B',str(ROOT/'platform/qwen35/a12/native_cpu_abi_probe.py'),str(path)],
            directory=self.root/('worker-'+str(len(self.workers))),env=env,health=lambda:None,
            owner_check=lambda:None,max_runs=10,max_loads=72,expires=time.monotonic()+60,real=False)
        self.workers.append(w);return w,w.get(5)

    def call(self,w,**fields):w.send(dict(op='run',**fields));return w.get(5)
    def close(self,w):
        w.send(dict(op='shutdown'));result=w.get(5);self.assertEqual(result['type'],'abi_closed')
        self.assertEqual((result['unload_rc'],result['close_rc']),(0,0));self.assertTrue(w.close())

    def test_real_cpu_T1_T8_bytes_match_and_native_counts(self):
        w,ready=self.launch();self.assertEqual(ready['type'],'abi_ready');rows=[]
        for job,t in enumerate((1,8),1):
            r=self.call(w,T=t,job=job);rows.append(r)
            self.assertEqual((r['rc'],r['reference_rc']),(0,0));self.assertTrue(r['bit_exact'])
            self.assertEqual(r['report']['cpu_run_count'],job)
            self.assertEqual(r['report']['pc_verified_completions'],w.runs)
            self.assertIsNone(r['report']['hardware_done_count']);self.assertIsNone(r['report']['kernel_build_id'])
        self.close(w)
        if EVIDENCE is not None:save(EVIDENCE/'ABI_T1_T8.json',rows)

    def test_reused_job_never_grants_and_marks_output_unusable(self):
        w,_=self.launch();self.call(w,T=1,job=1);r=self.call(w,T=1,job=1)
        self.assertNotEqual(r['rc'],0);self.assertTrue(r['output_unchanged_on_error'])
        self.assertEqual(w.runs,1);self.assertEqual(r['report']['pc_verified_completions'],1)
        if EVIDENCE is not None:save(EVIDENCE/'BAD_JOB.json',r)
        self.assertFalse(r['report']['pc_output_consumable'])
        self.close(w)

    def test_actual_parent_refusal_does_not_forward_CPU_call(self):
        w,_=self.launch()
        def unhealthy():raise RuntimeError('PC ABI fresh health failure')
        w.health=unhealthy;r=self.call(w,T=1,job=1)
        self.assertNotEqual(r['rc'],0);self.assertTrue(r['output_unchanged_on_error'])
        self.assertEqual((w.runs,r['report']['pc_started_calls'],r['report']['pc_verified_completions'],r['report']['cpu_run_count']),(0,0,0,0))
        self.assertTrue(w.quarantined);self.assertTrue(r['report']['pc_poisoned'])
        if EVIDENCE is not None:save(EVIDENCE/'PARENT_DENIAL.json',r)

    def test_bad_output_extent_keeps_failed_call_and_no_completion(self):
        w,_=self.launch();r=self.call(w,T=1,job=1,bad_size=True)
        self.assertNotEqual(r['rc'],0);self.assertTrue(r['output_unchanged_on_error'])
        self.assertEqual((w.runs,r['report']['pc_started_calls'],r['report']['pc_verified_completions']),(1,1,0))
        self.assertTrue(r['report']['pc_poisoned'])

    def test_wrong_library_hash_and_device_activation_refused_before_permits(self):
        for damage in ('hash','device'):
            w,r=self.launch(damage);self.assertEqual(r['type'],'abi_open_refused')
            self.assertTrue(r['context_null']);self.assertNotEqual(r['rc'],0)
            self.assertEqual((w.runs,w.loads,w.sequence),(0,0,0));w.process.wait(timeout=5)


def main():
    global EVIDENCE,BUILD
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path)
    p.add_argument('--build',type=Path,default=OUT/'BUILD.json');args=p.parse_args()
    BUILD=read(args.build);args.evidence.mkdir(parents=True,exist_ok=False);EVIDENCE=args.evidence
    out=io.StringIO();r=unittest.TextTestRunner(stream=out,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (EVIDENCE/'unittest.txt').write_text(out.getvalue())
    save(EVIDENCE/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,
        failures=len(r.failures),errors=len(r.errors),domain='REAL_PC_CPU_ABI_ARRAYS_NO_MODEL_OR_PL',
        BOARD='NOT_TESTED',PL_calls=0,model_runs=0,adapter_sha256=BUILD['library_sha256']))
    print(out.getvalue());return 0 if r.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
