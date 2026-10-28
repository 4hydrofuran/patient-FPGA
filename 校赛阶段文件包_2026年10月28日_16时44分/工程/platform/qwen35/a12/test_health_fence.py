"""Deterministic PC races and real Linux file/map mutation checks."""
import ctypes
from dataclasses import replace
import hashlib
import io
import json
import mmap
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from fresh_identity_io import FreshCheckedFile,FreshMaps,IdentityBlocked
from health_fence import HealthFence,HealthBlocked
from health_fence_evidence import OUT,save


class HealthTests(unittest.TestCase):
    def monitor(self,observe=lambda:dict(ok=True),**kw):
        m=HealthFence(observe,**kw);self.addCleanup(m.stop);return m

    def test_every_fence_requires_a_new_started_sample(self):
        m=self.monitor()
        for _ in range(200):
            t=m.fence();self.assertGreaterEqual(t.started_ns,t.requested_ns);m.authorize(t)
        s=m.status();self.assertEqual(s['counters']['fences'],200)
        self.assertEqual(s['counters']['authorizations'],200);self.assertEqual(len(s['recent_samples']),64)

    def test_sample_in_progress_before_request_cannot_satisfy_fence(self):
        entered=threading.Event();release=threading.Event();calls=[]
        def observe():
            calls.append(1)
            if len(calls)==1:entered.set();release.wait(1)
            return dict(call=len(calls))
        m=self.monitor(observe);self.assertTrue(entered.wait(1))
        timer=threading.Timer(0.02,release.set);timer.start();self.addCleanup(timer.join)
        t=m.fence();self.assertGreaterEqual(t.sample,2);self.assertEqual(json.loads(t.observation)['call'],2)
        m.authorize(t)

    def test_reused_forged_foreign_and_wrong_thread_tickets_latch(self):
        for kind in ('reuse','forge','foreign','thread'):
            with self.subTest(kind=kind):
                m=self.monitor();t=m.fence();errors=[]
                if kind=='reuse':m.authorize(t)
                if kind=='forge':t=replace(t,serial=t.serial+1)
                if kind=='foreign':t=self.monitor().fence()
                if kind=='thread':
                    def other():
                        try:m.authorize(t)
                        except HealthBlocked:errors.append(True)
                    th=threading.Thread(target=other);th.start();th.join(1);self.assertEqual(errors,[True])
                else:
                    with self.assertRaises(HealthBlocked):m.authorize(t)
                with self.assertRaises(HealthBlocked):m.fence()

    def test_slow_log_cannot_prevent_independent_fault_publication(self):
        failed=threading.Event();faulted=threading.Event();disk_lock=threading.Lock()
        def observe():
            if failed.is_set():raise RuntimeError('fixture kernel fault')
            return dict(ok=True)
        m=self.monitor(observe,interval_s=0.005,on_fault=lambda r:faulted.set())
        ticket=m.fence()
        with disk_lock:
            failed.set();self.assertTrue(faulted.wait(1))
            with self.assertRaises(HealthBlocked):m.authorize(ticket)
        self.assertEqual(m.status()['counters']['authorizations'],0)

    def test_callback_failure_does_not_clear_latch(self):
        def cb(r):raise OSError('callback failed')
        def observe():raise OSError('read failed')
        m=self.monitor(observe,on_fault=cb)
        with self.assertRaises(HealthBlocked):m.fence()
        self.assertIn('read failed',m.status()['fault'])

    def test_stalled_sample_times_out_and_stop_never_fakes_join(self):
        entered=threading.Event();release=threading.Event()
        def observe():entered.set();release.wait(2);return dict(ok=True)
        m=self.monitor(observe,timeout_s=0.03);self.assertTrue(entered.wait(1))
        try:
            with self.assertRaises(HealthBlocked):m.fence()
            self.assertFalse(m.stop(0.01));self.assertTrue(m.status()['thread_alive'])
        finally:release.set()
        self.assertTrue(m.stop())

    def test_stale_ticket_after_slow_end_is_rejected(self):
        m=self.monitor(max_age_s=0.01);t=m.fence();time.sleep(0.02)
        with self.assertRaises(HealthBlocked):m.authorize(t)
        self.assertEqual(m.status()['counters']['authorizations'],0)

    def test_invalid_or_oversize_observations_latch(self):
        for value in ([],dict(x=float('nan')),dict(x='x'*8193)):
            with self.subTest(type=type(value).__name__):
                m=self.monitor(lambda:value)
                with self.assertRaises(HealthBlocked):m.fence()

    def test_stop_refuses_new_fences_and_unused_tickets(self):
        m=self.monitor();t=m.fence();self.assertTrue(m.stop())
        with self.assertRaises(HealthBlocked):m.authorize(t)


