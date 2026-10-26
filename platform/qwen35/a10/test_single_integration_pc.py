"""PC integration only: real orchestration/locks/child, fake native/hardware.

No board, XRT, system service, driver or FPGA is contacted. Inherited negative
tests exercise the unchanged idle management gates with the NEW single scope.
"""
from contextlib import ExitStack
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

import isolated_single_trial as trial
import single_compute_policy as policy
import test_idle_integration_pc as idle_fixture
from test_single_compute import CHILD, review


class SingleControllerIntegrationTests(idle_fixture.ControllerIntegrationTests):
    def setUp(self):
        super().setUp()
        stack = ExitStack()
        self.addCleanup(stack.close)
        for module in (policy, trial):
            stack.enter_context(patch.object(module, 'CENTRAL', self.central))
            stack.enter_context(patch.object(module, 'LOCKS', self.locks))
            stack.enter_context(patch.object(module, 'ASSETS', self.fixture_assets))
            stack.enter_context(patch.object(module, 'trusted_file', self.pc_trusted_file))
            stack.enter_context(patch.object(module, 'digest', self.digest))
        self.window = 'a10-isolated-single-20261023-v9001'
        for name in policy.SOURCES:
            (self.source/name).write_text('# PC fixture, NOT deployed\n')
        (self.source/'vector.json').write_text(json.dumps(policy.vector()))
        (self.source/'prior-idle-audit.json').write_text(json.dumps(dict(
            status='PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS', kernel=policy.KERNEL,
            machine_sha256=policy.MACHINE, pc_fixture_only=True)))
        names = set(policy.ASSETS) | set(policy.SOURCES) | {'shell.json', 'vector.json', 'prior-idle-audit.json'}
        manifest = dict(schema='A10_ISOLATED_SINGLE_BUNDLE_V1', scope=policy.SCOPE,
                        authorization_included=False, max_submissions=1, board_accepted=False,
                        files={n: dict(bytes=(self.source/n).stat().st_size,
                                       sha256=self.digest(self.source/n)) for n in names})
        (self.source/'manifest.json').write_text(json.dumps(manifest))
        approved = dict(review(), boot_id=self.boot, window_id=self.window,
                        baseline_sha256=self.digest(self.source/'baseline.raw.txt'),
                        bundle_sha256=self.digest(self.source/'manifest.json'),
                        prior_idle_audit_sha256=self.digest(self.source/'prior-idle-audit.json'),
                        baseline_read_uptime_ns=time.monotonic_ns())
        (self.source/'review.json').write_text(json.dumps(approved))
        self.review_sha = self.digest(self.source/'review.json')
        self.obj = trial.IsolatedSingleTrial(self.source, self.review_sha)
        self.obj.target = self.root/'firmware'
        self.obj.snapshot, self.obj.park = self.snapshot, self.park

    def popen(self, argv, **kwargs):
        if len(argv) > 4 and argv[:3] == ['/usr/bin/python3', '-B', '-I']:
            self.calls.append(tuple(argv))
            self.assertEqual(argv[3], str(self.source/'single_compute_entry.py'))
            self.assertEqual(argv[4:7], ['--execute-isolated-single', '--source', str(self.source)])
            self.assertEqual(argv[-4], '--a10-boundary-request')
            mode = {'worker_identity': 'wrong_pid', 'bad_numeric': 'bad_numeric',
                    'two_runs': 'two_runs', 'wrong_baseline': 'wrong_baseline'}.get(self.fault, 'normal')
            return self.original_popen([sys._base_executable, '-B', '-I', '-c', CHILD,
                                        '--mode', mode, *argv[-4:]], **kwargs)
        return super().popen(argv, **kwargs)

    def execute(self):
        with patch.object(trial, 'IsolatedSingleTrial', return_value=self.obj):
            return trial.main(['--execute-authorized-single-once', '--source', str(self.source),
                               '--review-sha256', self.review_sha])

    def assert_blocked(self, fault, reason):
        super().assert_blocked(fault, reason)
        self.assertFalse((self.source/'single-receipt.json').exists())

    def test_real_logs_locks_child_exit_and_restore_wiring(self):
        self.assertEqual(self.execute(), 0)
        events = self.events()
        names = [r['event'] for r in events]
        self.assertLess(names.index('WORKER_REAPED'), names.index('RELEASE_PRECHECK_PASSED_NOT_UNLOADED'))
        self.assertEqual(names[-1], 'SINGLE_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED')
        self.assertTrue(all(r['boot_id'] == self.boot and r['window_id'] == self.window for r in events))
        self.assertFalse((self.central/'active').exists())
        self.assertEqual((self.gdm, self.overlay, self.module), ('active', policy.DEFAULT, False))
        self.assertEqual(self.obj.held_locks, [])
        receipt = policy.load_json(self.source/'single-receipt.json')
        self.assertEqual(receipt['compute_runs'], 1)  # Explicit PC fixture, NOT a hardware run.
        self.assertTrue(receipt['worker_result']['PC_FIXTURE_ONLY'])
        self.assertEqual(receipt['A10'], 'NOT_PASSED_UNTIL_INDEPENDENT_FINAL_READBACK_AND_REQUIREMENT_AUDIT')
        baseline = policy.load_json(self.source/'worker-baseline.json')
        self.assertEqual(baseline['manager_pid'], os.getpid())
        self.assertEqual(baseline['raw_sha256'], self.digest(self.source/'worker-baseline.raw.txt'))
        self.assertEqual(self.obj.identity['worker_baseline_sha256'], self.digest(self.source/'worker-baseline.json'))

    def test_wrong_result_count_blocks_teardown(self):
        self.assert_blocked('two_runs', 'WORKER_RESULT_UNPROVEN')

    def test_wrong_actual_result_blocks_teardown(self):
        self.assert_blocked('bad_numeric', 'WORKER_RESULT_UNPROVEN')

    def test_worker_baseline_identity_blocks_teardown(self):
        self.assert_blocked('wrong_baseline', 'WORKER_RESULT_UNPROVEN')


if __name__ == '__main__':
    unittest.main()
