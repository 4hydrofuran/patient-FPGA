"""Exercise the real logger/gate wiring, not a mocked emit or checkpoint."""
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import isolated_idle_trial as trial
from minimal_gate import MinimalGate


class CheckpointTests(unittest.TestCase):
    def test_snapshot_boot_field_matches_and_conflict_is_refused(self):
        obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        obj.boot, obj.package = 'pc-fixture-boot', 'pc-fixture-window'
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as log:
            obj.log = log
            with patch('sys.stdout', new=io.StringIO()):
                obj.emit('READBACK', boot_id=obj.boot, phase='health_guard')
                obj.emit('WORKER_REAPED', monotonic_ns=123, exit_code=0)
                with self.assertRaisesRegex(RuntimeError, 'identity field differs'):
                    obj.emit('READBACK', boot_id='wrong-boot')
            log.seek(0)
            rows = [json.loads(row) for row in log]
            self.assertEqual(rows[0]['boot_id'], obj.boot)
            self.assertEqual(rows[1]['observation_monotonic_ns'], 123)

    def test_actual_checkpoint_and_emit_do_not_duplicate_gate_fields(self):
        obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        obj.boot = 'pc-fixture-boot'
        obj.package = 'pc-fixture-window'
        obj.kernel_gate = MinimalGate()
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as log:
            obj.log = log
            with patch.object(trial.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout=b'<6>[1.0] fixture informational message\n', stderr=b'')), \
                    patch.object(Path, 'read_text', return_value=obj.boot), \
                    patch('sys.stdout', new=io.StringIO()):
                obj.kernel_checkpoint('initial_baseline_continuity')
                obj.kernel_checkpoint('second_read')
            log.seek(0)
            rows = [json.loads(row) for row in log]
            self.assertEqual(len(rows), 2)
            self.assertTrue(all(row['allowed'] and row['action'] == 'none' for row in rows))
            self.assertFalse(obj.kernel_gate.blocked)

    def test_real_checkpoint_latches_new_error(self):
        obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        obj.boot, obj.package, obj.kernel_gate = 'pc-fixture-boot', 'pc-fixture-window', MinimalGate()
        with tempfile.TemporaryFile(mode='w+', encoding='utf-8') as log:
            obj.log = log
            with patch.object(trial.subprocess, 'run', return_value=SimpleNamespace(
                    returncode=0, stdout=b'<3>[1.0] refcount failure\n', stderr=b'')), \
                    patch.object(Path, 'read_text', return_value=obj.boot), \
                    patch('sys.stdout', new=io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, 'kernel gate refused'):
                    obj.kernel_checkpoint('initial_baseline_continuity')
            self.assertTrue(obj.kernel_gate.blocked)


if __name__ == '__main__':
    unittest.main()
