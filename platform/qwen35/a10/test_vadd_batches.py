"""Synthetic PC fixtures ONLY; never publish these records as board evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from audit_vadd_batches import audit, validate_rows, LENGTHS, INIT, BYTES

EXPECTED = dict(machine_id_sha256='a'*64, host_binary_sha256='b'*64, xclbin_sha256='c'*64, boot_ids=['fixture-boot'])


def fixture(start=0, count=20):
    receipt = dict(schema='A10_REAL_BATCH_RECEIPT_V1', domain='BOARD_REAL_XRT',
                   process_exit_code=0, boot_id='fixture-boot', approval_sha256='d'*64,
                   **{k: EXPECTED[k] for k in ('machine_id_sha256', 'host_binary_sha256', 'xclbin_sha256')})
    rows = [dict(event='BEGIN', domain='BOARD_REAL_XRT', whole_A10_pass=False,
                 boot_id='fixture-boot', xclbin_sha256='c'*64, approval_sha256='d'*64,
                 start_job=start, requested_jobs=count, temperature_mC=[32000])]
    for step in INIT:
        rows.extend([dict(event='INIT_STEP_BEGIN', step=step), dict(event='INIT_STEP_COMPLETE', step=step, elapsed_ms=1)])
    rows.append(dict(event='BO_CREATED', groups=[3,3,3], addresses=[65536,131072,196608], bytes_each=BYTES, is_maximum_budget_probe=False))
    for job in range(start, start+count):
        rows.extend([dict(event='PREPARED_NOT_SUBMITTED', job=job, n=LENGTHS[job%20]),
                     dict(event='VERIFIED', job=job, n=LENGTHS[job%20], **{'pass': True},
                          sync_in_us=3, submit_poll_us=5, sync_out_us=2, temperature_mC=[32000])])
    rows.append(dict(event='BATCH_COMPLETE', verified=count, A10='NOT_PASSED_BY_A_BATCH'))
    return rows, receipt


class BatchTests(unittest.TestCase):
    def test_valid_fixture_and_line_numbers(self):
        rows, receipt = fixture()
        result = validate_rows(rows, receipt, EXPECTED)
        self.assertEqual(len(result),20)
        self.assertEqual(result[0]['source_line'],18)
        self.assertEqual({r['n'] for r in result}, set(LENGTHS))

    def test_failed_or_pc_receipt(self):
        for key, value in [('domain','PC'),('process_exit_code',None),('process_exit_code',1),
                           ('host_binary_sha256','e'*64),('boot_id','other'),('machine_id_sha256','e'*64)]:
            rows, receipt = fixture()
            receipt[key] = value
            with self.assertRaises(ValueError): validate_rows(rows, receipt, EXPECTED)

    def test_missing_init_or_terminal(self):
        for index in [1,2,-1]:
            rows, receipt=fixture()
            del rows[index]
            with self.assertRaises(ValueError): validate_rows(rows, receipt, EXPECTED)

    def test_numeric_shape_timing_and_temperature(self):
        for key, value in [('n',4095),('n',True),('n',1.0),('pass',False),('sync_in_us',None),('submit_poll_us',float('nan')),
                           ('sync_out_us',-1),('temperature_mC',[60000]),('job',False)]:
            rows, receipt=fixture()
            rows[17][key]=value
            with self.assertRaises(ValueError): validate_rows(rows, receipt, EXPECTED)

    def test_bo_ranges_and_groups(self):
        for key,value in [('addresses',[0,0,0]),('addresses',[2**31,1,2]),('groups',[0,0,0]),('bytes_each',1)]:
            rows, receipt=fixture()
            rows[15][key]=value
            with self.assertRaises(ValueError): validate_rows(rows, receipt, EXPECTED)

    def test_poison_cannot_be_sealed_as_pass(self):
        rows, receipt=fixture()
        rows.insert(-1,dict(event='POISONED_RETAIN_PROCESS_AND_BOS'))
        with self.assertRaises(ValueError): validate_rows(rows, receipt, EXPECTED)

    def test_length_mapping_matches_production(self):
        text=(Path(__file__).resolve().parents[2]/'a1/vadd/cases.hpp').read_text(encoding='utf-8')
        self.assertIn('LENGTHS{{'+','.join(map(str,LENGTHS))+'}}',text)

    def test_empty_real_index_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'index.json'
            path.write_text(json.dumps(dict(schema='A10_REAL_BATCH_INDEX_V1',expected=EXPECTED,batches=[])),encoding='utf-8')
            result=audit(path)
            self.assertEqual(result['accepted_unique_jobs'],0)
            self.assertFalse(result['comparison_count_criteria_met'])
            self.assertIsNone(result['measured_compute_time_s'])

    def test_counting_duplicate_hash_and_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); entries=[]
            def write(name,obj,lines=False):
                data=('\n'.join(json.dumps(r) for r in obj)+'\n' if lines else json.dumps(obj)).encode()
                (root/name).write_bytes(data)
                return dict(path=name,sha256=hashlib.sha256(data).hexdigest())
            for start in range(0,1000,20):
                rows, receipt=fixture(start)
                log=write(str(start)+'.jsonl',rows,True)
                receipt['log_sha256']=log['sha256']
                entries.append(dict(log=log,receipt=write(str(start)+'.json',receipt)))
            path=root/'index.json'
            def run(items):
                path.write_text(json.dumps(dict(schema='A10_REAL_BATCH_INDEX_V1',expected=EXPECTED,batches=items)),encoding='utf-8')
                return audit(path)
            good=run(entries)
            self.assertEqual(good['accepted_unique_jobs'],1000)
            self.assertTrue(good['comparison_count_criteria_met'])
            self.assertNotEqual(good['A10'],'PASS')
            partial=run(entries[:-1])
            self.assertEqual(partial['accepted_unique_jobs'],980)
            self.assertFalse(partial['comparison_count_criteria_met'])
            duplicate=run(entries+[entries[0]])
            self.assertEqual(duplicate['accepted_unique_jobs'],1000)
            self.assertFalse(duplicate['comparison_count_criteria_met'])
            self.assertEqual(len(duplicate['rejected']),1)
            bad=copy.deepcopy(entries[:1]);bad[0]['log']['sha256']='f'*64
            self.assertEqual(run(bad)['accepted_unique_jobs'],0)
            bad[0]['log']['path']='../outside'
            self.assertEqual(run(bad)['accepted_unique_jobs'],0)


if __name__=='__main__': unittest.main(verbosity=2)
