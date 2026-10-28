"""Real native transcript checks plus semantic corruption with a valid new chain."""
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from microbatch_evidence import OUT,read,save
from microbatch_audit import audit,SCHEMA
from request_journal_verified import canonical,digest,ZERO

BUILD=OUT/'BUILD-v5-reviewed.json'


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=read(BUILD);cls.source=Path(cls.build['workspace'])/'run-batch72-v5-01/worker'
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='a12-batch-audit-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
    def rechain(self,directory,rows):
        previous=ZERO
        for i,r in enumerate(rows,1):
            r['record_serial']=i;r['previous_record_sha256']=previous
            r['record_sha256']=digest({k:v for k,v in r.items() if k not in ('monotonic_ns','record_sha256')})
            previous=r['record_sha256']
            if r['event']=='REQUEST_END_PC_CANDIDATE':
                p=directory/('COMMIT-'+r['request_id']+'.json');receipt=read(p);receipt['end_record_sha256']=previous
                p.write_bytes(canonical(receipt)+b'\n')
        p=directory/'NORMAL_CLOSE.json';receipt=read(p);receipt['last_record_sha256']=previous;p.write_bytes(canonical(receipt)+b'\n')
        (directory/'events.jsonl').write_bytes(b''.join(canonical(r)+b'\n' for r in rows))

    def test_true_1_and_72_native_transcripts_and_counters(self):
        reports=[]
        for cap in (1,72):
            worker=Path(self.build['workspace'])/('run-batch'+str(cap)+'-v5-01/worker')
            result=audit(worker,BUILD);self.assertEqual(result['status'],'COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT',result)
            self.assertEqual(result['actual_cpu_calls'],2880);self.assertEqual(result['batch_grants'],2880//cap)
            self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed']);reports.append(result)
        save(OUT/'TEST_INDEPENDENT_NATIVE_AUDITS-v5.json',reports)

    def test_rehashed_semantic_grant_corruption_is_still_refused(self):
        cases=('range','T','worker','generation','request','deadline','process_start')
        reasons=[]
        for name in cases:
            with self.subTest(case=name):
                directory=self.root/name;shutil.copytree(self.source,directory)
                rows=[json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
                r=next(r for r in rows if r['event']=='MICROBATCH_GRANT');q=r['request'];g=r['grant']
                if name=='range':g['last_job']+=72;g['count']+=72
                if name=='T':q['T']=g['T']=1
                if name=='worker':q['worker_epoch']=g['worker_epoch']='0'*32
                if name=='generation':q['request_generation']=g['request_generation']=2
                if name=='request':q['request_sha256']=g['request_sha256']='0'*64
                if name=='deadline':g['deadline_monotonic_ns']=0
                if name=='process_start':q['process_start_ticks']+=1
                self.rechain(directory,rows);result=audit(directory,BUILD)
                self.assertEqual(result['status'],'REJECTED_OR_INCOMPLETE_RETAIN_OWNER',result)
                self.assertNotIn('SHA differs',result['reason']);self.assertFalse(result['release_allowed']);reasons.append(result)
        save(OUT/'REHASHED_GRANT_CORRUPTION_REFUSALS-v5.json',reasons)

    def test_native_stdout_receipt_and_inventory_damage_refused(self):
        for name in ('native_count','receipt_missing','extra_file','journal_torn'):
            with self.subTest(case=name):
                directory=self.root/name;shutil.copytree(self.source,directory)
                if name=='native_count':
                    p=directory/'stdout.jsonl';rows=[json.loads(s) for s in p.read_text().splitlines()]
                    next(r for r in rows if r.get('type')=='result')['bridge']['a12_route']['pc_batch']['shared_claims']+=1
                    p.write_bytes(b''.join(canonical(r)+b'\n' for r in rows))
                if name=='receipt_missing':(directory/'COMMIT-app_hit.json').unlink()
                if name=='extra_file':(directory/'unlisted.txt').write_text('not allowed')
                if name=='journal_torn':
                    p=directory/'events.jsonl';p.write_bytes(p.read_bytes()[:-7])
                result=audit(directory,BUILD);self.assertEqual(result['status'],'REJECTED_OR_INCOMPLETE_RETAIN_OWNER',result)
                self.assertFalse(result['release_allowed']);self.assertFalse(result['replay_allowed'])


if __name__=='__main__':
    target=OUT/'audit-tests-02';target.mkdir(exist_ok=False);stream=io.StringIO()
    r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    (target/'unittest.txt').write_text(stream.getvalue());save(target/'RESULT.json',dict(status='PASS' if r.wasSuccessful() else 'FAIL',
        tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),BOARD='NOT_TESTED',PL_calls=0,new_model_runs=0))
    print(stream.getvalue());raise SystemExit(0 if r.wasSuccessful() else 1)
