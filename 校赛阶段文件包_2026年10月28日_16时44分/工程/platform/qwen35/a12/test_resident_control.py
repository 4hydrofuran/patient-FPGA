"""Real private atomic writer boundaries; no model/PL completion claims."""
import os
import time
import unittest
from resident_evidence import OUT, read
from resident_manager import ResidentPage
from plm_page import Page
from plm_manager import ticks


class ControlTests(unittest.TestCase):
    def page(self, old=False):
        b=read(OUT/('BUILD-v1.json' if old else 'BUILD-v2.json'))
        p=(Page if old else ResidentPage)(b['writer_library'],b['writer_sha256'])
        p.health(time.monotonic_ns());p.bind(os.getpid(),ticks(os.getpid()),'1'*64);p.load_end()
        self.addCleanup(p.close)
        return p

    def test_nine_then_tenth_rejected(self):
        p=self.page()
        for i in range(9):
            p.health(time.monotonic_ns());p.begin(0,1,format(i+1,'064x'));p.end(0)
            self.assertEqual(p.snapshot()['request_serial'],i+1)
        with self.assertRaises(RuntimeError):p.begin(0,1,'a'*64)
        self.assertEqual(p.snapshot()['claims'],0)
        self.assertEqual(p.snapshot()['generation'],10)

    def test_old_three_not_silently_extended(self):
        p=self.page(old=True)
        for i in range(3):p.begin(0,1,format(i+1,'064x'));p.end(0)
        with self.assertRaises(RuntimeError):p.begin(0,1,'a'*64)

    def test_original_5000_budget(self):
        p=self.page()
        with self.assertRaises(RuntimeError):p.begin(0,5001,'a'*64)
        p.begin(0,5000,'b'*64);p.end(0)
        self.assertEqual(p.snapshot()['claims'],0)

    def test_active_and_revoked_refuse(self):
        p=self.page();p.begin(0,1,'a'*64)
        with self.assertRaises(RuntimeError):p.begin(0,1,'b'*64)
        p.end(0);p.revoke()
        with self.assertRaises(RuntimeError):p.begin(0,1,'c'*64)


if __name__=='__main__':unittest.main()
