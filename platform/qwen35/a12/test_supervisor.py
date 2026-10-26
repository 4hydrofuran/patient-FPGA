"""Real Linux subprocess/flock/socket tests; never opens XRT or a board device."""
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import sys
import tempfile
import time
import unittest
from supervisor import OwnedWorker


WORKER=r'''
import json,os,signal,socket,sys,time
signal.signal(signal.SIGUSR1,lambda *args:None)
s=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']))
print(json.dumps({'type':'ready','pid':os.getpid()}),flush=True)
seq=0
for line in sys.stdin:
    r=json.loads(line)
    if r.get('op')=='shutdown':
        time.sleep(float(os.environ.get('SLOW_CLOSE','0')));break
    if r.get('op')=='wait':time.sleep(.2);print(json.dumps({'type':'result'}),flush=True);continue
    seq+=1
    q=dict(sequence=seq,pid=os.getpid(),phase=r.get('phase','submit'),job=seq)
    if r.get('bad'):q['sequence']=0
    s.sendall((json.dumps(q)+'\n').encode())
    response=s.makefile('r').readline()
    print(json.dumps({'type':'permit','response':response}),flush=True)
'''


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.workers=[]
    def tearDown(self):
        for w in self.workers:
            # All doubles terminate themselves; no kill/terminate escape hatch in tests.
            if w.process.poll() is None:
                w.process.stdin.write('{"op":"shutdown"}\n');w.process.stdin.flush();w.process.wait(timeout=2)
            w.quarantined=False;w.close(timeout=2)
        self.tmp.cleanup()
    def start(self,**kwargs):
        env=dict(os.environ,**kwargs.pop('extra_env',{}))
        w=OwnedWorker([sys.executable,'-u','-c',WORKER],directory=self.base/str(len(self.workers)),env=env,
          health=kwargs.pop('health',lambda:None),max_runs=1,max_loads=1,expires=time.monotonic()+5,**kwargs)
        self.workers.append(w);self.assertEqual(w.get(2)['type'],'ready');return w
    def test_permit_limit_no_submission_after_bound(self):
        w=self.start();w.send({'phase':'submit'});self.assertTrue(json.loads(w.get(2)['response'])['allow'])
        w.send({'phase':'submit'});self.assertFalse(json.loads(w.get(2)['response'])['allow']);self.assertEqual(w.runs,1)
    def test_corrupt_sequence_quarantines(self):
        w=self.start();w.send({'bad':True});w.get(2);time.sleep(.02);self.assertTrue(w.quarantined)
        self.assertFalse(w.close());self.assertIsNone(w.process.poll())
    def test_deadline_discards_late_result_and_retains_child(self):
        w=self.start();w.send({'op':'wait'})
        with self.assertRaises(TimeoutError):w.get(.01)
        self.assertIsNone(w.process.poll())
        with self.assertRaises(RuntimeError):w.get(2)
        with self.assertRaises(RuntimeError):w.send({'op':'generate'})
    def test_slow_close_never_kills_worker(self):
        w=self.start(extra_env={'SLOW_CLOSE':'.2'});self.assertFalse(w.close(timeout=.01))
        self.assertIsNone(w.process.poll());w.process.wait(timeout=2)
    def test_real_inherited_flock_not_released_on_close_timeout(self):
        p=self.base/'lock';lock=p.open('a+');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        w=self.start(inherited_fds=(lock.fileno(),),extra_env={'SLOW_CLOSE':'.2'})
        self.assertFalse(w.close(timeout=.01))
        with p.open('a+') as other:
            with self.assertRaises(BlockingIOError):fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
        w.process.wait(timeout=2);lock.close()
    def test_health_fault_refuses_work_retains_worker(self):
        def fail():raise RuntimeError('synthetic health gate')
        w=self.start(health=fail);w.send({'phase':'submit'});w.get(2);time.sleep(.02)
        self.assertTrue(w.quarantined);self.assertEqual(w.runs,0);self.assertIsNone(w.process.poll())
    def test_real_worker_requires_owner_gate(self):
        with self.assertRaises(ValueError):self.start(real=True)


if __name__=='__main__':unittest.main()
