"""Meaningful failure/continuity/concurrency tests for the real candidate module."""
import errno
from pathlib import Path
import tempfile
import threading
import unittest
from health_opt import PersistentKmsg, HealthBlocked, StableTemperatures, HealthSchedule

def record(seq, text='ok', flag='-', stamp=1234567):
    return f'6,{seq},{stamp},{flag};{text}\n'.encode()

def reader(records):
    source=iter(records)
    def read():
        value=next(source,BlockingIOError(errno.EAGAIN,'empty'))
        if isinstance(value,BaseException):raise value
        return value
    return PersistentKmsg(read=read)

class HealthTests(unittest.TestCase):
    def test_exact_and_incremental(self):
        r=reader([record(4),BlockingIOError(errno.EAGAIN,'empty'),record(5,'next')])
        self.assertEqual(r.drain(),'<6>[    1.234567] ok\n')
        self.assertEqual(r.drain(),'<6>[    1.234567] ok\n<6>[    1.234567] next\n')
        self.assertEqual(r.records,2)
    def test_kmsg_escape_is_decoded_once(self):
        r=reader([record(1,r'a\x09b\x0ac\xc2\xa9\x5cx09')])
        self.assertEqual(r.drain(),'<6>[    1.234567] a\tb\n                  c©\\x09\n')
    def test_pinned_non_kernel_priority(self):
        r=reader([b'30,1,1234567,-;userspace\n'])
        self.assertEqual(r.drain(),'<7>[    1.234567] userspace\n')
    def test_loss_replay_and_fragments(self):
        for bad in (record(3),record(1),record(2,flag='c'),b'bad\n',b'6,2,3,-;partial',b'6,2,3,-;x\nnot-metadata\n'):
            with self.subTest(bad=bad):
                r=reader([record(1),bad])
                with self.assertRaises((ValueError,HealthBlocked)):r.drain()
                with self.assertRaises(HealthBlocked):r.drain()
    def test_io_overrun_and_latched(self):
        for exc in (OSError(errno.EPIPE,'overrun'),OSError(errno.EACCES,'permission'),OSError(errno.EIO,'failure')):
            r=reader([exc])
            with self.assertRaises(OSError):r.drain()
            with self.assertRaises(HealthBlocked):r.drain()
    def test_snapshot_mismatch(self):
        r=reader([record(1)])
        with self.assertRaises(HealthBlocked):r.assert_full_snapshot('different\n')
        with self.assertRaises(HealthBlocked):r.drain()
    def test_empty_and_closed(self):
        with self.assertRaises(HealthBlocked):reader([]).drain()
        r=reader([record(1)]);r.close()
        with self.assertRaises(HealthBlocked):r.drain()
    def test_idle_never_replaces_fresh(self):
        now=[1000000000];s=HealthSchedule(clock=lambda:now[0]);calls=[]
        def observe():calls.append(len(calls));return {'checked':len(calls)}
        self.assertEqual(s.fresh(observe),{'checked':1})
        self.assertFalse(s.idle(observe,lambda:None))
        self.assertEqual(s.fresh(observe),{'checked':2})
        now[0]+=250000001;self.assertTrue(s.idle(observe,lambda:None))
        self.assertEqual(len(calls),3)
    def test_idle_does_not_block_active_permission(self):
        s=HealthSchedule();entered=threading.Event();release=threading.Event()
        def observe():entered.set();self.assertTrue(release.wait(2));return {}
        t=threading.Thread(target=lambda:s.fresh(observe));t.start()
        self.assertTrue(entered.wait(2));self.assertFalse(s.idle(lambda:self.fail(),lambda:self.fail()))
        release.set();t.join(2);self.assertFalse(t.is_alive())
    def test_failed_observation_latches(self):
        s=HealthSchedule()
        with self.assertRaises(ValueError):s.fresh(lambda:(_ for _ in ()).throw(ValueError('bad')))
        with self.assertRaises(HealthBlocked):s.fresh(lambda:{})
        with self.assertRaises(HealthBlocked):s.idle(lambda:{},lambda:None)
    def test_sensor_value_missing_replacement_topology(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'hwmon0';p.mkdir();v=p/'temp1_input';v.write_text('30000')
            s=StableTemperatures(root);self.assertEqual(s.read(),[30000])
            v.write_text('55000')
            with self.assertRaises(HealthBlocked):s.read()
            v.write_text('30000');(p/'temp2_input').write_text('31000')
            with self.assertRaises(HealthBlocked):s.verify_topology()
            v.rename(root/'old_sensor')
            v.write_text('30000')
            with self.assertRaises(HealthBlocked):s.read()
            v.unlink()
            with self.assertRaises(FileNotFoundError):s.read()

if __name__=='__main__':unittest.main(verbosity=2)
