"""Native Linux regression of bounded observations and identity-bound parked-owner retirement."""
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
from common import ROOT,save
from step07_finalize_policy import validate_retirement,retire_once,complete_scan

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
from accelerator_release_gate_v2 import SCHEMA,require_no_users


def scan():return dict(schema=SCHEMA,scan_complete=True,boot_id='pc-boot',boot_id_after='pc-boot',
    scan_issues=[],device_holders=[],device_mappings=[],inspected_processes=['1'],ps_display_holders=[],ps_display_mappings=[])


def inventory():
    e=dict(boot_id='pc-boot',machine_sha256='pc-only',manager_pid=123,manager_start_ticks=456,
           lease_sha256='lease',manifest_sha256='manifest')
    s=dict(e,observed_monotonic_ns=time.monotonic_ns(),ZOCL_absent=True,module_refcount=None)
    for k in ('no_device_users','no_manager_devices','no_manager_XRT','no_manager_children','single_sleeping_thread',
              'source_pins_match','workers_normal_exit','default_restored','kernel_allowed','old_manager_owns_both_locks','known_parked_code'):s[k]=True
    return s,e


class Tests(unittest.TestCase):
    def test_each_identity_and_quiescence_fault_blocks_retirement(self):
        s,e=inventory();self.assertTrue(validate_retirement(s,e))
        for key in e:
            bad=dict(s);bad[key]='wrong'
            with self.subTest(key=key),self.assertRaises(RuntimeError):validate_retirement(bad,e)
        for key,value in s.items():
            if value is True:
                bad=dict(s);bad[key]=False
                with self.subTest(key=key),self.assertRaises(RuntimeError):validate_retirement(bad,e)
        bad=dict(s,observed_monotonic_ns=time.monotonic_ns()-6_000_000_000)
        with self.assertRaises(RuntimeError):validate_retirement(bad,e)
        with self.assertRaises(RuntimeError):validate_retirement(dict(s,module_refcount=0),e)

    def test_failed_observation_saved_and_only_complete_scan_accepted(self):
        first=scan();first.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        collector=Mock(side_effect=[first,scan()]);records=[]
        result=complete_scan(collector,require_no_users,'pc-boot',lambda:True,lambda event,**r:records.append(r),pause=lambda _:None)
        self.assertTrue(result['scan_complete']);self.assertEqual(collector.call_count,2)
        self.assertFalse(records[0]['scan']['scan_complete']);self.assertTrue(records[1]['scan']['scan_complete'])

    def test_unknown_or_device_or_boot_fault_never_retried_as_success(self):
        variants=[dict(boot_id='wrong'),dict(device_holders=[dict(pid=99)]),dict(device_mappings=[dict(pid=99)]),
                  dict(scan_complete=False,scan_issues=[dict(reason='PermissionError: denied')]),
                  dict(scan_complete=False,scan_issues=[dict(pid=99,reason="FileNotFoundError: [Errno 2] No such file or directory: '/proc/88/maps'")])]
        for v in variants:
            one=scan();one.update(v);collector=Mock(return_value=one)
            with self.subTest(v=v),self.assertRaises(RuntimeError):complete_scan(collector,require_no_users,'pc-boot',lambda:True,lambda *a,**k:None,pause=lambda _:None)
            self.assertEqual(collector.call_count,1)
        collector=Mock(return_value=scan())
        with self.assertRaises(RuntimeError):complete_scan(collector,require_no_users,'pc-boot',lambda:False,lambda *a,**k:None,pause=lambda _:None)
        self.assertEqual(collector.call_count,1)

    def test_persistent_churn_is_bounded_and_never_passes(self):
        s=scan();s.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        collector=Mock(return_value=s);events=[]
        with self.assertRaises(RuntimeError):complete_scan(collector,require_no_users,'pc-boot',lambda:True,lambda *a,**k:events.append(k),pause=lambda _:None)
        self.assertEqual(collector.call_count,4);self.assertEqual(len(events),4)

    def test_native_parked_child_pidfd_exit_releases_real_flocks(self):
        with tempfile.TemporaryDirectory() as td:
            paths=[Path(td)/'first.lock',Path(td)/'second.lock']
            child=r'''import fcntl,json,os,signal,sys,time
signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM,signal.SIGHUP,signal.SIGQUIT})
fds=[open(p,'a+') for p in sys.argv[1:]]
for f in fds:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
print(json.dumps({'pid':os.getpid()}),flush=True)
while True:time.sleep(1)
'''
            p=subprocess.Popen([sys.executable,'-u','-c',child,*map(str,paths)],stdout=subprocess.PIPE,text=True)
            self.assertEqual(json.loads(p.stdout.readline())['pid'],p.pid)
            for path in paths:
                with path.open('a+') as f:
                    with self.assertRaises(BlockingIOError):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            s,e=inventory();s['manager_pid']=e['manager_pid']=p.pid
            fd=os.pidfd_open(p.pid,0);events=[]
            try:retire_once(fd,s,e,lambda event,**r:events.append(dict(event=event,**r)))
            finally:os.close(fd)
            self.assertEqual(p.wait(timeout=3),-9);p.stdout.close()
            for path in paths:
                with path.open('a+') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertEqual([v['event'] for v in events],['EXACT_PARKED_OWNER_RETIRE_RESERVED','EXACT_PARKED_OWNER_SIGNAL_SENT','EXACT_PARKED_OWNER_EXIT_PROVEN_BY_PIDFD'])
            self.assertFalse(events[-1]['normal_manager_exit'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    save(OUT/'POLICY_PC.json',dict(status='PASS_PC_LINUX_RETIREMENT_AND_SCAN_GATES' if result.wasSuccessful() else 'FAIL',
         methods=result.testsRun,BOARD='NOT_TESTED',native_child_exit=-9,board_computation=0))
    raise SystemExit(0 if result.wasSuccessful() else 1)
