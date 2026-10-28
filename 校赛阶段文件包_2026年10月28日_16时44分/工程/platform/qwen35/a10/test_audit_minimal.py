import json
from pathlib import Path
import tempfile
import unittest
from audit_minimal import audit, sha


class AuditTests(unittest.TestCase):
    root = Path(__file__).resolve().parents[3]
    evidence = root / 'evidence/board_platform/A10_20261018_intake/minimal-board-20261021-v1'

    def test_real_failure_not_pass(self):
        r = audit(self.evidence)
        self.assertEqual(r['A10'], 'NOT_PASSED_KERNEL_OOPS')
        self.assertEqual(r['compute_runs'], 0)
        self.assertFalse(r['final_default_restored'])
        self.assertIsNone(r['sync_us'])
        self.assertTrue(all(c['exit_code'] == 0 for c in r['command_results']))

    def test_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for p in self.evidence.iterdir():
                if p.name in ('idle-result.jsonl', 'continuation.jsonl', 'download_hashes.json'):
                    (d / p.name).write_bytes(p.read_bytes())
            with (d / 'continuation.jsonl').open('a') as f:
                f.write('{}\n')
            with self.assertRaises(ValueError):
                audit(d)

    def test_zero_exit_not_sufficient(self):
        # Actual dfx management command returned zero while kernel oopsed.
        r = audit(self.evidence)
        self.assertEqual(r['command_results'][-1]['exit_code'], 0)
        self.assertIn('kernel BUG', r['kernel_oops'])


if __name__ == '__main__':
    unittest.main()
