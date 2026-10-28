"""Linux no-board regressions: real sockets/fsync, faults, fresh locks and logs."""
import ast
import errno
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1'
SOURCE=OUT/'source'
sys.path.insert(0,str(SOURCE))
sys.path.insert(1,str(ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/integrated/bundle-v1/control/support'))
import cpu01b_observer as ob
from cpu01b_supervisor import OwnedWorker
from cpu01b_health import PersistentKmsg, HealthBlocked, HealthSchedule
from cpu01b_kernel_gate import MinimalGate
from cpu01b_healthrecord import compact_kernel_record
from cpu02_support import DurableJournal, SnapshotCache, owned_lock_fds


def existing_tests():
    text=(ROOT/'platform/qwen35/a12/test_cpu01b.py').read_text(encoding='utf-8')
    text=text.replace("SOURCE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1/source'","SOURCE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-02-v1/source'")
    text=text.replace("{'request.parse','request.order','owner.total','health.total','record.json_encode','record.write','record.flush','record.fsync','reply.encode','reply.send'}","{'request.parse','request.order','owner.total','health.total','record.json_encode','record.write','record.fsync','reply.encode','reply.send'}")
    text=text.replace("with patch('pathlib.Path.open',return_value=BadStream()):","with patch('cpu02_support.os.write',side_effect=OSError('write failed')):")
    text=text.replace("self.worker.manager_sock.close();self.temp.cleanup()","self.worker.manager_sock.close()\n        if hasattr(self.worker,'_journal'):self.worker._journal.close()\n        self.temp.cleanup()")
    # Old and new records must use distinct new directories, then parse identically.
    text=text.replace("        OwnedWorker.record(self.worker,event='BYTE_TEST',observation={'fresh':True})", "        oldpath=self.worker.directory\n        self.worker.directory=self.path/'candidate';self.worker.directory.mkdir()\n        OwnedWorker.record(self.worker,event='BYTE_TEST',observation={'fresh':True})")
    text=text.replace("rows=[json.loads(line) for line in (self.path/'events.jsonl').read_text().splitlines()]", "rows=[json.loads((folder/'events.jsonl').read_text()) for folder in (oldpath,self.worker.directory)]")
    namespace={'__file__':str(ROOT/'platform/qwen35/a12/test_cpu01b.py'),'__name__':'cpu02_existing_protocol_tests'}
    exec(compile(text,'cpu02_adapted_prior_protocol_tests','exec'),namespace)
    (OUT/'adapted_prior_protocol_tests.py').write_text(text,encoding='utf-8')
    return namespace['Tests']


class Additional(unittest.TestCase):
    def test_worker_eof_retains_owner_and_never_yields_result(self):
        import queue
        w=OwnedWorker.__new__(OwnedWorker);w.messages=queue.Queue();w.messages.put(None)
        w.quarantined=False;w.delivery_cancelled=False
        with self.assertRaisesRegex(RuntimeError,'unexpected worker EOF'):w.get(.1)
        self.assertTrue(w.quarantined)
    def test_manager_exit_closes_permission_channel_without_grant(self):
        manager,worker=socket.socketpair()
        pid=os.fork()
        if pid==0:
            worker.close();manager.close();os._exit(0)
        manager.close();os.waitpid(pid,0);worker.settimeout(.5)
        self.assertEqual(worker.recv(1024),b'');worker.close()
    def test_immutable_cache_content_identity_and_bound(self):
        c=SnapshotCache();a='one\n';b='two\n'
        x=c.get(a);self.assertIs(c.get(a),x)
        other=('x'+a)[1:];self.assertEqual(c.get(other).sha256,x.sha256)
        self.assertEqual(c.get(b).sha256,hashlib.sha256(b.encode()).hexdigest())
        self.assertEqual(len(c.entries),2)
        with self.assertRaises(TypeError):c.get(bytearray(b'x'))
    def test_fresh_kmsg_read_even_on_cache_hit(self):
        queue=[b'6,1,1234567,-;ok\n',BlockingIOError(errno.EAGAIN,'empty'),BlockingIOError(errno.EAGAIN,'empty'),OSError(errno.EPIPE,'lost')];calls=[]
        def read():calls.append(1);item=queue.pop(0);return item if isinstance(item,bytes) else (_ for _ in ()).throw(item)
        reader=PersistentKmsg(read=read);first=reader.drain();self.assertIs(reader.drain(),first)
        with self.assertRaises(OSError):reader.drain()
        self.assertEqual(len(calls),4);self.assertTrue(reader.blocked)
    def test_real_lock_fd_fresh_release_replacement_and_close(self):
        with tempfile.TemporaryDirectory() as d:
            paths=[Path(d)/str(i) for i in (1,2)];fds=[]
            for p in paths:
                fd=os.open(p,os.O_CREAT|os.O_RDWR,0o600);fds.append(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            self.assertTrue(owned_lock_fds(paths,fds,os.getpid()))
            fcntl.flock(fds[1],fcntl.LOCK_UN);self.assertFalse(owned_lock_fds(paths,fds,os.getpid()))
            fcntl.flock(fds[1],fcntl.LOCK_EX);paths[0].rename(Path(d)/'old');paths[0].touch()
            self.assertFalse(owned_lock_fds(paths,fds,os.getpid()))
            for fd in fds:os.close(fd)
            with self.assertRaises(OSError):owned_lock_fds(paths,fds,os.getpid())
    def test_gate_exact_old_new_results_and_failures(self):
        old_path=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/manager-source/cpu01b_kernel_gate.py'
        spec=importlib.util.spec_from_file_location('cpu02_old_gate',old_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        base='<6>[    1.000000] baseline\n'
        scenarios=[('boot',base,None,'none'),('boot',base,None,'none'),('boot',base+'<6>[    2.000000] next\n',None,'none'),('boot',base+'<3>[    2.000000] DMA error\n',None,'none')]
        a,b=module.MinimalGate(),MinimalGate()
        for boot,raw,pin,action in scenarios:self.assertEqual(a.observe_action(boot,raw,pin,action),b.observe_action(boot,raw,pin,action))
        for bad in ('cut\n',base[:-1],base+'<4>[    2.000000] warning\n'):
            a,b=module.MinimalGate(),MinimalGate();a.observe_action('boot',base,None,'none');b.observe_action('boot',base,None,'none')
            self.assertEqual(a.observe_action('boot',bad,None,'none'),b.observe_action('boot',bad,None,'none'))
        a,b=module.MinimalGate(),MinimalGate();a.observe_action('boot',base,None,'none');b.observe_action('boot',base,None,'none')
        self.assertEqual(a.observe_action('newboot',base,None,'none'),b.observe_action('newboot',base,None,'none'))
    def test_kernel_archive_read_loss_and_collision_remain_failures(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw='<6>[    1.000000] ok\n'
            row=compact_kernel_record(root,dict(raw_log=raw));p=root/row['raw_log_file']
            self.assertEqual(p.read_bytes(),raw.encode());compact_kernel_record(root,dict(raw_log=raw))
            p.write_bytes(b'tampered')
            with self.assertRaises(RuntimeError):compact_kernel_record(root,dict(raw_log=raw))
            with patch('pathlib.Path.read_bytes',side_effect=OSError('unreadable archive')):
                with self.assertRaises(OSError):compact_kernel_record(root,dict(raw_log=raw))
    def test_journal_one_fsync_per_append_and_directory_once(self):
        with tempfile.TemporaryDirectory() as d:
            journal=DurableJournal(Path(d)/'events');calls=[];original=os.fsync
            def sync(fd):calls.append(fd);return original(fd)
            with patch('cpu02_support.os.fsync',side_effect=sync):
                journal.append(b'{"n":1}\n');journal.append(b'{"n":2}\n')
            self.assertEqual(len(calls),3);self.assertEqual(calls[0],calls[2]);journal.close()
            self.assertEqual([json.loads(s) for s in (Path(d)/'events').read_text().splitlines()],[{'n':1},{'n':2}])
    def test_journal_missing_truncated_replaced_and_symlink_latch(self):
        for change in ('missing','truncate','replace','symlink'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
                p=Path(d)/'events';j=DurableJournal(p);j.append(b'one\n')
                if change=='truncate':p.write_bytes(b'')
                else:
                    p.unlink()
                    if change=='replace':p.write_bytes(b'one\n')
                    if change=='symlink':p.symlink_to(Path(d)/'other')
                with self.assertRaises(OSError):j.append(b'two\n')
                self.assertTrue(j.blocked)
                with self.assertRaises(OSError):j.append(b'three\n')
                j.close()
    def test_journal_partial_write_and_no_progress(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'good';j=DurableJournal(p);original=os.write
            with patch('cpu02_support.os.write',side_effect=lambda fd,data:original(fd,data[:2])):j.append(b'abcdef\n')
            self.assertEqual(p.read_bytes(),b'abcdef\n');j.close()
            j=DurableJournal(Path(d)/'bad')
            with patch('cpu02_support.os.write',return_value=0):
                with self.assertRaises(OSError):j.append(b'x')
            self.assertTrue(j.blocked);j.close()
    def test_permission_waits_for_fsync(self):
        with tempfile.TemporaryDirectory() as d:
            w=OwnedWorker.__new__(OwnedWorker);w.manager_sock,child=socket.socketpair();child.settimeout(.1)
            w.process=types.SimpleNamespace(pid=1234);w.directory=Path(d);w._lock=threading.Lock();w.records=[]
            w.sequence=w.runs=w.loads=0;w.quarantined=w.delivery_cancelled=False;w.max_runs=w.max_loads=2;w.expires=time.monotonic()+30
            w.owner_check=lambda:None;w.health=lambda:dict(fresh=True)
            entered=threading.Event();release=threading.Event();original=os.fsync
            def sync(fd):entered.set();self.assertTrue(release.wait(2));original(fd)
            with patch('cpu02_support.os.fsync',side_effect=sync):
                t=threading.Thread(target=w._permissions);t.start();child.sendall(b'{"phase":"router_open","sequence":1,"job":0,"pid":1234}\n')
                self.assertTrue(entered.wait(1))
                with self.assertRaises(socket.timeout):child.recv(1024)
                release.set();child.settimeout(1);self.assertTrue(json.loads(child.recv(1024))['allow'])
                child.shutdown(socket.SHUT_WR);t.join(2);self.assertFalse(t.is_alive())
            w._journal.close();child.close();w.manager_sock.close()


def main():
    prior=existing_tests()
    health=(ROOT/'platform/qwen35/a12/test_health_opt.py').read_text(encoding='utf-8').replace('from health_opt import','from cpu01b_health import')
    namespace={'__file__':str(ROOT/'platform/qwen35/a12/test_health_opt.py'),'__name__':'cpu02_prior_health'}
    exec(compile(health,'cpu02_prior_health','exec'),namespace)
    suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(prior),unittest.defaultTestLoader.loadTestsFromTestCase(Additional),unittest.defaultTestLoader.loadTestsFromTestCase(namespace['HealthTests'])])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    data=dict(status='PASS_PC_CPU02_PROTOCOL_AND_FAILURES' if result.wasSuccessful() else 'FAIL_PC_CPU02',tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),BOARD='NOT_TESTED')
    with (OUT/'PC.json').open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2);stream.write('\n')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
