"""PC Linux checks for manager ownership; no board identity is fabricated as PASS."""
import fcntl
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import window
from common import sha


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'active').mkdir();(self.root/'active/lease.json').write_text('{}')
        self.paths=(self.root/'deployment.lock',self.root/'device.lock');self.fds=[]
        for path in self.paths:
            fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.fds.append(fd)
        self.owner=window.Window.__new__(window.Window)
        self.owner.locks=self.fds;self.owner.lease_hash=sha(self.root/'active/lease.json')
        self.owner.boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.owner.expires=123
        self.patches=[patch.object(window,'CENTRAL',self.root),patch.object(window,'LOCKS',self.paths)]
        for p in self.patches:p.start()
    def tearDown(self):
        for fd in self.fds:os.close(fd)
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def test_same_manager_dual_lock_profile(self):
        self.owner.owner_check();fields=self.owner.profile_fields()
        self.assertEqual(fields['manager_pid'],os.getpid())
        self.assertEqual(fields['inherited_device_lock_fd'],self.fds[1])
    def test_changed_lease_refused(self):
        (self.root/'active/lease.json').write_text('{"changed":true}')
        with self.assertRaises(RuntimeError):self.owner.owner_check()
    def test_lost_lock_refused(self):
        fcntl.flock(self.fds[0],fcntl.LOCK_UN)
        with self.assertRaises(RuntimeError):self.owner.owner_check()
    def test_pending_worker_cannot_release_lease(self):
        class Pending:closed=False
        with self.assertRaises(RuntimeError):self.owner.finish(Pending())
        self.assertTrue((self.root/'active/lease.json').exists())


if __name__=='__main__':unittest.main()
