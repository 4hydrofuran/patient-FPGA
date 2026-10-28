"""Meaningful corrupt-evidence counterexamples against independent audit."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import resident_audit as target
from resident_evidence import OUT,read,save
from request_journal_verified import canonical,digest,ZERO


def rewrite_chain(path, mutate):
    rows=[json.loads(q) for q in path.read_text().splitlines()]
    mutate(rows);previous=ZERO
    for i,row in enumerate(rows):
        row.pop('sha256');row.update(serial=i+1,previous_sha256=previous);row['sha256']=digest(row);previous=row['sha256']
    path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))


class AuditCounterexamples(unittest.TestCase):
    def fixture(self):
        d=tempfile.TemporaryDirectory(prefix='resident-audit-negative-');self.addCleanup(d.cleanup)
        root=Path(d.name);shutil.copytree(OUT/'flow04',root/'window')
        shutil.copyfile(OUT/'SERVICE_BUILD-v3.json',root/'SERVICE_BUILD-v3.json')
        old=target.OUT;target.OUT=root;self.addCleanup(setattr,target,'OUT',old)
        return root/'window'

    def test_missing_native_receipt(self):
        p=self.fixture();(p/'state/model_1-receipt.json').unlink()
        with self.assertRaises((RuntimeError,FileNotFoundError)):target.audit('window')

    def test_forged_native_result(self):
        p=self.fixture();path=p/'native.stdout';rows=[json.loads(q) for q in path.read_text().splitlines()]
        next(q for q in rows if q['type']=='result')['text']='错误。'
        path.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
        with self.assertRaises(RuntimeError):target.audit('window')

    def test_rehashed_app_plan(self):
        p=self.fixture();rewrite_chain(p/'application-state/control.jsonl',lambda rows:next(q for q in rows if q['event']=='INPUT_BEGIN').__setitem__('plan_sha256','0'*64))
        with self.assertRaises(RuntimeError):target.audit('window')

    def test_rehashed_wrong_frozen_identity(self):
        p=self.fixture();rewrite_chain(p/'state/control.jsonl',lambda rows:[q.__setitem__('frozen_request_sha256','0'*64) for q in rows if q['event']=='BEGIN' and q['request']['op']=='generate'])
        # Chain-consistent mutation still disagrees with native END receipt or
        # original input/plan reconstruction; hashes alone do not grant trust.
        with self.assertRaises(RuntimeError):target.audit('window')

    def test_final_fence_before_end(self):
        p=self.fixture();path=next(q for q in sorted(p.glob('EVENT_*.json')) if read(q)['op']=='submit' and read(q)['value']['type']=='validated_answer')
        row=read(path);row['value']['delivery_fence']['requested_ns']=0;path.write_bytes(canonical(row)+b'\n')
        with self.assertRaises(RuntimeError):target.audit('window')

    def test_missing_host_ack(self):
        p=self.fixture();rewrite_chain(p/'application-state/control.jsonl',lambda rows:rows.pop(next(i for i,q in enumerate(rows) if q['event']=='HOST_TEXT_ACK')))
        with self.assertRaises(RuntimeError):target.audit('window')


if __name__=='__main__':unittest.main()
