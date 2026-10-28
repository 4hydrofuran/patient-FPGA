"""Actual adapter+CPU math, local credit races and two distinct DSO mappings."""
import io
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from microbatch_evidence import ROOT,OUT,read,save
from microbatch_page import BatchPage,COUNT,REVOKED

BUILD=None;EVIDENCE=None


class Actor:
    def __init__(self,root,*,budget=8,count=3,damage=None,page=None,expires_s=None):
        self.root=root;self.own_page=page is None
        self.page=page or BatchPage(BUILD['library'],expires_ns=None if expires_s is None else time.monotonic_ns()+int(expires_s*1e9))
        self.page.health(time.monotonic_ns())
        if self.own_page:self.page.begin(0,budget,'a'*64)
        self.count=count;self.damage=damage;self.grants=[];self.rows=[];self.errors=[]
        self.stop=threading.Event();self.a,self.b=socket.socketpair();self.messages=queue.Queue()
        cfg=read(Path(BUILD['workspace'])/'adapter-config.json');self.context=cfg['context_sha256']
        file=root/'probe.json';save(file,dict(adapter=BUILD['library'],adapter_config=str(Path(BUILD['workspace'])/'adapter-config.json'),
            cpu=BUILD['existing_cpu_library'],cpu_config=cfg['cpu_config']))
        env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','SP_TT10','LD_'))}
        env.update(SP_A12_CONTROL_FD=str(self.b.fileno()),SP_A12_BATCH_PAGE_FD=str(self.page.fd))
        self.stderr=(root/'stderr.txt').open('x')
        self.process=subprocess.Popen([sys.executable,'-B',str(ROOT/'platform/qwen35/a12/microbatch_abi_probe.py'),str(file)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=self.stderr,text=True,env=env,
            pass_fds=(self.b.fileno(),self.page.fd))
        self.b.close();self.server=threading.Thread(target=self.permissions,daemon=True);self.server.start()
        self.reader=threading.Thread(target=self.receive,daemon=True);self.reader.start()
        self.heartbeat=threading.Thread(target=self.observe,daemon=True);self.heartbeat.start()
    def observe(self):
        while not self.stop.wait(.01):self.page.health(time.monotonic_ns())
    def receive(self):
        for line in self.process.stdout:
            r=json.loads(line);self.rows.append(r);self.messages.put(r)
        self.messages.put(None)
    def permissions(self):
        try:
            with self.a.makefile('r') as stream:
                for line in stream:
                    q=json.loads(line);assert q['pid']==self.process.pid and q['manager_epoch']==self.page.epoch
                    assert q['context_sha256']==self.context
                    if q['phase']=='router_open' and self.own_page:self.page.bind_worker(q['pid'],q['process_start_ticks'])
                    r={k:q[k] for k in ('sequence','worker_epoch','manager_epoch','context_sha256')};r['allow']=True
                    if q['phase']=='batch':
                        count=min(self.count,8-q['job']+1) # tests never grant beyond the explicit page budget below
                        limit=self.budget
                        count=min(count,limit-q['job']+1)
                        r.update(first_job=q['job'],last_job=q['job']+count-1,count=count,T=q['T'],
                            request_generation=q['request_generation'],request_sha256=q['request_sha256'],
                            deadline_monotonic_ns=self.page.deadline)
                        self.grants.append(q)
                        if self.damage:
                            key,value=self.damage;r[key]=value
                    self.a.sendall((json.dumps(r)+'\n').encode())
        except BaseException as exc:self.errors.append(str(exc))
    def ready(self,budget):self.budget=budget;return self.get()
    def get(self):
        r=self.messages.get(timeout=5)
        if r is None:raise RuntimeError('PC probe EOF')
        return r
    def call(self,**q):self.send(**q);return self.get()
    def send(self,**q):self.process.stdin.write(json.dumps(q)+'\n');self.process.stdin.flush()
    def close(self):
        self.stop.set();self.heartbeat.join(1)
        if self.process.poll() is None:
            self.send(op='exit');self.process.stdin.close();self.process.wait(timeout=5)
        self.a.close();self.server.join(1);self.reader.join(1);self.stderr.close();self.process.stdout.close()
        if self.own_page:self.page.close()


class NativeBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='a12-batch-abi-');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.actors=[]
    def actor(self,**kw):
        directory=self.root/str(len(self.actors));directory.mkdir()
        a=Actor(directory,**kw);self.actors.append(a);self.addCleanup(a.close)
        self.assertEqual(a.ready(kw.get('budget',8))['type'],'ready');return a
    def result(self,a,**q):return a.call(op='run',**q)
    def save(self,name,value):
        if EVIDENCE:save(EVIDENCE/(name+'.json'),value)

    def test_real_T1_T8_match_original_CPU(self):
        a=self.actor(count=1);rows=[]
        for job,t in enumerate((1,8),1):
            r=self.result(a,job=job,T=t);rows.append(r);self.assertEqual(r['rc'],0);self.assertTrue(r['bit_exact'])
            self.assertEqual(r['report']['pc_batch']['shared_claims'],job)
        self.save('CPU_T1_T8',rows)

    def test_cached_credit_revoke_cannot_forward_or_refund(self):
        a=self.actor();self.assertEqual(self.result(a,job=1)['rc'],0)
        previous=a.page.revoke();self.assertEqual(previous&COUNT,1)
        r=self.result(a,job=2);self.assertNotEqual(r['rc'],0);self.assertTrue(r['unchanged'])
        self.assertEqual((r['report']['pc_started_calls'],r['report']['cpu_run_count'],a.page.gate()&COUNT),(1,1,1))
        self.assertEqual(len(a.grants),1);self.assertFalse(r['report']['pc_output_consumable']);self.save('REVOKE',r)

    def test_two_DSO_contexts_cannot_spend_budget_twice(self):
        a=self.actor(budget=1);self.assertEqual(self.result(a,job=1)['rc'],0);self.assertEqual(a.call(op='clone')['type'],'cloned')
        r=self.result(a,job=2,context='b');self.assertNotEqual(r['rc'],0)
        self.assertEqual(r['report']['pc_started_calls'],0);self.assertEqual(r['report']['pc_batch']['shared_claims'],1)
        self.save('TWO_DISTINCT_DSOS',r)

    def test_unknown_inflight_blocks_second_DSO_even_with_unused_budget(self):
        a=self.actor();self.result(a,job=1,bad_size=True);a.call(op='clone')
        r=self.result(a,job=2,context='b');self.assertNotEqual(r['rc'],0)
        self.assertEqual(r['report']['pc_started_calls'],0);self.assertEqual(a.page.gate()&COUNT,1)
        self.assertTrue(r['report']['pc_batch']['inflight_or_unknown'])
        self.assertNotEqual(a.page.end_fn(a.page.handle,1),0)
        self.save('UNKNOWN_INFLIGHT_SECOND_DSO',r)

    def test_end_destroys_unused_grant_and_new_generation_requires_new_grant(self):
        a=self.actor(budget=4,count=3);self.result(a,job=1);self.assertEqual(len(a.grants),1)
        a.page.end(1);a.page.begin(1,1,'b'*64);a.budget=2
        r=self.result(a,job=2);self.assertEqual(r['rc'],0);self.assertTrue(r['bit_exact'])
        self.assertEqual(len(a.grants),2);self.assertEqual(a.grants[-1]['request_generation'],2)
        self.assertEqual(a.grants[-1]['request_sha256'],'b'*64);self.save('NEW_GENERATION',r)

    def test_cached_grant_wrong_T_rejects_before_CPU(self):
        a=self.actor();self.result(a,job=1);r=self.result(a,job=2,T=8)
        self.assertNotEqual(r['rc'],0);self.assertEqual(r['report']['pc_started_calls'],1)

    def test_bad_output_extent_spends_one_claim_and_poisons_no_retry(self):
        a=self.actor();r=self.result(a,job=1,bad_size=True)
        self.assertNotEqual(r['rc'],0);self.assertTrue(r['unchanged']);self.assertEqual(a.page.gate()&COUNT,1)
        self.assertEqual(r['report']['pc_started_calls'],1);self.assertEqual(r['report']['pc_verified_completions'],0)
        self.assertTrue(r['report']['pc_batch']['inflight_or_unknown'])
        self.assertNotEqual(a.page.end_fn(a.page.handle,1),0,'unknown call cannot be treated as a completed request')
        again=self.result(a,job=2);self.assertNotEqual(again['rc'],0);self.assertEqual(a.page.gate()&COUNT,1)

    def test_disconnected_manager_stops_cached_credit(self):
        a=self.actor();self.result(a,job=1);a.a.shutdown(socket.SHUT_WR)
        r=self.result(a,job=2);self.assertNotEqual(r['rc'],0);self.assertEqual(r['report']['pc_started_calls'],1)
        self.save('MANAGER_DISCONNECT',r)

    def test_stalled_heartbeat_rejects_cached_credit(self):
        a=self.actor();self.result(a,job=1);a.stop.set();a.heartbeat.join(1);time.sleep(.28)
        r=self.result(a,job=2);self.assertNotEqual(r['rc'],0);self.assertEqual(r['report']['pc_started_calls'],1)

    def test_foreign_old_reply_ranges_and_T_never_start(self):
        for damage in [('worker_epoch','0'*32),('manager_epoch','0'*32),('context_sha256','0'*64),
                ('request_generation',9),('request_sha256','0'*64),('count',73),('first_job',2),('T',8),('deadline_monotonic_ns',0)]:
            with self.subTest(damage=damage):
                a=self.actor(damage=damage);r=self.result(a,job=1)
                self.assertNotEqual(r['rc'],0);self.assertEqual(r['report']['pc_started_calls'],0)
                self.assertEqual(a.page.gate()&COUNT,0)

    def test_reinitialize_page_and_overflow_budget_are_refused(self):
        a=self.actor(budget=1);self.result(a,job=1);a.page.end(1)
        handle=a.page.writer_open_fn(a.page.fd,0,1,time.monotonic_ns()+1_000_000_000,250_000_000)
        self.assertFalse(handle);self.assertEqual(a.page.gate()&COUNT,1)
        self.assertNotEqual(a.page.begin_fn(a.page.handle,1,2**64-1,b'c'*64),0)
        self.assertEqual(a.page.gate()&COUNT,1)

    def test_restarted_actual_process_cannot_use_old_shared_page_credit(self):
        a=self.actor();self.result(a,job=1);a.send(op='exit');a.process.wait(timeout=5)
        b=self.actor(page=a.page)
        # Fixture server deliberately acknowledges startup of the new process.
        # The backend itself must still refuse the old page's worker identity.
        r=self.result(b,job=2);self.assertNotEqual(r['rc'],0)
        self.assertEqual(r['report']['pc_started_calls'],0);self.assertEqual(a.page.gate()&COUNT,1)
        self.save('ACTUAL_WORKER_RESTART',r)

    def test_revoke_start_race_reconciles_atomic_order(self):
        rows=[]
        for index in range(12):
            a=self.actor();self.result(a,job=1);a.send(op='run',job=2)
            if index%2:time.sleep(.0001)
            before=a.page.revoke();r=a.get();claimed=before&COUNT
            self.assertIn(claimed,(1,2))
            if claimed==1:self.assertEqual(r['report']['pc_started_calls'],1);self.assertNotEqual(r['rc'],0)
            self.assertEqual(a.page.gate()&COUNT,claimed)
            rows.append(dict(revoke_observed_claims=claimed,result=r))
        self.save('REVOKE_START_RACES',rows)

    def test_expired_deadline_refuses_cached_credit(self):
        a=self.actor(expires_s=1);self.assertEqual(self.result(a,job=1)['rc'],0);time.sleep(1.03)
        r=self.result(a,job=2);self.assertNotEqual(r['rc'],0);self.assertEqual(r['report']['pc_started_calls'],1)

    def test_page_constructor_failure_does_not_leak_FD(self):
        from unittest import mock
        before=len(list(Path('/proc/self/fd').iterdir()))
        with mock.patch('microbatch_page.c.CDLL',side_effect=OSError('fixture loader failure')):
            with self.assertRaises(OSError):BatchPage('absent')
        self.assertEqual(before,len(list(Path('/proc/self/fd').iterdir())))

    def test_actual_manager_exit_stops_cached_native_credit(self):
        directory=self.root/'manager-exit'
        result=subprocess.run([sys.executable,str(ROOT/'platform/qwen35/a12/microbatch_manager_exit_probe.py'),
            str(OUT/('BUILD-v'+str(BUILD['revision'])+'.json')),str(directory)],capture_output=True,text=True,timeout=8)
        self.assertEqual(result.returncode,0,result.stderr)
        path=directory/'parent-exit-result.json';until=time.monotonic()+5
        while not path.exists() and time.monotonic()<until:time.sleep(.01)
        r=read(path);self.assertNotEqual(r['observed_parent'],r['old_manager']);self.assertNotEqual(r['rc'],0)
        self.assertEqual((r['report']['pc_started_calls'],r['report']['cpu_run_count']),(1,1))
        self.assertEqual(r['report']['pc_batch']['shared_claims'],1)
        import select
        try:
            fd=os.pidfd_open(r['probe_pid']);poll=select.poll();poll.register(fd,select.POLLIN)
            try:self.assertTrue(poll.poll(5000),'PC child did not cooperatively exit')
            finally:os.close(fd)
        except ProcessLookupError:pass
        self.save('ACTUAL_MANAGER_EXIT',r)


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--tag',required=True);args=p.parse_args()
    BUILD=read(args.build);EVIDENCE=OUT/args.tag;EVIDENCE.mkdir(exist_ok=False);stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (EVIDENCE/'unittest.txt').write_text(stream.getvalue())
    save(EVIDENCE/'RESULT.json',dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
        errors=len(result.errors),failures=len(result.failures),domain='REAL_PC_ADAPTER_AND_CPU_ARRAYS',BOARD='NOT_TESTED',PL_calls=0))
    print(stream.getvalue());raise SystemExit(0 if result.wasSuccessful() else 1)
