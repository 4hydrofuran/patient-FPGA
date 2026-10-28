import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock

from mlp_boundary import MlpBoundary, validate_result, schedule, TIMINGS


class Parked(Exception):pass


class Boundary(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a11-pc-boundary-')
        self.request=dict(boot_id='PC_ONLY_BOOT',window_id='PC_ONLY_WINDOW',lease_sha256='1'*64,
                          request_sha256='2'*64,plan_sha256='3'*64,worker_baseline_sha256='4'*64)
        self.path=Path(self.temp.name)/'result.json'
        self.quarantine=Mock(side_effect=Parked)
        self.guard=Mock(return_value=True)
        self.b=MlpBoundary(self.request,self.path,guard=self.guard,quarantine=self.quarantine,emit=Mock())
        self.b.process=Mock(pid=12345);self.b.process.wait.return_value=0
        self.b.state='RUNNING'

    def tearDown(self):self.temp.cleanup()

    def result(self):
        rows=[]
        for plan in schedule():
            rows.append(dict(plan,numeric_pass=True,guards_intact=True,status_code=0,kernel_build_id=0xB3030002,
                             output_consumable=True,completion_validated=True,host_verified_completions=plan['job_id'],
                             actual_output_sha256='5'*64,hardware_cycles=None,measured_AXI_bytes=None,pure_kernel_ms=None,
                             **{k:3. if k=='service_ms' else 1. for k in TIMINGS}))
        return dict(self.b.identity,worker_pid=12345,status='NORMAL_CLOSED_A11_MINIMAL',normal_handles_closed=True,
                    real_submissions=23,weight_loads=5,calls=rows)

    def test_normal_exit_does_not_itself_authorize_unload(self):
        self.path.write_text(json.dumps(self.result()))
        self.b.wait_normal(30)
        self.assertEqual(self.b.state,'EXITED_NORMAL')
        self.b.process.wait.assert_called_once_with(timeout=30)
        self.assertEqual(MlpBoundary.check_release.__module__, 'xrt_worker_boundary')

    def test_timeout_retains_no_kill(self):
        self.b.process.wait.side_effect=subprocess.TimeoutExpired('PC_DOUBLE',1)
        with self.assertRaises(Parked):self.b.wait_normal(1)
        self.b.process.kill.assert_not_called();self.b.process.terminate.assert_not_called()
        self.assertEqual(self.b.state,'QUARANTINED')

    def test_abnormal_exit_blocks(self):
        self.b.process.wait.return_value=-11
        with self.assertRaises(Parked):self.b.wait_normal(10)

    def test_missing_result_blocks(self):
        with self.assertRaises(Parked):self.b.wait_normal(10)

    def test_false_identity_or_old_a10_protocol_blocks(self):
        for key in ('protocol','boot_id','lease_sha256','plan_sha256','worker_baseline_sha256'):
            r=self.result();r[key]='OLD_OR_WRONG'
            with self.subTest(key=key),self.assertRaises(ValueError):validate_result(r,self.b.identity,12345)

    def test_incomplete_or_duplicate_jobs_rejected(self):
        r=self.result();r['calls'].pop()
        with self.assertRaises(ValueError):validate_result(r,self.b.identity,12345)
        r=self.result();r['calls'][1]['job_id']=1
        with self.assertRaises(ValueError):validate_result(r,self.b.identity,12345)

    def test_error_outputs_and_fake_metrics_rejected(self):
        changes={'numeric_pass':False,'guards_intact':False,'status_code':5,'kernel_build_id':1,
                 'output_consumable':False,'completion_validated':False,'actual_output_sha256':'',
                 'host_verified_completions':True,'service_ms':0.,'input_quant_ms':float('nan'),
                 'pure_kernel_ms':1.,'measured_AXI_bytes':1,'hardware_cycles':1}
        for key,value in changes.items():
            r=self.result();r['calls'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_result(r,self.b.identity,12345)

    def test_release_refused_while_running(self):
        observe=Mock()
        with self.assertRaises(Parked):self.b.check_release(observe)
        observe.assert_not_called()

    def test_failed_postexit_scan_retains(self):
        self.path.write_text(json.dumps(self.result()));self.b.wait_normal(10)
        with self.assertRaises(Parked):self.b.check_release(lambda:({},1,False))


if __name__=='__main__':unittest.main(verbosity=2)