@unittest.skipUnless(os.name=='posix','Linux PC file checks')
class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a12-fresh-');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.file=self.root/'lease.json';self.raw=b'original'+b'x'*131072
        self.file.write_bytes(self.raw);self.file.chmod(0o600)
    def reader(self,**kw):
        r=FreshCheckedFile(self.file,hashlib.sha256(self.raw).hexdigest(),**kw);self.addCleanup(r.close);return r

    def test_full_content_read_each_time_with_bounded_buffer_and_one_open(self):
        r=self.reader(expected_bytes=self.raw,chunk=127)
        for _ in range(4):self.assertTrue(r.check()['content_read_fresh'])
        self.assertEqual(r.bytes_read,5*len(self.raw));self.assertEqual(r.opens,1);self.assertEqual(len(r.buffer),127)

    def test_replace_symlink_truncate_and_mutation_always_latch(self):
        for action in ('replace','symlink','truncate','mutate'):
            self.file.unlink(missing_ok=True);self.file.write_bytes(self.raw);self.file.chmod(0o600)
            r=self.reader()
            if action=='replace':
                q=self.root/'new';q.write_bytes(self.raw);q.chmod(0o600);q.replace(self.file)
            elif action=='symlink':self.file.unlink();self.file.symlink_to(self.root/'absent')
            elif action=='truncate':self.file.write_bytes(b'x')
            else:self.file.write_bytes(b'X'+self.raw[1:])
            with self.assertRaises(IdentityBlocked):r.check()
            self.assertTrue(r.blocked);r.close()

    def test_mmap_second_write_can_keep_metadata_but_fresh_digest_rejects(self):
        with self.file.open('r+b') as stream:
            mm=mmap.mmap(stream.fileno(),0);self.addCleanup(mm.close)
            mm[0]=ord('A') # first dirtying establishes timestamps before the pin
            self.raw=mm[:];r=self.reader();before=self.file.stat()
            mm[1]=ord('B');after=self.file.stat()
            self.assertEqual((before.st_size,before.st_mtime_ns,before.st_ctime_ns),
                (after.st_size,after.st_mtime_ns,after.st_ctime_ns))
            with self.assertRaisesRegex(IdentityBlocked,'digest'):r.check()

    def test_real_proc_maps_fd_observes_later_cpu_mapping_named_xrt(self):
        # A harmless existing CPU ELF under an XRT-like name. Isolated process;
        # this is not an XRT load, board access or library implementation.
        script='''
import ctypes,shutil,sys
from pathlib import Path
from fresh_identity_io import FreshMaps,IdentityBlocked
r=FreshMaps(chunk=17);r.check()
source=Path('/lib/x86_64-linux-gnu/libm.so.6');target=Path(sys.argv[1])/'libxrt_fixture.so'
shutil.copyfile(source,target);handle=ctypes.CDLL(str(target))
try:r.check()
except IdentityBlocked:print('NEW_MAPPING_REFUSED');r.close();raise SystemExit(0)
raise SystemExit(3)
'''
        env=dict(os.environ,PYTHONPATH=str(Path(__file__).parent))
        run=subprocess.run([sys.executable,'-c',script,str(self.root)],env=env,capture_output=True,text=True,timeout=5)
        self.assertEqual(run.returncode,0,run.stderr);self.assertIn('NEW_MAPPING_REFUSED',run.stdout)

    def test_maps_cross_chunk_marker_decode_and_budget_fail_closed(self):
        for raw,chunk,limit in ((b'abc libxrt_test',7,100),(b'abc\xff',3,100),(b'a'*40,7,10),(b'',2,10)):
            p=self.root/'maps';p.write_bytes(raw);r=FreshMaps(path=str(p),chunk=chunk,limit=limit)
            self.addCleanup(r.close)
            with self.assertRaises((IdentityBlocked,UnicodeDecodeError)):r.check()
            self.assertTrue(r.blocked)


def main():
    target=OUT/'pc-tests-01';target.mkdir(exist_ok=False)
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue(),encoding='utf-8')
    save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,
        errors=len(r.errors),failures=len(r.failures),BOARD='NOT_TESTED',PL_calls=0))
    print(stream.getvalue());return 0 if r.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
