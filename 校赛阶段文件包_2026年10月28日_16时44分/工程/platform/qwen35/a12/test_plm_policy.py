"""Actual atomic-writer boundaries and durable file faults; no XRT/model/device."""
import io
import mmap
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from plm_page import Page
from plm_journal import Journal
from plm_evidence import OUT,read,save
from plm_manager import ticks

class AtomicPolicy(unittest.TestCase):
    def setUp(self):
        self.build=read(OUT/'BUILD-v4.json');self.page=Page(self.build['writer_library'],self.build['writer_sha256'])
        self.page.health(time.monotonic_ns())
    def tearDown(self):self.page.close()
    def ready(self):
        # Identity-only helper fixture: no worker/Gate/device is created here.
        self.page.bind(os.getpid(),ticks(os.getpid()),'a'*64);self.page.load_end()
    def test_unbound_and_invalid_identity(self):
        with self.assertRaises(RuntimeError):self.page.begin(0,72,'b'*64)
        with self.assertRaises(RuntimeError):self.page.bind(os.getpid(),ticks(os.getpid()),'bad')
        self.assertEqual(self.page.snapshot()['worker_pid'],0)
    def test_startup_cannot_grant(self):
        self.page.bind(os.getpid(),ticks(os.getpid()),'a'*64)
        with self.assertRaises(RuntimeError):self.page.grant(1,72)
        with self.assertRaises(RuntimeError):self.page.begin(0,72,'b'*64)
    def test_request_and_range_caps(self):
        self.ready()
        with self.assertRaises(RuntimeError):self.page.begin(0,5001,'b'*64)
        with self.assertRaises(RuntimeError):self.page.begin(0,0,'b'*64)
        self.page.begin(0,72,'b'*64)
        with self.assertRaises(RuntimeError):self.page.grant(1,73)
        self.page.grant(1,72)
        with self.assertRaises(RuntimeError):self.page.grant(1,72)
        with self.assertRaises(RuntimeError):self.page.end(0) # unconsumed credits never appear completed
        with self.assertRaises(RuntimeError):self.page.begin(0,72,'c'*64)
    def test_request_generation_bound_and_revoke_sticky(self):
        self.ready()
        for gen in (2,3,4):
            self.page.begin(0,72,str(gen)*64);self.assertEqual(self.page.snapshot()['generation'],gen)
            self.page.end(0) # no grant issued: helper accounting only, not delivery approval
        with self.assertRaises(RuntimeError):self.page.begin(0,72,'e'*64)
        self.page.revoke()
        with self.assertRaises(RuntimeError):self.page.health(time.monotonic_ns())
        with self.assertRaises(RuntimeError):self.page.begin(0,72,'e'*64)
    def test_health_publication_is_monotonic_and_not_future(self):
        with self.assertRaises(RuntimeError):self.page.health(time.monotonic_ns()+1_000_000_000)
        with self.assertRaises(RuntimeError):self.page.health(1)
    def test_missing_writer_API_opens_no_page_FD(self):
        lib=self.build['observer_library'];from plm_evidence import sha
        before=len(os.listdir('/proc/self/fd'))
        with self.assertRaises(AttributeError):Page(lib,sha(lib))
        self.assertEqual(before,len(os.listdir('/proc/self/fd')))
    def test_failed_page_geometry_closes_only_new_unbound_FD(self):
        before=len(os.listdir('/proc/self/fd'))
        with patch('plm_page.os.ftruncate',side_effect=OSError('PC injected ftruncate failure')):
            with self.assertRaises(OSError):Page(self.build['writer_library'],self.build['writer_sha256'])
        self.assertEqual(before,len(os.listdir('/proc/self/fd')))

class DurablePolicy(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.failures=[];self.j=Journal(Path(self.temp.name)/'state','d'*32,self.failures.append)
    def tearDown(self):
        for fd in (self.j.fd,self.j.lock,self.j.root):
            try:os.close(fd)
            except OSError:pass
        self.temp.cleanup() # ephemeral PC fixture only, never project/board evidence
    def test_zero_progress_latches_dirty(self):
        with patch('plm_journal.os.write',return_value=0):
            with self.assertRaises(RuntimeError):self.j.append('WINDOW_OPEN')
        self.assertTrue(self.j.blocked and self.failures and (self.j.path/'DIRTY.json').exists())
        with self.assertRaises(RuntimeError):self.j.append('WINDOW_OPEN')
    def test_full_end_bytes_are_not_fsync_or_close_proof(self):
        self.j.append('WINDOW_OPEN');self.j.fault='end_fsync'
        with self.assertRaises(OSError):self.j.append('END',request_id='app_R0')
        self.assertIn(b'"event":"END"',(self.j.path/'control.jsonl').read_bytes())
        self.assertEqual(self.j.serial,1);self.assertTrue(self.j.blocked and self.failures)
        self.assertTrue((self.j.path/'DIRTY.json').exists())
    def test_receipt_fsync_failure_keeps_dirty(self):
        self.j.fault='receipt_fsync'
        with self.assertRaises(OSError):self.j.receipt('app_R0',dict(domain='PC_FIXTURE'))
        self.assertTrue((self.j.path/'app_R0-receipt.json').is_file() and self.j.blocked and self.failures)
        self.assertTrue((self.j.path/'DIRTY.json').exists())
    def test_boundary_reads_current_history_bytes(self):
        self.j.append('WINDOW_OPEN');self.j.check_all();path=self.j.path/'control.jsonl'
        with path.open('r+b') as f:
            with mmap.mmap(f.fileno(),0) as data:
                i=data[:].index(b'WINDOW_OPEN');data[i]=ord('X')
        self.j.owner_check() # live marker/inodes are not a cached content verdict
        with self.assertRaises(RuntimeError):self.j.check_all()

if __name__=='__main__':
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    save(OUT/'UNIT_POLICY_RESULT-v2.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,output=stream.getvalue(),
        verification_layer='PRIVATE_ATOMIC_MANAGER_AND_PC_FILE_IO_ONLY',BOARD='NOT_TESTED',actual_FPGA_calls=None))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
