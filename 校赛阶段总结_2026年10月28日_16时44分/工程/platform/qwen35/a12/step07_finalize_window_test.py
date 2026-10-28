"""Future Window v2 actual Linux flock/archive/recovery tests, physical BOARD untested."""
import fcntl
import json
import os
import sys
from pathlib import Path
import tempfile
import time
import types
import unittest
from unittest.mock import Mock,patch
import window_closeout_v2 as window
from common import ROOT,sha,save
from accelerator_release_gate_v2 import SCHEMA,start_ticks

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'active').mkdir();(self.root/'active/lease.json').write_text('{}')
        self.paths=(self.root/'deployment.lock',self.root/'device.lock');self.fds=[]
        for p in self.paths:
            fd=os.open(p,os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.fds.append(fd)
        self.owner=window.Window.__new__(window.Window);o=self.owner
        o.locks=self.fds;o.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        o.lease_hash=sha(self.root/'active/lease.json');o.evidence=self.root/'evidence';o.evidence.mkdir()
        o.finished=False;o.review=dict(window_id='pc-finalize-v2');o.health=lambda **kwargs:None
        o._verify_default=lambda:None # PC fixture, no FPGA/GDM claim.
        self.worker=types.SimpleNamespace(closed=True,process=types.SimpleNamespace(returncode=0))
        o._owned_worker=self.worker
        self.patches=[patch.object(window,'CENTRAL',self.root),patch.object(window,'LOCKS',self.paths)]
        for p in self.patches:p.start()
    def tearDown(self):
        for fd in list(self.fds):
            try:os.close(fd)
            except OSError:pass
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def scan(self):return dict(schema=SCHEMA,scan_complete=True,boot_id=self.owner.boot,boot_id_after=self.owner.boot,
        scan_issues=[],device_holders=[],device_mappings=[],inspected_processes=[str(os.getpid())])
    def held(self):
        for p in self.paths:
            with p.open('a+') as f:
                with self.assertRaises(BlockingIOError):fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.assertTrue((self.root/'active/lease.json').exists())
    def ticket(self,**override):
        r=dict(schema='A12_FINALIZE_ONLY_V2',op='finish_only',boot_id=self.owner.boot,
             window_id=self.owner.review['window_id'],manager_pid=os.getpid(),manager_start_ticks=start_ticks(Path('/proc/self')),
             lease_sha256=self.owner.lease_hash,expires_monotonic_ns=time.monotonic_ns()+20_000_000_000)
        r.update(override);p=self.owner.evidence/'finalize-request-0001.json';p.write_text(json.dumps(r));p.chmod(0o600);return p
    def trusted(self,p):
        s=p.stat();assert not p.is_symlink() and s.st_uid==os.geteuid() and not s.st_mode&0o022
    def test_churn_then_complete_preserves_failed_snapshot_and_finishes(self):
        first=self.scan();first.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        with patch.object(window,'collect',side_effect=[first,self.scan()]):self.owner.finish(self.worker)
        rows=[json.loads(l) for l in (self.owner.evidence/'finalization-events.jsonl').read_text().splitlines()]
        scans=[r for r in rows if r['event']=='FULL_PROCESS_OBSERVATION']
        self.assertEqual(len(scans),2);self.assertFalse(scans[0]['scan']['scan_complete'])
        self.assertTrue(self.owner.finished);self.assertFalse((self.root/'active').exists())
        self.assertEqual(sha(self.root/'history/pc-finalize-v2/lease.json'),self.owner.lease_hash)
        for p in self.paths:
            with p.open('a+') as f:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
    def test_persistent_churn_retains_locks_lease_and_four_raw_failures(self):
        s=self.scan();s.update(scan_complete=False,scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        with patch.object(window,'collect',return_value=s),self.assertRaises(RuntimeError):self.owner.finish(self.worker)
        self.held();self.assertFalse(self.owner.finished)
        rows=[json.loads(l) for l in (self.owner.evidence/'finalization-events.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),4);self.assertTrue(all(not r['scan']['scan_complete'] for r in rows))
    def test_device_holder_blocks_without_retry_or_archive(self):
        s=self.scan();s['device_holders']=[dict(pid=99)];collector=Mock(return_value=s)
        with patch.object(window,'collect',collector),self.assertRaises(RuntimeError):self.owner.finish(self.worker)
        self.assertEqual(collector.call_count,1);self.held()
    def test_pending_or_bad_worker_cannot_finish(self):
        for closed,code in ((False,0),(True,1)):
            w=types.SimpleNamespace(closed=closed,process=types.SimpleNamespace(returncode=code))
            with self.assertRaises(RuntimeError):self.owner.finish(w)
            self.held()
    def test_finalize_ticket_cannot_widen_or_replay_identity(self):
        for override in (dict(op='compute'),dict(boot_id='other'),dict(manager_pid=99),dict(lease_sha256='other'),
                         dict(expires_monotonic_ns=0),dict(expires_monotonic_ns=time.monotonic_ns()+60_000_000_000)):
            p=self.ticket(**override)
            with patch.object(window,'trusted_file',self.trusted),self.assertRaises(RuntimeError):self.owner._apply_finalize_ticket(p)
            p.unlink();self.held()
    def test_ticket_refuses_pending_child_without_signal(self):
        self.owner._owned_worker.closed=False;p=self.ticket()
        with patch.object(window,'trusted_file',self.trusted),self.assertRaises(RuntimeError):self.owner._apply_finalize_ticket(p)
        self.assertTrue(p.exists());self.held()
    def test_explicit_finalize_only_request_exits_normally_after_cleanup(self):
        p=self.ticket()
        with patch.object(window,'trusted_file',self.trusted),patch.object(window,'collect',return_value=self.scan()):
            with self.assertRaises(SystemExit) as result:self.owner.retain_until_finished('synthetic prior scan failure')
        self.assertEqual(result.exception.code,0);self.assertTrue(self.owner.finished)
        self.assertTrue((self.owner.evidence/'consumed-finalize-request-0001.json').exists())
        self.assertFalse((self.root/'active').exists());self.assertTrue((self.owner.evidence/'ISOLATED.json').exists())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    name='WINDOW_V2_PC_FINAL.json' if sys.argv[1:]==['final'] else 'WINDOW_V2_PC.json'
    save(OUT/name,dict(status='PASS_PC_WINDOW_V2_FLOCK_SCAN_AND_CONTROLLED_RECOVERY' if result.wasSuccessful() else 'FAIL',
         methods=result.testsRun,BOARD='NOT_TESTED',new_computation=0,signals_from_recovery_ticket=0,
         tested_source_sha256=sha(ROOT/'platform/qwen35/a12/window_closeout_v2.py')))
    raise SystemExit(0 if result.wasSuccessful() else 1)
