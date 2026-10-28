"""PC integration of the actual manager, logs, locks and child-exit boundary.

No board, XRT library, device node, systemctl or dfx command is opened/run.
Hardware observations and external commands are explicit stateful fixtures.
Temporary files/flocks, policy validation, orchestration, evidence writes,
kernel gate, process reaping and release decisions are the production code.
"""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

import isolated_idle_policy as policy
import isolated_idle_trial as trial
from minimal_gate import PREFIX, IRQ_END, TEST_PROPERTIES, DEFAULT_PROPERTIES
from test_xrt_worker_boundary import CHILD, clear_snapshot


class Parked(BaseException):
    """Test-only escape, never used by the production controller."""


@unittest.skipUnless(os.name == 'posix', 'Actual flock/proc checks require Linux PC')
class ControllerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a10-controller-pc-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir(mode=0o700)
        self.central = self.root / 'central'
        self.central.mkdir(mode=0o700)
        (self.central / 'history').mkdir(mode=0o700)
        self.locks = (self.central / 'deployment.lock', self.central / 'shared.lock')
        self.boot = str(uuid.uuid4())
        self.window = 'a10-isolated-idle-20261023-v9001'
        self.calls, self.lock_streams = [], []
        self.fault, self.scan_count = None, 0
        self.gdm, self.module, self.overlay = 'active', False, policy.DEFAULT
        self.raw = '<6>[1.0] PC fixture kernel baseline\n'
        self.original_popen = subprocess.Popen
        self.original_read = Path.read_text
        self.original_read_bytes = Path.read_bytes
        self.original_exists = Path.exists
        self.original_digest = policy.digest
        self.original_lexists = os.path.lexists
        self.fixture_assets = {}
        for name in policy.ASSETS:
            path = self.source / name
            path.write_bytes(b'PC_FIXTURE_NOT_EXECUTABLE_FIRMWARE:' + name.encode())
            self.fixture_assets[name] = policy.digest(path)
        for name in policy.SOURCES:
            (self.source / name).write_text('# PC bundle fixture; not executable\n')
        (self.source / 'shell.json').write_text(json.dumps(
            dict(shell_type='XRT_FLAT', num_pl_slots=1, num_aie_slots=0)))
        manifest = dict(schema='A10_ISOLATED_IDLE_BUNDLE_V1', scope=policy.SCOPE,
                        compute_authorized=False, files={p.name: dict(
                            bytes=p.stat().st_size, sha256=policy.digest(p))
                            for p in self.source.iterdir()})
        (self.source / 'manifest.json').write_text(json.dumps(manifest))
        (self.source / 'baseline.raw.txt').write_text(self.raw)
        review = dict(schema='A10_ISOLATED_IDLE_REVIEW_V1', scope=policy.SCOPE,
                      authorized=True, allow_gdm_stop_restore=True, compute_authorized=False,
                      boot_id=self.boot, window_id=self.window, kernel=policy.KERNEL,
                      machine_sha256=policy.MACHINE,
                      baseline_sha256=policy.digest(self.source / 'baseline.raw.txt'),
                      bundle_sha256=policy.digest(self.source / 'manifest.json'),
                      baseline_read_uptime_ns=time.monotonic_ns())
        (self.source / 'review.json').write_text(json.dumps(review))
        self.review_sha = policy.digest(self.source / 'review.json')
        self.platform_hashes = {**policy.BOOT_FILES, **policy.LIBRARIES,
                               '/etc/machine-id': policy.MACHINE}
        self.platform_hashes.update({str(Path('/lib/firmware/xilinx') / policy.DEFAULT / n): sha
                                     for n, sha in trial.RESTORE.items()})

        stack = ExitStack()
        self.addCleanup(stack.close)
        # OS/board boundaries are mocked; no generic shell or device fallback.
        for module in (policy, trial):
            stack.enter_context(patch.object(module, 'CENTRAL', self.central))
            stack.enter_context(patch.object(module, 'LOCKS', self.locks))
            stack.enter_context(patch.object(module, 'ASSETS', self.fixture_assets))
            stack.enter_context(patch.object(module, 'trusted_file', self.pc_trusted_file))
            stack.enter_context(patch.object(module, 'digest', self.digest))
        stack.enter_context(patch.object(trial.os, 'geteuid', return_value=0))
        stack.enter_context(patch.object(trial.os, 'uname', return_value=SimpleNamespace(
            machine='aarch64', release=policy.KERNEL)))
        stack.enter_context(patch.object(trial.signal, 'pthread_sigmask'))
        stack.enter_context(patch.object(trial.os, 'umask'))
        stack.enter_context(patch.object(Path, 'read_text', lambda p, *a, **k: self.read(p, *a, **k)))
        stack.enter_context(patch.object(Path, 'read_bytes', lambda p: self.read_bytes(p)))
        stack.enter_context(patch.object(Path, 'exists', lambda p: self.exists(p)))
        stack.enter_context(patch.object(os.path, 'lexists', self.lexists))
        stack.enter_context(patch.object(subprocess, 'run', self.run_command))
        stack.enter_context(patch.object(subprocess, 'Popen', self.popen))
        stack.enter_context(patch.object(trial, 'collect', self.collect))
        stack.enter_context(patch.object(trial.time, 'sleep', lambda delay: None))
        stack.enter_context(patch('sys.stdout', new=io.StringIO()))
        self.obj = trial.IsolatedIdleTrial(self.source, self.review_sha)
        self.obj.target = self.root / 'firmware'
        self.obj.snapshot = self.snapshot
        self.obj.park = self.park
        self.addCleanup(self.close_fixture_resources)

    def pc_trusted_file(self, path):
        p = Path(path)
        self.assertTrue(p.is_relative_to(self.root), str(p))
        self.assertFalse(p.is_symlink())
        self.assertEqual(p.stat().st_uid, os.getuid())  # PC owner, not a board root proof
        self.assertEqual(p.stat().st_mode & 0o022, 0)

    def digest(self, path):
        return self.platform_hashes[str(path)] if str(path) in self.platform_hashes else self.original_digest(path)

    def read(self, path, *args, **kw):
        name = str(path)
        if name == '/proc/sys/kernel/random/boot_id':
            return self.boot + '\n'
        if name == '/etc/dfx-mgrd/default_firmware':
            return policy.DEFAULT + '\n'
        if name == '/sys/module/zocl/srcversion':
            self.assertTrue(self.module)
            return '15F2AC2306CB3CB7257CFCB\n'
        if name == '/sys/module/zocl/refcnt':
            self.assertTrue(self.module)
            return '1\n' if self.fault == 'refs' and self.worker_reaped() else '0\n'
        if name.startswith(('/sys/', '/etc/', '/boot/', '/lib/firmware')):
            self.fail('unexpected board read: ' + name)
        return self.original_read(path, *args, **kw)

    def read_bytes(self, path):
        prefix = '/sys/firmware/devicetree/base/axi/'
        suffix = str(path).removeprefix(prefix)
        entries = {'interrupt-controller@80020000/phandle': (42).to_bytes(4, 'big'),
                   'interrupt-controller@80020000/#interrupt-cells': (2).to_bytes(4, 'big'),
                   'interrupt-controller@80020000/xlnx,num-intr-inputs': (32).to_bytes(4, 'big'),
                   'zyxclmm_drm/interrupts-extended': b''.join(struct.pack('>III', 42, n, 4) for n in range(32))}
        if str(path).startswith(prefix):
            self.assertIn(suffix, entries)
            return entries[suffix]
        return self.original_read_bytes(path)

    def exists(self, path):
        if str(path) in ('/sys/module/zocl', '/sys/module/zocl/refcnt'):
            return self.module
        if str(path) == '/state.txt':
            return False
        return self.original_exists(path)

    def lexists(self, path):
        if str(path) in ('/lib/firmware/a1-vadd.bit.bin', '/lib/firmware/a1-vadd.dtbo'):
            return False
        return self.original_lexists(path)

    def run_command(self, argv, **kw):
        self.calls.append(tuple(argv))
        if argv == ['dmesg', '--raw']:
            return SimpleNamespace(returncode=0, stdout=self.raw.encode(), stderr=b'')
        if argv == ['systemctl', 'is-active', 'gdm.service']:
            return SimpleNamespace(returncode=0 if self.gdm == 'active' else 3,
                                   stdout=(self.gdm + '\n').encode(), stderr=b'')
        self.fail('unexpected PC command, no execution: ' + repr(argv))

    def popen(self, argv, **kw):
        self.calls.append(tuple(argv))
        if len(argv) > 4 and argv[:3] == ['/usr/bin/python3', '-B', '-I']:
            self.assertEqual(argv[3], str(self.source / 'isolated_idle_entry.py'))
            self.assertEqual(argv[4:7], ['--execute-isolated-idle', '--source', str(self.source)])
            self.assertEqual(argv[-4], '--a10-boundary-request')
            mode = 'wrong_pid' if self.fault == 'worker_identity' else 'normal'
            # Only this known no-XRT PC child can actually execute.
            return self.original_popen([sys._base_executable, '-B', '-I', '-c', CHILD,
                                        '--mode', mode, *argv[-4:]], **kw)
        out = ''
        if argv in (['systemctl', 'stop', 'gdm.service'], ['systemctl', 'start', 'gdm.service']):
            if self.fault == 'gdm_timeout' and argv[1] == 'stop':
                def unknown(**unused):
                    raise subprocess.TimeoutExpired(argv, 30)
                return SimpleNamespace(returncode=None, communicate=unknown)
            self.gdm = 'inactive' if argv[1] == 'stop' else 'active'
        elif argv == ['dfx-mgr-client', '-listPackage']:
            out = f'{policy.DEFAULT} 0->0\n{self.window} 0->1\n'
            if self.fault == 'lease_tamper':
                (self.central / 'active/lease.json').write_text('{}')
        elif argv == ['dfx-mgr-client', '-remove', '0']:
            self.assertEqual(self.overlay, policy.DEFAULT)
            self.overlay = None
        elif argv == ['insmod', str(self.obj.driver)]:
            self.assertFalse(self.module)
            self.module = True
            self.raw += '<4>[2.0] zocl: loading out-of-tree module taints kernel.\n'
            if self.fault == 'kernel':
                self.raw += '<3>[2.1] PC injected unreviewed fault\n'
        elif argv == ['dfx-mgr-client', '-load', self.window]:
            self.assertTrue(self.module)
            self.overlay = self.window
            self.raw += ''.join(f'<4>[3.0] {PREFIX}{p}\n' for p in TEST_PROPERTIES)
            self.raw += '<3>[3.1] ' + IRQ_END + '\n'
        elif argv == ['dfx-mgr-client', '-remove', '1']:
            self.assertEqual(self.obj.worker.state, 'RELEASE_PRECHECK_PASSED')
            self.assertIsNotNone(self.obj.worker.process.returncode)
            self.overlay = None
        elif argv == ['rmmod', 'zocl']:
            self.assertIsNone(self.overlay)
            self.module = False
        elif argv == ['dfx-mgr-client', '-load', policy.DEFAULT]:
            self.assertFalse(self.module)
            self.overlay = policy.DEFAULT
            self.raw += ''.join(f'<4>[4.0] {PREFIX}{p}\n' for p in DEFAULT_PROPERTIES)
        else:
            self.fail('unexpected command, no execution: ' + repr(argv))
        text = kw.get('text', False)
        return SimpleNamespace(returncode=0, communicate=lambda **unused: (out, '') if text else (out.encode(), b''))

    def snapshot(self, phase):
        details = []
        if self.overlay == self.window:
            main = '/fixture/axi/zyxclmm_drm'
            details = [dict(name='axi:zyxclmm_drm', path=main, driver='zocl-drm'),
                       dict(name='ZOCL_CU_INTC.0.auto', path=main + '/ZOCL_CU_INTC.0.auto', driver='zocl_irq_intc')]
            if self.obj.worker is not None and self.obj.worker.process is not None:
                details.append(dict(name='CU.0.auto', path=main + '/CU.0.auto', driver='cu_drv'))
        # Trial.snapshot enumerates details in sorted binding-name order.
        details.sort(key=lambda row: row['name'])
        row = dict(phase=phase, boot_id=self.boot, overlays={self.overlay + '_image_1': 'applied'} if self.overlay else {},
                   zocl_binding_details=details, zocl_bound=sorted(d['name'] for d in details),
                   render_nodes=['/dev/dri/renderD128'] if details else [], device_holders=[],
                   accelerator_card_nodes=[], module_refcount=0 if self.module else None,
                   fpga_state='operating', vart_sha256='f' * 64,
                   pc_fixture_only=True)
        self.obj.emit('READBACK', **row)
        return row

    def worker_reaped(self):
        return self.obj.worker is not None and self.obj.worker.exited_ns is not None

    def collect(self, **kw):
        self.assertEqual(kw, dict(allow_ps_display=True))
        self.scan_count += 1
        row = clear_snapshot()
        row.update(boot_id=self.boot, boot_id_after=self.boot)
        if self.fault == 'prepl_race' and self.scan_count == 1:
            row.update(scan_complete=False, scan_issues=[dict(reason='PROCESS_SET_CHANGED')])
        if self.fault == 'vma' and self.worker_reaped():
            row['device_mappings'] = [dict(pid=999, map='/dev/dri/renderD128 (deleted)')]
        return row

    def park(self, reason):
        self.lock_streams = list(self.obj.held_locks)
        self.obj.emit('PC_QUARANTINE_ESCAPE', reason=reason, pc_fixture_only=True)
        raise Parked(reason)

    def execute(self):
        # Constructor above is real; main() failure handling and run() are real.
        with patch.object(trial, 'IsolatedIdleTrial', return_value=self.obj):
            return trial.main(['--execute-authorized-idle-once', '--source', str(self.source),
                               '--review-sha256', self.review_sha])

    def events(self):
        return [json.loads(line) for line in (self.source / 'lifecycle.jsonl').read_text().splitlines()]

    def close_fixture_resources(self):
        if self.obj.worker is not None:
            if self.obj.worker.process is not None:
                self.obj.worker.process.wait(timeout=5)
            for stream in self.obj.worker.logs:
                stream.close()
        for stream in self.obj.held_locks:
            stream.close()  # PC temporary locks only, after assertions, not production cleanup
        if self.obj.log is not None:
            self.obj.log.close()

    def test_real_logs_locks_child_exit_and_restore_wiring(self):
        self.assertEqual(self.execute(), 0)
        events = self.events()
        names = [row['event'] for row in events]
        self.assertLess(names.index('WORKER_REAPED'), names.index('RELEASE_PRECHECK_PASSED_NOT_UNLOADED'))
        self.assertIn('EXACT_IRQ_DT_VERIFIED', names)
        self.assertEqual(names[-1], 'IDLE_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED')
        self.assertTrue(all(row['boot_id'] == self.boot and row['window_id'] == self.window for row in events))
        reaped = next(row for row in events if row['event'] == 'WORKER_REAPED')
        self.assertEqual(reaped['exit_code'], 0)
        self.assertEqual(reaped['worker_pid'], self.obj.worker.process.pid)
        self.assertIn('observation_monotonic_ns', reaped)
        self.assertFalse((self.central / 'active').exists())
        self.assertEqual(self.gdm, 'active')
        self.assertEqual(self.overlay, policy.DEFAULT)
        self.assertFalse(self.module)
        self.assertEqual(self.obj.held_locks, [])
        receipt = policy.load_json(self.source / 'idle-receipt.json')
        self.assertEqual(receipt['A10'], 'NOT_PASSED_POSTCOMPUTE_VERIFICATION_OPEN')
        self.assertEqual(receipt['compute_runs'], 0)

    def test_prepl_race_is_preserved_before_two_complete_reads(self):
        self.fault = 'prepl_race'
        self.assertEqual(self.execute(), 0)
        events = self.events()
        names = [row['event'] for row in events]
        self.assertIn('PREPL_INCOMPLETE_READ_PRESERVED', names)
        quiet = next(row for row in events if row['event'] == 'PREPL_TWO_COMPLETE_QUIET_READS')
        self.assertEqual(quiet['readiness_attempt'], 3)
        mutation = next(i for i, row in enumerate(events) if row['event'] == 'COMMAND_BEGIN' and row['state_changing'])
        self.assertLess(names.index('PREPL_TWO_COMPLETE_QUIET_READS'), mutation)

    def assert_blocked(self, fault, reason):
        self.fault = fault
        with self.assertRaisesRegex(Parked, reason):
            self.execute()
        self.assertNotIn(('dfx-mgr-client', '-remove', '1'), self.calls)
        self.assertNotIn(('rmmod', 'zocl'), self.calls)
        self.assertNotIn(('systemctl', 'start', 'gdm.service'), self.calls)
        self.assertFalse((self.source / 'idle-receipt.json').exists())
        self.assertTrue((self.central / 'active').is_dir())
        self.assertTrue(all(policy.lock_owned(p, os.getpid()) for p in self.locks))
        self.assertFalse(any(s.closed for s in self.obj.held_locks))

    def test_new_kernel_error_blocks_next_hardware_command(self):
        self.assert_blocked('kernel', 'kernel gate refused')
        self.assertTrue(self.obj.kernel_gate.blocked)
        self.assertNotIn(('dfx-mgr-client', '-load', self.window), self.calls)
        self.assertIsNone(self.obj.worker)

    def test_wrong_worker_identity_blocks_all_teardown(self):
        self.assert_blocked('worker_identity', 'WORKER_RESULT_UNPROVEN')

    def test_post_exit_deleted_vma_blocks_all_teardown(self):
        self.assert_blocked('vma', 'ACCELERATOR_VMA_STILL_MAPPED')

    def test_post_exit_refcount_blocks_all_teardown(self):
        self.assert_blocked('refs', 'MODULE_REFERENCE_HELD_OR_UNKNOWN')

    def test_lease_tamper_blocks_first_pl_mutation(self):
        self.assert_blocked('lease_tamper', 'lease changed')
        self.assertNotIn(('dfx-mgr-client', '-remove', '0'), self.calls)
        self.assertFalse(self.obj.pl_mutation_started)

    def test_unknown_service_result_never_starts_pl_or_worker(self):
        self.assert_blocked('gdm_timeout', 'GDM_ACTION_UNKNOWN_NO_KILL')
        self.assertFalse(self.obj.target.exists())
        self.assertIsNone(self.obj.worker)
        self.assertFalse(self.obj.pl_mutation_started)


if __name__ == '__main__':
    unittest.main()
