"""PC fixtures only. Never open UART, SSH, an FPGA node or a board device."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import candidate_idle_trial as candidate
import idle_board_trial as legacy
from kernel_log_gate import KernelLogBlocked, diagnostics, digest

BOOT = '12345678-1234-4234-8234-123456789abc'  # fixture, not a board observation
BASE = '<6>[ 1.000000] Linux ready\n<4>[ 2.000000] baseline warning\n'
NEW = '<3>[ 3.000000] OF: ERROR: memory leak, expected refcount 1 instead of 65\n'


def review(raw=BASE):
    return dict(schema='A10_IDLE_BASELINE_REVIEW_V1', scope=candidate.REVIEW_SCOPE,
                kernel=candidate.KERNEL, machine_id_sha256=legacy.MACHINE,
                driver_sha256=candidate.DRIVER_SHA, compute_authorized=False, boot_id=BOOT,
                raw_dmesg_sha256=digest(raw), reviewer='UNIT_TEST_FIXTURE_NOT_BOARD_REVIEW',
                review_rationale='Fixture for exact-byte checks; no real diagnostic accepted.',
                diagnostic_decisions=[
                    dict(diagnostic=d, decision='ACCEPT_BASELINE_FOR_IDLE_ONLY', rationale='Fixture only')
                    for d in diagnostics(raw)])


class CandidateIdleTests(unittest.TestCase):
    def test_default_plan_does_not_read_or_change_board(self):
        output = io.StringIO()
        with patch.object(candidate, 'CandidateTrial') as trial, \
                patch.object(candidate, 'prepare') as prepare, \
                patch.object(Path, 'read_bytes', side_effect=AssertionError('unexpected read')), \
                patch.object(Path, 'read_text', side_effect=AssertionError('unexpected read')), \
                contextlib.redirect_stdout(output):
            self.assertEqual(candidate.main([]), 0)
        trial.assert_not_called()
        prepare.assert_not_called()
        p = json.loads(output.getvalue())
        self.assertIsNone(p['boot_id'])
        self.assertFalse(p['authorized'])
        self.assertFalse(p['execution_performed'])
        self.assertEqual(p['limits']['compute_runs'], 0)
        self.assertEqual(p['numerical_regression'], 'CANCELLED_BY_USER')

    def test_candidate_identity_does_not_change_historical_trial(self):
        self.assertNotEqual(candidate.CandidateTrial.kernel_release, legacy.Trial.kernel_release)
        self.assertEqual(legacy.Trial.kernel_release, '6.8.0-1015-xilinx')
        self.assertEqual(legacy.Trial.boot, legacy.BOOT)
        self.assertEqual(legacy.Trial.target, legacy.TARGET)
        self.assertIsNone(legacy.Trial.reviewed_baseline_sha256)
        self.assertEqual(candidate.CandidateTrial.driver.as_posix(), candidate.DRIVER)
        self.assertEqual(candidate.CandidateTrial.temperature_limit_mC, 55000)
        self.assertEqual(candidate.CandidateTrial.memory_reserve_KiB, 1048576)

    def test_exact_review_and_all_duplicate_diagnostics(self):
        self.assertEqual(candidate.validate_review(review(), BASE), (BOOT, digest(BASE)))
        repeated = BASE + NEW + NEW
        r = review(repeated)
        self.assertEqual(len(r['diagnostic_decisions']), 3)
        candidate.validate_review(r, repeated)
        r['diagnostic_decisions'].pop()
        with self.assertRaises(RuntimeError):
            candidate.validate_review(r, repeated)

    def test_review_rejects_scope_identity_and_incomplete_log(self):
        for key, value in [('kernel', '6.8.0-1015-xilinx'), ('machine_id_sha256', 'other'),
                           ('driver_sha256', 'old-driver'), ('compute_authorized', True),
                           ('boot_id', None), ('boot_id', '00000000-0000-0000-0000-000000000000'),
                           ('raw_dmesg_sha256', '0' * 64), ('reviewer', ''), ('review_rationale', ''),
                           ('diagnostic_decisions', []), ('scope', 'COMPUTE')]:
            with self.subTest(key=key, value=value), self.assertRaises((RuntimeError, ValueError)):
                candidate.validate_review({**review(), key: value}, BASE)
        for raw in ['', BASE.rstrip(), BASE + '\x00\n', BASE + '<6> appended\n']:
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                candidate.validate_review(review(), raw)
        for key, value in [('rationale', ''), ('decision', 'IGNORE_FOREVER'),
                           ('diagnostic', {'line': 99})]:
            r = review()
            r['diagnostic_decisions'][0][key] = value
            with self.assertRaises(RuntimeError):
                candidate.validate_review(r, BASE)

    def test_allowlist_excludes_compute_force_reset_and_wrong_driver(self):
        for cmd in [['dmesg', '--color=never'], ['dfx-mgr-client', '-listPackage']]:
            candidate.command_gate(cmd, False)
        for cmd in [['insmod', candidate.DRIVER], ['rmmod', 'zocl'],
                    ['dfx-mgr-client', '-load', candidate.PACKAGE],
                    ['dfx-mgr-client', '-load', legacy.DEFAULT],
                    ['dfx-mgr-client', '-remove', '7']]:
            candidate.command_gate(cmd, True)
            with self.assertRaises(RuntimeError):
                candidate.command_gate(cmd, False)
        for cmd in [['reboot'], ['reset'], ['rmmod', '-f', 'zocl'], ['modprobe', 'zocl'],
                    ['insmod', str(legacy.DRIVER)], ['dfx-mgr-client', '-remove', '-1'],
                    ['dfx-mgr-client', '-load', legacy.PACKAGE], ['vadd', '--count', '1000'],
                    ['dmesg', '-c'], ['sh', '-c', 'anything']]:
            for changing in (False, True):
                with self.subTest(cmd=cmd, changing=changing), self.assertRaises(RuntimeError):
                    candidate.command_gate(cmd, changing)

    def test_loaded_topology_uses_candidate_package(self):
        path = '/sys/devices/platform/axi/axi:zyxclmm_drm'
        state = dict(overlays={candidate.PACKAGE + '_image_1': 'applied'},
                     zocl_bound=['ZOCL_CU_INTC.2.auto', 'axi:zyxclmm_drm'],
                     zocl_binding_details=[
                         dict(name='axi:zyxclmm_drm', driver='zocl-drm', path=path),
                         dict(name='ZOCL_CU_INTC.2.auto', driver='zocl_irq_intc',
                              path=path + '/ZOCL_CU_INTC.2.auto')],
                     render_nodes=['/dev/dri/renderD128'], device_holders=[], fpga_state='operating')
        legacy.check_loaded(state, candidate.PACKAGE)
        with self.assertRaises(RuntimeError):
            legacy.check_loaded(state)  # the historical trial still rejects it

    def make_bundle(self, root):
        artifacts = root / 'platform/build/a1-overlay-candidate-20260928'
        artifacts.mkdir(parents=True)
        mock_hashes = {}
        for name in legacy.HASHES:
            data = ('UNIT_TEST_NOT_HARDWARE_' + name).encode()
            (artifacts / name).write_bytes(data)
            mock_hashes[name] = hashlib.sha256(data).hexdigest()
        return mock_hashes

    def test_pc_bundle_inventory_hashes_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(candidate, 'HASHES', self.make_bundle(root)):
                out = root / 'new-bundle'
                result = candidate.prepare(root, out)
                self.assertFalse(result['board_contact'])
                candidate.verify_bundle(out, result['manifest_sha256'])
                # Running its harmless default must not add an unmanifested
                # __pycache__ that would prevent the later explicit entry.
                child = subprocess.run([sys.executable, str(out / 'candidate_idle_trial.py')],
                                       capture_output=True, text=True, timeout=5, check=False)
                self.assertEqual(child.returncode, 0, child.stderr)
                self.assertFalse(json.loads(child.stdout)['execution_performed'])
                candidate.verify_bundle(out, result['manifest_sha256'])
                before = {p.name: p.read_bytes() for p in out.iterdir()}
                with self.assertRaises(FileExistsError):
                    candidate.prepare(root, out)
                self.assertEqual(before, {p.name: p.read_bytes() for p in out.iterdir()})
                with self.assertRaises(RuntimeError):
                    candidate.verify_bundle(out, '0' * 64)
                (out / 'unexpected.xclbin').write_bytes(b'fixture')
                with self.assertRaises(RuntimeError):
                    candidate.verify_bundle(out, result['manifest_sha256'])
                (out / 'unexpected.xclbin').unlink()  # only this test-created temporary file
                (out / 'kernel_log_gate.py').write_bytes(b'tampered')
                with self.assertRaises(RuntimeError):
                    candidate.verify_bundle(out, result['manifest_sha256'])

    def test_wrong_artifact_prevents_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_bundle(root)
            with self.assertRaises(RuntimeError):
                candidate.prepare(root, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_constructor_rejects_review_before_creating_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(candidate, 'verify_bundle'):
                with self.assertRaises(RuntimeError):
                    candidate.CandidateTrial(Path(tmp), 'a' * 64, {}, BASE)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_wrong_kernel_rejected_before_base_runner(self):
        trial = candidate.CandidateTrial.__new__(candidate.CandidateTrial)
        trial.snapshot = Mock()
        trial.kernel_checkpoint = Mock()
        with patch.object(candidate.os, 'geteuid', return_value=0, create=True), \
                patch.object(candidate.os, 'uname', return_value=Mock(machine='aarch64',
                            release='6.8.0-1015-xilinx'), create=True), \
                patch.object(legacy.Trial, 'run') as base_run:
            with self.assertRaises(RuntimeError):
                trial.run()
        trial.snapshot.assert_not_called()
        base_run.assert_not_called()

    def test_failed_preflight_log_never_enters_mutation_runner(self):
        trial = candidate.CandidateTrial.__new__(candidate.CandidateTrial)
        trial.snapshot = Mock()
        trial.kernel_checkpoint = Mock(side_effect=KernelLogBlocked('unreviewed baseline'))
        with patch.object(candidate.os, 'geteuid', return_value=0, create=True), \
                patch.object(candidate.os, 'uname', return_value=Mock(machine='aarch64',
                            release=candidate.KERNEL), create=True), \
                patch.object(legacy.Trial, 'run') as base_run:
            with self.assertRaises(KernelLogBlocked):
                trial.run()
        base_run.assert_not_called()

    def trial_fixture(self):
        trial = candidate.CandidateTrial.__new__(candidate.CandidateTrial)
        trial.boot = BOOT
        trial.reviewed_baseline_sha256 = digest(BASE)
        trial.emit = Mock()
        return trial

    def test_new_warning_stops_even_when_same_text_was_reviewed(self):
        trial = self.trial_fixture()
        child = Mock(returncode=0)
        child.communicate.return_value = ('', '')
        appended = BASE + BASE.splitlines(keepends=True)[-1]
        with patch.object(legacy.Path, 'read_text', return_value=BOOT), \
                patch.object(legacy.subprocess, 'run', side_effect=[
                    Mock(returncode=0, stderr=b'', stdout=BASE.encode()),
                    Mock(returncode=0, stderr=b'', stdout=appended.encode()),
                    Mock(returncode=0, stderr=b'', stdout=appended.encode())]), \
                patch.object(legacy.subprocess, 'Popen', return_value=child) as mutate:
            with self.assertRaises(KernelLogBlocked):
                trial.command(['dfx-mgr-client', '-remove', '7'], True)
            with self.assertRaises(KernelLogBlocked):
                trial.command(['insmod', candidate.DRIVER], True)
        self.assertEqual(mutate.call_count, 1)
        child.kill.assert_not_called()
        child.terminate.assert_not_called()

    def test_boot_changed_or_raw_unreviewed_blocks_first_mutation(self):
        for boot, raw in [('other-boot', BASE), (BOOT, BASE + NEW)]:
            trial = self.trial_fixture()
            with patch.object(legacy.Path, 'read_text', return_value=boot), \
                    patch.object(legacy.subprocess, 'run',
                                 return_value=Mock(returncode=0, stderr=b'', stdout=raw.encode())), \
                    patch.object(legacy.subprocess, 'Popen') as mutate:
                with self.assertRaises(KernelLogBlocked):
                    trial.command(['insmod', candidate.DRIVER], True)
                mutate.assert_not_called()

    def test_successful_review_only_permits_scoped_idle_call(self):
        trial = self.trial_fixture()
        child = Mock(returncode=0)
        child.communicate.return_value = ('', '')
        with patch.object(legacy.Path, 'read_text', return_value=BOOT), \
                patch.object(legacy.subprocess, 'run',
                             return_value=Mock(returncode=0, stderr=b'', stdout=BASE.encode())), \
                patch.object(legacy.subprocess, 'Popen', return_value=child) as mutate:
            trial.command(['insmod', candidate.DRIVER], True)
            with self.assertRaises(RuntimeError):
                trial.command(['vadd'], True)
        self.assertEqual(mutate.call_count, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
