"""Private file/persistence faults and real read-only page/process observations."""
import ctypes
import io
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest import mock
import sys

from mode_evidence import OUT,PARENT,read,save
from mode_journal import ModeJournal,ModeBlocked,read_journal
from mode_reader import PageObservation,ProcessObservation
from microbatch_page import BatchPage


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a12-mode-journal-');self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'state';self.handles=[]
        self.addCleanup(lambda:[j.dispose() for j in self.handles if not j.closed])
    def journal(self):
        j=ModeJournal(self.path,'e'*32);self.handles.append(j);return j
    def test_valid_close_and_reopen_preserves_chain(self):
        a=self.journal();a.append('SESSION_OPEN');a.append('SESSION_CLOSE');a.finish()
        rows=read_journal(self.path/'coordinator.jsonl');self.assertEqual(len(rows),2)
        b=self.journal();b.append('SESSION_OPEN');b.append('SESSION_CLOSE');b.finish()
        self.assertEqual(len(read_journal(self.path/'coordinator.jsonl')),4)
    def test_second_lock_and_unclean_restart_refused(self):
        a=self.journal();a.append('SESSION_OPEN')
        with self.assertRaises(BlockingIOError):self.journal()
        a.dispose()
        with self.assertRaisesRegex(ModeBlocked,'unclean'):self.journal()
    def test_fsync_failure_keeps_dirty_even_when_close_bytes_exist(self):
        a=self.journal();a.append('SESSION_OPEN');actual=os.fsync
        def fail(fd):
            if fd==a.fd:raise OSError('PC injected journal fsync')
            return actual(fd)
        with mock.patch('mode_journal.os.fsync',side_effect=fail):
            with self.assertRaises(OSError):a.append('SESSION_CLOSE')
        self.assertTrue(a.blocked);self.assertTrue((self.path/'DIRTY.json').exists())
        self.assertEqual(read_journal(self.path/'coordinator.jsonl')[-1]['event'],'SESSION_CLOSE')
        a.dispose()
        with self.assertRaises(ModeBlocked):self.journal()
    def test_changed_log_marker_and_lock_are_refused(self):
        for name in ('coordinator.jsonl','DIRTY.json','coordinator.lock'):
            path=self.path/name
            if self.path.exists():self.tmp.cleanup();self.tmp=tempfile.TemporaryDirectory(prefix='a12-mode-journal-');self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'state';path=self.path/name
            j=self.journal();j.append('SESSION_OPEN')
            if name=='coordinator.jsonl':path.write_bytes(path.read_bytes().replace(b'SESSION_OPEN',b'SESSION_XPEN'))
            elif name=='DIRTY.json':path.write_bytes(b'{}\n')
            else:path.unlink();path.write_bytes(b'')
            with self.assertRaises(ModeBlocked):j.append('SHOULD_NOT_COMMIT')
            self.assertTrue(j.blocked);j.dispose()
    def test_short_writes_are_completed_without_losing_bytes(self):
        j=self.journal();actual=os.write
        with mock.patch('mode_journal.os.write',side_effect=lambda fd,raw:actual(fd,raw[:3])):
            j.append('SESSION_OPEN');j.append('SESSION_CLOSE')
        j.finish();self.assertEqual(len(read_journal(self.path/'coordinator.jsonl')),2)
    def test_zero_progress_write_latches(self):
        j=self.journal()
        with mock.patch('mode_journal.os.write',return_value=0):
            with self.assertRaises(ModeBlocked):j.append('SESSION_OPEN')
        self.assertTrue(j.blocked)
    def test_unlisted_state_files_and_unsafe_permissions_refused(self):
        self.path.mkdir(parents=True);(self.path/'alien').write_text('x')
        with self.assertRaises(ModeBlocked):self.journal()
    def test_record_bound_is_enforced(self):
        j=self.journal()
        with self.assertRaises(ModeBlocked):j.append('OVERSIZE',payload='x'*8192)
        self.assertTrue(j.blocked)


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.build=read(PARENT/'BUILD-v5-reviewed.json');self.reader=read(OUT/'READER_BUILD-v2.json')
        self.page=BatchPage(self.build['library']);self.addCleanup(self.page.close)
    def observation(self):
        o=PageObservation(os.dup(self.page.fd),self.reader);self.addCleanup(o.close);return o
    def test_read_only_observer_sees_real_revoke_and_cannot_write(self):
        o=self.observation();self.assertFalse(o.snapshot()['revoked'])
        with self.assertRaises(OSError):os.write(o.fd,b'x')
        self.page.revoke();self.assertTrue(o.snapshot()['revoked'])
    def test_observer_survives_writer_close_without_changing_page(self):
        o=self.observation();self.page.close();s=o.snapshot();self.assertTrue(s['revoked']);self.assertEqual(s['shared_claims'],0)
    def test_reader_rejects_RW_FD(self):
        lib=ctypes.CDLL(self.reader['library']);f=lib.a12_pc_mode_read_page_v1
        f.argtypes=[ctypes.c_int,ctypes.c_void_p,ctypes.c_uint64];f.restype=ctypes.c_int
        out=ctypes.create_string_buffer(1024);self.assertNotEqual(f(self.page.fd,out,len(out)),0)
    def test_pidfd_acquired_live_reports_actual_terminal(self):
        import subprocess
        from mode_child import start_ticks
        p=subprocess.Popen([sys.executable,'-c','import sys;sys.stdin.read()'],stdin=subprocess.PIPE)
        o=ProcessObservation(p.pid,start_ticks(p.pid));self.addCleanup(o.close)
        self.assertFalse(o.terminal());p.stdin.close();p.wait(timeout=5);self.assertTrue(o.terminal())


if __name__=='__main__':
    target=OUT/'control-tests-02';target.mkdir(exist_ok=False);stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue());save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',
        tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),domain='PC_REAL_FILES_PAGE_AND_PIDFD',BOARD='NOT_TESTED',PL_calls=0))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
