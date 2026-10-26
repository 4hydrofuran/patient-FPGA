"""Recorded real native responses: controller rejects and independent log audit."""
import argparse
import copy
import io
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest import mock
import sys

from native_cpu_build import OUT,read,save
from native_request_journal import NativeRequestController,canonical,digest,RequestJournalBlocked
import native_request_audit as reader
from resource_probe_policy import ProbeBlocked

EVIDENCE=None
BUILD=OUT/'BUILD-v2.json'


class RecordedWorker:
    real=False;max_runs=5000;max_loads=72;loads=72
    def __init__(self):
        self.runs=0;self._request_lock=threading.RLock();self._request_failed=False
        self.quarantined=False;self.delivery_cancelled=False;self._io_fault=None;self.sent=[];self.commits=[]
    def _attach(self,value):self.gate=value
    def _isolate(self,reason):self._request_failed=True;self.quarantined=True;self._io_fault=reason
    def _begin_verified(self,token,wire,budget,meta):self.meta=meta;self.budget=budget
    def _finish_verified(self,token,result,summary):self.commits.append((result,summary))
    def send(self,request):self.sent.append(copy.deepcopy(request))
    def owner_check(self):pass
    def health(self):pass
    def record(self,**row):pass


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory=OUT/'run-request-v2-01';cls.ready=read(cls.directory/'ready.json')
        cls.native_run=read(cls.directory/'RESULT.json');cls.results={n:read(cls.directory/n/'result.json')
            for n in ('app_R0','warm_prefix','app_hit')}
        messages=[json.loads(line) for line in (Path(cls.native_run['workspace'])/'worker/stdout.jsonl').read_text().splitlines()]
        cls.tokens={n:[m for m in messages if m.get('id')==n and m['type']=='token'] for n in cls.results}
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a12-native-gate-');self.root=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def gate(self):
        w=RecordedWorker();g=NativeRequestController(w,copy.deepcopy(self.ready),self.native_run['native_identity']);return w,g
    def start(self,w,g,name='app_R0'):
        request=g.arm(name);wire=g.wire(request);g.send(wire)
        for event in self.tokens[name]:g.accept_token(copy.deepcopy(event))
        r=copy.deepcopy(self.results[name]);w.runs=r['bridge']['a12_route']['pc_verified_completions'];return r

    def test_real_recorded_three_request_sequence_and_warm_wire(self):
        w,g=self.gate()
        for name in self.results:
            r=self.start(w,g,name);g.finish(r)
            if name=='warm_prefix':self.assertEqual(len(w.sent[-1]['tokens']),70)
            else:self.assertNotIn('tokens',w.sent[-1])
        self.assertEqual(len(w.commits),3);self.assertEqual(w.runs,2880)

    def test_real_recorded_metadata_mutations_never_commit(self):
        changes={
            'id':lambda r:r.update(id='foreign'),
            'fixture':lambda r:r.update(fixture_domain='PC_CONTROL_FIXTURE'),
            'state':lambda r:r.update(state_cleared_before_response=False),
            'token_list':lambda r:r.update(output_tokens='bad'),
            'token_mismatch':lambda r:r['output_tokens'].__setitem__(0,1),
            'GPU_bool':lambda r:r.update(gpu_layers=False),
            'count':lambda r:r['bridge']['a12_route'].update(pc_verified_completions=1),
            'count_bool':lambda r:r['bridge']['a12_route'].update(pc_attempted_calls=True),
            'poison':lambda r:r['bridge']['a12_route'].update(pc_poisoned=True),
            'CPU_fallback':lambda r:r['bridge'].update(cpu_run_count=72),
            'fake_hardware':lambda r:r['bridge']['a12_route'].update(kernel_build_id=0xB3030002),
            'residency':lambda r:r['bridge']['a12_route'].update(owned_weight_bytes=0),
            'cache':lambda r:r['prefix_cache_request'].update(hit=True),
            'eos':lambda r:r.update(eos=False),
            'content':lambda r:r.update(text='最近服药了。'),
            'job':lambda r:r['bridge']['a12_route'].update(pc_last_job=0),
        }
        for name,change in changes.items():
            with self.subTest(name=name):
                w,g=self.gate();r=self.start(w,g);change(r)
                with self.assertRaises((RequestJournalBlocked,ProbeBlocked)):g.finish(r)
                self.assertTrue(w.quarantined);self.assertEqual(w.commits,[])

    def test_token_stream_wrong_index_foreign_id_and_negative_token(self):
        for changes in ({'index':1},{'id':'foreign'},{'token':-1},{'index':False}):
            w,g=self.gate();req=g.arm('app_R0');g.send(g.wire(req));event=copy.deepcopy(self.tokens['app_R0'][0]);event.update(changes)
            with self.assertRaises(RequestJournalBlocked):g.accept_token(event)
            self.assertTrue(w.quarantined);self.assertEqual(w.commits,[])

    def test_old_warm_encoding_without_tokens_is_refused(self):
        w,g=self.gate();g.finish(self.start(w,g));request=g.arm('warm_prefix');wire=g.wire(request);wire.pop('tokens')
        with self.assertRaises(RequestJournalBlocked):g.send(wire)
        self.assertTrue(w.quarantined);self.assertEqual(len(w.commits),1)

    def test_first_error_stays_latched_and_wrong_order_does_not_arm(self):
        w,g=self.gate()
        with self.assertRaises(RequestJournalBlocked):g.arm('warm_prefix')
        with self.assertRaises(RequestJournalBlocked):g.arm('app_R0')
        self.assertEqual(w.sent,[])

    def test_last_fresh_owner_or_health_refusal_prevents_commit(self):
        for name in ('owner_check','health'):
            w,g=self.gate();r=self.start(w,g)
            def refused():raise RuntimeError('recorded-native fresh boundary failure')
            setattr(w,name,refused)
            with self.assertRaises(RuntimeError):g.finish(r)
            self.assertTrue(w.quarantined);self.assertEqual(w.commits,[])

    def test_true_native_stdout_and_journal_are_independently_reconciled(self):
        rows=[]
        for name in ('request-v2-01','strict-v2-01'):
            d=read(OUT/('run-'+name)/'RESULT.json');r=reader.audit(Path(d['workspace'])/'worker',BUILD)
            self.assertEqual(r['status'],'COMPLETE_ACTUAL_PC_NATIVE_TRANSCRIPT',r)
            self.assertEqual(r['actual_cpu_calls'],2880);self.assertFalse(r['release_allowed']);self.assertFalse(r['replay_allowed']);rows.append(r)
        if EVIDENCE is not None:save(EVIDENCE/'INDEPENDENT_NATIVE_AUDITS.json',rows)

    def test_corruption_of_stdout_commits_and_journal_is_rejected(self):
        source=Path(self.native_run['workspace'])/'worker'
        for damage in ('native_count','native_token','native_extra','journal_torn','journal_sha','receipt_missing','close_release'):
            with self.subTest(damage=damage):
                target=self.root/damage;shutil.copytree(source,target)
                if damage.startswith('native_'):
                    path=target/'stdout.jsonl';rows=[json.loads(s) for s in path.read_text().splitlines()]
                    if damage=='native_count':next(r for r in rows if r.get('id')=='app_R0' and r['type']=='result')['bridge']['a12_route']['cpu_run_count']+=1
                    if damage=='native_token':next(r for r in rows if r['type']=='token')['token']=1
                    if damage=='native_extra':rows.append(rows[-1])
                    path.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
                if damage=='journal_torn':
                    path=target/'events.jsonl';path.write_bytes(path.read_bytes()[:-9])
                if damage=='journal_sha':
                    path=target/'events.jsonl';path.write_bytes(path.read_bytes().replace(b'REQUEST_BEGIN_PC_CANDIDATE',b'REQUEST_BOGUS_PC_CANDIDATE',1))
                if damage=='receipt_missing':(target/'COMMIT-app_hit.json').unlink()
                if damage=='close_release':
                    path=target/'NORMAL_CLOSE.json';r=read(path);r['release_allowed']=True;path.write_bytes(canonical(r))
                result=reader.audit(target,BUILD)
                self.assertEqual(result['status'],'REJECTED_OR_INCOMPLETE_RETAIN_OWNER',result)
                self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])


def main():
    global EVIDENCE
    p=argparse.ArgumentParser();p.add_argument('--evidence',required=True,type=Path);a=p.parse_args()
    a.evidence.mkdir(parents=True,exist_ok=False);EVIDENCE=a.evidence;stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (EVIDENCE/'unittest.txt').write_text(stream.getvalue())
    save(EVIDENCE/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',tests=r.testsRun,
        errors=len(r.errors),failures=len(r.failures),domain='RECORDED_REAL_PC_NATIVE_REJECTION_AND_AUDIT',
        new_model_runs=0,PL_calls=0,BOARD='NOT_TESTED'))
    print(stream.getvalue());return 0 if r.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
