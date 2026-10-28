"""Offline tests. Temporary locks are PC-only; no serial/SSH/XRT imports."""
import argparse
from collections import Counter
import fcntl
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from freeze_vectors import schedule, scalar

LOCK_BINARY=None


class Preparation(unittest.TestCase):
    def test_exact_schedule_and_unique_jobs(self):
        plan=schedule()
        self.assertEqual(len(plan),23)
        self.assertEqual([x['job_id'] for x in plan],list(range(1,24)))
        for op in ('gate','up','down'):
            self.assertEqual(Counter(x['T'] for x in plan if x['weight']=='l00_'+op),{1:3,8:3,3:1})

    def test_hand_fp32_regression_not_tolerance_relaxation(self):
        xq,sx=scalar.quant_activations([[127.,127.]])
        w,sw=scalar.pack_weights([[1.,0.],[0.,2.]])
        y,_=scalar.execute(2,2,1,w,sw,xq,sx)
        self.assertNotEqual(y[:2],[127.,254.])  # preserved freeze_01 minimal cause
        w,sw=scalar.pack_weights([[7.,0.],[0.,14.]])
        y,_=scalar.execute(2,2,1,w,sw,xq,sx)
        self.assertEqual(y[:2],[889.,1778.])
        self.assertEqual(y[2:],[0.]*30)

    def test_tail_and_dual_scale_sensitivity(self):
        w,sw=scalar.pack_weights([[1.]*128+[8.] for _ in range(33)])
        xq,sx=scalar.quant_activations([[1.]*129]*3)
        y,sums=scalar.execute(33,129,3,w,sw,xq,sx)
        self.assertEqual(len(y),3*64)
        self.assertEqual(len(sums),3*64*2)
        for t in range(3): self.assertEqual(y[t*64+33:(t+1)*64],[0.]*31)
        modified=bytearray(sw);modified[32*4:33*4]=modified[:4]
        wrong,_=scalar.execute(33,129,3,w,bytes(modified),xq,sx)
        self.assertNotEqual(wrong,y)


class InheritedLock(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a11-pc-lock-')
        self.path=Path(self.temp.name)/'test.lock'
        self.fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_CLOEXEC,0o600)
        self.pid=os.getpid()
        self.ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]

    def tearDown(self):
        os.close(self.fd);self.temp.cleanup()

    def child(self,fd=None,path=None,pid=None,ticks=None):
        fd=self.fd if fd is None else fd
        return subprocess.run([str(LOCK_BINARY),str(fd),str(self.pid if pid is None else pid),
                               self.ticks if ticks is None else ticks,str(self.path if path is None else path)],
                              pass_fds=(fd,),capture_output=True,text=True,timeout=5)

    def test_inherited_close_keeps_parent_exclusive(self):
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.assertEqual(self.child().returncode,0)
        other=os.open(self.path,os.O_RDWR)
        try:
            with self.assertRaises(BlockingIOError): fcntl.flock(other,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally: os.close(other)

    def test_unlocked_fd_rejected_without_taking_lock(self):
        self.assertEqual(self.child().returncode,3)
        # The child did not claim an unowned lock in its validation path.
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)

    def test_same_inode_different_open_description_rejected(self):
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        other=os.open(self.path,os.O_RDWR)
        try: self.assertEqual(self.child(fd=other).returncode,3)
        finally: os.close(other)

    def test_pid_and_starttime_rejected(self):
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.assertEqual(self.child(pid=self.pid+1).returncode,3)
        self.assertEqual(self.child(ticks='0').returncode,3)

    def test_symlink_rejected(self):
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        link=self.path.with_name('alias');link.symlink_to(self.path)
        self.assertEqual(self.child(path=link).returncode,3)

    def test_writable_lock_rejected(self):
        fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        self.path.chmod(0o666)
        self.assertEqual(self.child().returncode,3)


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--lock-binary',required=True,type=Path)
    args,remaining=ap.parse_known_args();LOCK_BINARY=args.lock_binary
    unittest.main(argv=['test_preparation',*remaining],verbosity=2)
