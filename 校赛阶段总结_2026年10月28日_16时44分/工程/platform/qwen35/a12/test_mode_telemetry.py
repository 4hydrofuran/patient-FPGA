"""Real SCM_RIGHTS, page and live pidfd binding failure cleanup."""
import array
import io
import os
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest import mock
import sys
from mode_evidence import OUT,PARENT,read,save
from mode_coordinator import ModeCoordinator
from mode_child import start_ticks
from mode_journal import ModeBlocked
from microbatch_page import BatchPage
from request_journal_verified import canonical

class TelemetryTests(unittest.TestCase):
    def test_mismatched_page_closes_new_native_pidfd(self):
        page=BatchPage(read(PARENT/'BUILD-v5-reviewed.json')['library']);self.addCleanup(page.close)
        parent,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET);self.addCleanup(parent.close);self.addCleanup(child.close)
        c=ModeCoordinator.__new__(ModeCoordinator);c.epoch='a'*32;c.capsule={'reader_build':str(OUT/'READER_BUILD-v2.json')}
        ticks=start_ticks(os.getpid());r=dict(telemetry=None,socket=parent,window_id='b'*32,cap=72,
            process=types.SimpleNamespace(pid=os.getpid()),manager=types.SimpleNamespace(ticks=ticks))
        data=dict(event='MODE_NATIVE_OWNED',domain='PC_NATIVE_MATH_NOT_FPGA',session_epoch=c.epoch,window_id=r['window_id'],
            grant_size=72,manager_pid=os.getpid(),manager_start_ticks=ticks,native_pid=os.getpid(),native_start_ticks=ticks,
            page_epoch='c'*32) # deliberately differs from the real page
        before=len(list(Path('/proc/self/fd').iterdir()))
        child.sendmsg([canonical(data)],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[page.fd]))])
        with self.assertRaisesRegex(ModeBlocked,'page owner'):c._receive(r)
        after=len(list(Path('/proc/self/fd').iterdir()));self.assertEqual(after,before,'native pidfd leaked on rejected telemetry')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args();target=OUT/a.tag;target.mkdir(exist_ok=False)
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue());save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',
        tests=r.testsRun,errors=len(r.errors),failures=len(r.failures),domain='REAL_PC_TELEMETRY_NEGATIVE_IO',BOARD='NOT_TESTED'))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
