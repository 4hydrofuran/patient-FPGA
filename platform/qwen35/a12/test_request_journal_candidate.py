"""No-board journal prototype: real socket/child and frozen permission loop."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
import request_journal_candidate as candidate_module
from unittest import mock

from request_journal_candidate import RequestJournalCandidate, RequestJournalBlocked

ROOT = Path(__file__).resolve().parents[3]
FROZEN = ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2/platform/qwen35/a12'
EVIDENCE = None
sys.path.insert(0, str(FROZEN))
import cpu01b_observer as ob
ob.ENABLED = False
from cpu01b_supervisor import OwnedWorker
from cpu02_support import DurableJournal


class Candidate(RequestJournalCandidate, OwnedWorker):
    pass


CHILD = r'''
import json, os, signal, socket, sys
signal.signal(signal.SIGUSR1, lambda *_: None)
s=socket.socket(fileno=int(os.environ['SP_A12_CONTROL_FD']));f=s.makefile('r')
lanes={'router':0,'backend':0};job=0
def permit(phase,job):
    lane='router' if phase.startswith('router_') else 'backend';lanes[lane]+=1
    req=dict(pid=os.getpid(),sequence=lanes[lane],phase=phase,job=job)
    s.sendall((json.dumps(req)+'\n').encode());line=f.readline()
    if not line:return False
    reply=json.loads(line)
    assert reply['sequence']==req['sequence']
    return reply['allow'] is True
assert permit('router_open',0) and permit('device_open',0) and permit('weight_load',1)
print(json.dumps({'ready':True}),flush=True)
for line in sys.stdin:
    r=json.loads(line)
    if r['op']=='shutdown':
        permit('router_close',0);break
    n=0
    for _ in range(r['count']):
        job+=1
        if r.get('replay'):lanes['backend']-=1
        if not permit('submit',job):break
        n+=1
    print(json.dumps({'fixture_permits':n,'not_hardware_completions':True}),flush=True)
f.close();s.close()
'''


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a12-journal-pc-')
        self.root = Path(self.temp.name)
        self.workers = []
        self.checks = {'owner':0,'health':0}

    def tearDown(self):
        for worker in self.workers:
            # CPU fixture only: normal stdin exit; never signal/kill/reset or claim release.
            if worker.process.poll() is None:
                worker.process.stdin.write('{"op":"shutdown"}\n');worker.process.stdin.flush()
                worker.process.wait(timeout=5)
            worker.permission_thread.join(2);worker.reader_thread.join(2)
            for item in (worker.stderr, worker.process.stdin, worker.process.stdout, worker.manager_sock):
                item.close()
            if hasattr(worker,'_journal'):worker._journal.close()
        self.temp.cleanup()

    def owner(self):self.checks['owner'] += 1
    def health(self):
        self.checks['health'] += 1
        return dict(MemAvailable=1114112,CmaFree=98304)

    def worker(self, cls=Candidate, **kw):
        worker=cls([sys.executable,'-B','-c',CHILD],directory=self.root/str(len(self.workers)),
                   env=os.environ,health=self.health,owner_check=self.owner,max_runs=5000,
                   max_loads=72,expires=time.monotonic()+60,real=False,**kw)
        self.workers.append(worker)
        self.assertEqual(worker.get(5),{'ready':True})
        return worker

    def run_submits(self, worker, count):
        worker.send(dict(op='fixture',count=count));return worker.get(10)

    def finish(self, worker, request_id='R0'):
        worker.end_request(request_id,cumulative_completions=worker.runs,pending=0,
                           state_cleared=True,outcome='VALIDATED')

    def test_strict_baseline_and_candidate_keep_all_fresh_checks(self):
        results=[]
        for cls in (OwnedWorker,Candidate):
            self.checks={'owner':0,'health':0};worker=self.worker(cls)
            if cls is Candidate:worker.begin_request('R0',1000)
            self.assertEqual(self.run_submits(worker,1000)['fixture_permits'],1000)
            if cls is Candidate:
                self.assertEqual(len(worker._recent_submits),64)
                self.assertLess(len(worker.records),10)
                self.finish(worker)
            self.assertTrue(worker.close())
            rows=[json.loads(x) for x in (worker.directory/'events.jsonl').read_text().splitlines()]
            results.append(dict(checks=dict(self.checks),rows=rows))
        self.assertEqual(results[0]['checks'],results[1]['checks'])
        self.assertEqual(results[0]['checks'],dict(owner=1005,health=1004))
        strict,candidate=(r['rows'] for r in results)
        self.assertEqual(sum(r.get('request',{}).get('phase')=='submit' for r in strict),1000)
        self.assertEqual(sum(r.get('request',{}).get('phase')=='submit' for r in candidate),0)
        end=next(r for r in candidate if r['event']=='REQUEST_END_PC_CANDIDATE')
        self.assertEqual((end['permit_count'],end['overwritten_submits']),(1000,936))
        self.assertEqual([r for r in candidate if r['event']=='PERMISSION'],
                         [r for r in candidate if r.get('request',{}).get('phase') in
                          ('router_open','device_open','weight_load','router_close')])
        if EVIDENCE is not None:
            for worker,name in zip(self.workers,('strict','candidate')):
                shutil.copyfile(worker.directory/'events.jsonl',EVIDENCE/(name+'-events.jsonl'))
            metrics=dict(domain='PC_SOCKET_CONTROL_FIXTURE_NO_PL',simulated_submit_permits=1000,
                         fresh_checks=results[0]['checks'],strict_durable_records=len(strict),
                         candidate_durable_records=len(candidate),ring_capacity=64,
                         overwritten_submit_details=end['overwritten_submits'],
                         BOARD='NOT_TESTED',PL_calls=0,measured_board_saving_s=None)
            (EVIDENCE/'STRUCTURAL_COMPARISON.json').write_text(json.dumps(metrics,indent=2)+'\n')

    def test_three_distinct_request_boundaries(self):
        w=self.worker()
        for name,n in [('R0',3),('warm',2),('hit',1)]:
            w.begin_request(name,n);self.assertEqual(self.run_submits(w,n)['fixture_permits'],n)
            self.finish(w,name)
        self.assertTrue(w.close());self.assertEqual(w.runs,6)

    def test_no_active_request_never_replies_allow(self):
        w=self.worker();self.assertEqual(self.run_submits(w,1)['fixture_permits'],0)
        self.assertEqual(w.runs,0);self.assertTrue(w.quarantined);self.assertFalse(w.close())

    def test_budget_overrun_never_replies_extra_allow(self):
        w=self.worker();w.begin_request('R0',2)
        self.assertEqual(self.run_submits(w,3)['fixture_permits'],2)
        self.assertEqual(w.runs,2);self.assertFalse(w.close())

    def test_begin_persistence_failure_latches_before_any_submit(self):
        w=self.worker()
        with mock.patch.object(DurableJournal,'append',side_effect=OSError('injected BEGIN fsync failure')):
            with self.assertRaises(OSError):w.begin_request('R0',1)
        self.assertIsNone(w._active_request);self.assertEqual(w.runs,0)
        with self.assertRaises(RequestJournalBlocked):w.begin_request('new',1)
        self.assertFalse(w.close())

    def test_end_persistence_failure_retains_incomplete_begin(self):
        w=self.worker();w.begin_request('R0',1);self.run_submits(w,1)
        with mock.patch.object(DurableJournal,'append',side_effect=OSError('injected END fsync failure')):
            with self.assertRaises(OSError):self.finish(w)
        self.assertIsNotNone(w._active_request);self.assertFalse(w.close())
        rows=(w.directory/'events.jsonl').read_text()
        self.assertIn('REQUEST_BEGIN_PC_CANDIDATE',rows);self.assertNotIn('REQUEST_END_PC_CANDIDATE',rows)

    def test_invalid_completion_assertions_latch_and_block_close(self):
        for field,value in [('cumulative_completions',0),('cumulative_completions',True),
                            ('pending',1),('pending',False),('state_cleared',False),('outcome','FAILED')]:
            with self.subTest(field=field,value=value):
                w=self.worker();w.begin_request('R0',1);self.run_submits(w,1)
                args=dict(cumulative_completions=1,pending=0,state_cleared=True,outcome='VALIDATED')
                args[field]=value
                with self.assertRaises(RequestJournalBlocked):w.end_request('R0',**args)
                self.assertFalse(w.close())

    def test_reused_id_or_nested_begin_refused(self):
        for nested in (False,True):
            w=self.worker();w.begin_request('R0',1);self.run_submits(w,1)
            if not nested:self.finish(w)
            with self.assertRaises(RequestJournalBlocked):w.begin_request('R0',1)
            self.assertFalse(w.close())

    def test_cancellation_keeps_durable_fault_and_owner(self):
        w=self.worker();w.begin_request('R0',2);self.run_submits(w,1);w.cancel('PC fixture')
        with self.assertRaises(RequestJournalBlocked):self.finish(w)
        self.assertFalse(w.close())
        self.assertIn('CANCEL_PENDING_NO_KILL',(w.directory/'events.jsonl').read_text())

    def test_real_worker_activation_refused_before_spawn(self):
        with mock.patch('subprocess.Popen') as spawn:
            with self.assertRaises(RequestJournalBlocked):Candidate(real=True)
            spawn.assert_not_called()

    def test_arm_activation_refused_before_spawn(self):
        with mock.patch.object(candidate_module.platform,'machine',return_value='aarch64'):
            with mock.patch('subprocess.Popen') as spawn:
                with self.assertRaises(RequestJournalBlocked):Candidate(real=False)
                spawn.assert_not_called()

    def test_original_stale_sequence_check_still_refuses(self):
        w=self.worker();w.begin_request('R0',1)
        w.send(dict(op='fixture',count=1,replay=True))
        self.assertEqual(w.get(5)['fixture_permits'],0)
        self.assertEqual(w.runs,0);self.assertTrue(w.quarantined);self.assertFalse(w.close())

    def test_original_fresh_health_failure_still_refuses(self):
        w=self.worker();w.begin_request('R0',1)
        def failed():raise RuntimeError('PC health failure')
        w.health=failed
        self.assertEqual(self.run_submits(w,1)['fixture_permits'],0)
        self.assertEqual(w.runs,0);self.assertFalse(w.close())

    def test_original_fresh_owner_failure_still_refuses(self):
        w=self.worker();w.begin_request('R0',1)
        def failed():raise RuntimeError('PC owner failure')
        w.owner_check=failed
        self.assertEqual(self.run_submits(w,1)['fixture_permits'],0)
        self.assertEqual(w.runs,0);self.assertFalse(w.close())


def main():
    global EVIDENCE
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path);args=p.parse_args()
    args.evidence.mkdir(parents=True,exist_ok=False);EVIDENCE=args.evidence;output=io.StringIO()
    result=unittest.TextTestRunner(stream=output,verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    row=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun,
             failures=len(result.failures),errors=len(result.errors),
             domain='PC_CONTROL_SOCKET_FIXTURES_NOT_MODEL_OR_HARDWARE',PL_calls=0,
             BOARD='NOT_TESTED',production_enabled=False,latency_saving_s=None)
    (args.evidence/'unittest.txt').write_text(output.getvalue())
    (args.evidence/'RESULT.json').write_text(json.dumps(row,indent=2)+'\n')
    print(output.getvalue());print(json.dumps(row));return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
