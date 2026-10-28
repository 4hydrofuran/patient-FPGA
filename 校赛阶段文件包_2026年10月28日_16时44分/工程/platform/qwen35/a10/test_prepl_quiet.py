"""Bounded read-only settling, never a hardware retry or release waiver."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import isolated_idle_trial as trial
from test_xrt_worker_boundary import clear_snapshot


class QuietTests(unittest.TestCase):
    def setUp(self):
        self.obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        self.obj.boot = 'test-boot'
        self.obj.pl_mutation_started, self.obj.worker, self.obj.gdm_isolated = False, None, True
        self.events = []
        self.obj.emit = lambda event, **kw: self.events.append((event, kw))
        self.calls = 0

    def run_scans(self, scans):
        values = iter(scans)
        def read():
            self.calls += 1
            return next(values)
        self.obj.observation = read
        with patch.object(trial.time, 'sleep'), patch.object(Path, 'exists', return_value=False):
            self.obj.wait_prepl_quiet()

    def test_preserved_real_race_then_two_clean_reads(self):
        root = Path(__file__).resolve().parents[3]
        rows = [json.loads(row) for row in (root/'evidence/board_platform/A10_20261023_isolated_idle_v1/parked_readback_01/lifecycle.jsonl').read_text().splitlines()]
        race = next(row['scan'] for row in rows if row['event'] == 'PROCESS_RELEASE_OBSERVATION')
        self.obj.boot = race['boot_id']
        clean = clear_snapshot()
        clean.update(boot_id=self.obj.boot, boot_id_after=self.obj.boot)
        self.run_scans([(race, None, True), (clean, None, True), (clean, None, True)])
        self.assertEqual(self.calls, 3)
        self.assertEqual(self.events[-1][0], 'PREPL_TWO_COMPLETE_QUIET_READS')

    def test_single_clean_read_does_not_suffice_and_bound_is_four(self):
        scans = []
        for i in range(4):
            scan = clear_snapshot()
            scan['inspected_processes'][0]['pid'] = 100+i
            scans.append((scan, None, True))
        with self.assertRaisesRegex(RuntimeError, 'QUIET_NOT_ESTABLISHED'):
            self.run_scans(scans)
        self.assertEqual(self.calls, 4)

    def test_cannot_enter_after_any_pl_command_or_worker(self):
        for attribute, value in (('pl_mutation_started', True), ('worker', object()), ('gdm_isolated', False)):
            original = getattr(self.obj, attribute)
            setattr(self.obj, attribute, value)
            with self.assertRaisesRegex(RuntimeError, 'only before PL'):
                self.run_scans([])
            setattr(self.obj, attribute, original)
        self.assertEqual(self.calls, 0)

    def test_kernel_fault_unknown_permission_or_device_user_never_retried(self):
        for change in ('kernel', 'permission', 'holder', 'vma', 'wrong_boot', 'module'):
            scan, refs, allowed = clear_snapshot(), None, True
            if change == 'kernel': allowed = False
            elif change == 'permission':
                scan.update(scan_complete=False, scan_issues=[dict(reason='PermissionError: inaccessible')])
            elif change == 'holder': scan['device_holders'] = [dict(pid=123)]
            elif change == 'vma': scan['device_mappings'] = [dict(pid=123)]
            elif change == 'wrong_boot': scan['boot_id_after'] = 'old'
            elif change == 'module': refs = 0
            self.calls = 0
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.run_scans([(scan, refs, allowed)])
            self.assertEqual(self.calls, 1)


if __name__ == '__main__':
    unittest.main()
