"""Pure PC recovery tests; never execute the historical XRT source."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import recover_peer_resource_ledger as ledger


class ResourceRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[3]
        cls.package = root / 'A10_refcount_交付包_20261023/A10_refcount_handoff_20261023'
        cls.native = root / 'evidence/board_platform/A10_20261023_peer_intake/received_board_files/single_xrt_call.py'
        cls.raw = (cls.package / ledger.LOG).read_bytes()
        cls.actual = ledger.decode((cls.package / ledger.ACTUAL).read_bytes())
        cls.audit = ledger.decode((cls.package / ledger.AUDIT).read_bytes())

    def test_verified_real_records_recovered_without_new_board_claim(self):
        result = ledger.recover(self.package, self.native)
        self.assertEqual(result['small_bo']['explicit_requested_live_peak_bytes'], 49344)
        self.assertEqual(result['small_bo']['addresses'], [1146814464, 1146847232, 1146880000])
        self.assertEqual([r['smaps_kib']['Pss'] for r in result['process_account']], [25470, 29704, 29776])
        self.assertEqual(result['historical_teardown'], 'FAILED')
        self.assertEqual(result['A10'], 'NOT_PASSED')
        self.assertFalse(result['new_board_access'])
        self.assertEqual(result['new_compute_submissions'], 0)
        self.assertIsNone(result['timing']['pure_sync_in_us'])
        self.assertIsNone(result['small_bo']['physical_allocation_peak_bytes'])
        self.assertIsNone(result['process_account'][0]['observed_current_bo_bytes'])
        self.assertFalse(result['process_account'][-1]['release_proven'])

    def test_original_line_numbers_and_sha_are_verifiable(self):
        result = ledger.recover(self.package, self.native)
        lines = self.raw.splitlines()
        for entry in result['process_account']:
            row = ledger.decode(lines[entry['source_line'] - 1])
            self.assertEqual(row['event'], 'MEMORY_OBSERVATION')
            self.assertEqual(row['phase'], entry['phase'])
        self.assertEqual(result['provenance']['sources'][ledger.LOG]['sha256'], ledger.sha(self.raw))

    def test_missing_counter_is_null_not_zero_and_bad_units_rejected(self):
        self.assertEqual(ledger.counters('Pss: 10 kB\n', ('Pss', 'Rss')), dict(Pss=10, Rss=None))
        for raw in ('Pss: 10 MB', 'Pss: -1 kB', 'Pss: 10 kB\nPss: 11 kB'):
            with self.assertRaises(ValueError):
                ledger.counters(raw, ('Pss',))

    def test_duplicate_or_mixed_boot_evidence_refused(self):
        rows = [ledger.decode(line) for line in self.raw.splitlines()]
        bo = next(row for row in rows if row.get('event') == 'BO_CREATED')
        for extra in (bo, dict(event='READBACK', boot_id='different-boot')):
            with self.assertRaises(ValueError):
                ledger.extract(self.raw + b'\n' + json.dumps(extra).encode() + b'\n', self.actual, self.audit)

    def test_output_mismatch_or_false_recovery_success_refused(self):
        changed = copy.deepcopy(self.actual)
        changed['sync_in_us'] = 0
        with self.assertRaisesRegex(ValueError, 'output record differs'):
            ledger.extract(self.raw, changed, self.audit)
        audit = dict(self.audit, overall_A10='PASS')
        with self.assertRaisesRegex(ValueError, 'failure must be retained'):
            ledger.extract(self.raw, self.actual, audit)

    def test_changed_manifest_or_native_source_refused_without_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'MANIFEST.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'unreviewed handoff'):
                ledger.recover(root, self.native)
            bogus = root / 'never_execute.py'
            bogus.write_text('raise AssertionError("must never execute captured source")\n')
            with self.assertRaisesRegex(ValueError, 'timing source changed'):
                ledger.recover(self.package, bogus)
            bogus.write_bytes(self.native.read_bytes())
            (root / 'run_refcount_step5.py').write_text('# changed logger\n')
            with self.assertRaisesRegex(ValueError, 'logger source changed'):
                ledger.recover(self.package, bogus)

    def test_json_duplicates_nonfinite_and_output_overwrite_refused(self):
        for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
            with self.assertRaises(ValueError):
                ledger.decode(raw)
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'ledger.json'
            ledger.write_new(target, dict(original=True))
            with self.assertRaises(FileExistsError):
                ledger.write_new(target, dict(original=False))
            self.assertEqual(ledger.decode(target.read_bytes()), dict(original=True))


if __name__ == '__main__':
    unittest.main()
