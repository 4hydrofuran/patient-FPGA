"""PC tests for the real idle worker code and controller wiring, never a board run."""
import ast
import ctypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from contextlib import ExitStack
from types import SimpleNamespace

import accelerator_release_gate_v2 as release
import isolated_idle_policy as policy
import isolated_idle_worker as worker
import isolated_idle_trial as trial


class Quarantined(BaseException):
    pass


def park(reason):
    raise Quarantined(reason)


class FakeAPI:
    def __init__(self, failure=None, wrong_uuid=False, group=3):
        self.calls, self.failure, self.wrong_uuid, self.group = [], failure, wrong_uuid, group

    def __getattr__(self, name):
        def call(*args):
            self.calls.append(name)
            if name == self.failure:
                return 0 if name in ('xrtDeviceOpen', 'xrtPLKernelOpenExclusive') else -1
            if name == 'xrtDeviceGetXclbinUUID':
                raw = uuid.UUID(policy.XCLBIN_UUID).bytes if not self.wrong_uuid else bytes(16)
                for n, value in enumerate(raw):
                    args[1][n] = value
            if name in ('xrtDeviceOpen', 'xrtPLKernelOpenExclusive'):
                return 123
            if name == 'xrtKernelArgGroupId':
                return self.group
            return 0
        return call


class IdleWorkerTests(unittest.TestCase):
    def test_actual_worker_call_sequence_has_no_compute(self):
        api = FakeAPI()
        result = worker.run_idle(api, Path('fixture.xclbin'), lambda *a, **k: None, park)
        self.assertEqual(api.calls, ['xrtDeviceOpen', 'xrtDeviceLoadXclbinFile',
                         'xrtDeviceGetXclbinUUID', 'xrtPLKernelOpenExclusive',
                         'xrtKernelArgGroupId', 'xrtKernelArgGroupId', 'xrtKernelArgGroupId',
                         'xrtKernelClose', 'xrtDeviceClose'])
        self.assertEqual(result['real_submissions'], 0)
        self.assertEqual(result['explicit_bo_allocations'], 0)
        self.assertTrue(result['normal_handles_closed'])

    def test_every_failed_native_call_parks_without_auto_cleanup(self):
        names = ['xrtDeviceOpen', 'xrtDeviceLoadXclbinFile', 'xrtDeviceGetXclbinUUID',
                 'xrtPLKernelOpenExclusive', 'xrtKernelArgGroupId', 'xrtKernelClose', 'xrtDeviceClose']
        for name in names:
            api = FakeAPI(failure=name)
            with self.subTest(call=name), self.assertRaises(Quarantined):
                worker.run_idle(api, Path('fixture'), lambda *a, **k: None, park)
            self.assertEqual(api.calls[-1], name)

    def test_uuid_and_metadata_mismatches_stop_before_close(self):
        for api in (FakeAPI(wrong_uuid=True), FakeAPI(group=4)):
            with self.assertRaises(Quarantined):
                worker.run_idle(api, Path('fixture'), lambda *a, **k: None, park)
            self.assertNotIn('xrtDeviceClose', api.calls)

    def test_native_soft_deadline_does_not_abort(self):
        api = FakeAPI()
        ticks = iter([0, 0, 11])
        with self.assertRaises(Quarantined):
            worker.run_idle(api, Path('fixture'), lambda *a, **k: None, park, clock=lambda: next(ticks))
        self.assertEqual(api.calls, ['xrtDeviceOpen'])

    def test_default_cli_never_loads_native_or_reads_proc(self):
        with patch.object(worker, 'IdleNativeAPI', side_effect=AssertionError('native forbidden')), \
                patch.object(worker, 'verify_owner', side_effect=AssertionError('board access')), \
                patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(worker.main([]), 0)
            self.assertEqual(trial.main([]), 0)

    def test_source_only_binds_idle_apis(self):
        tree = ast.parse(Path(worker.__file__).read_text())
        names = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and
                 isinstance(node.value, str) and node.value.startswith('xrt')}
        self.assertEqual(names, {'xrtDeviceOpen', 'xrtDeviceClose', 'xrtDeviceLoadXclbinFile',
                                'xrtDeviceGetXclbinUUID', 'xrtPLKernelOpenExclusive',
                                'xrtKernelClose', 'xrtKernelArgGroupId'})
        manager_source = Path(trial.__file__).read_text()
        self.assertNotIn('CDLL', manager_source)
        self.assertNotIn('import isolated_idle_worker', manager_source)


class PolicyTests(unittest.TestCase):
    def review(self):
        return dict(schema='A10_ISOLATED_IDLE_REVIEW_V1', scope=policy.SCOPE,
                    compute_authorized=False, authorized=True, allow_gdm_stop_restore=True,
                    boot_id=str(uuid.uuid4()), kernel=policy.KERNEL, machine_sha256=policy.MACHINE,
                    window_id='a10-isolated-idle-20261023-v1', baseline_sha256='a' * 64,
                    bundle_sha256='b' * 64, baseline_read_uptime_ns=1000)

    def test_missing_authorization_compute_and_old_identity_refused(self):
        policy.validate_review(self.review())
        for change in (dict(authorized=False), dict(compute_authorized=True),
                       dict(allow_gdm_stop_restore=False), dict(kernel='6.8.0-1036-xilinx'),
                       dict(boot_id=next(iter(policy.CONSUMED_BOOTS))), dict(baseline_sha256=''),
                       dict(window_id='a10-refcount-step5-20261022-v1')):
            review = self.review()
            review.update(change)
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                policy.validate_review(review)

    def test_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'duplicate.json'
            p.write_text('{"authorized": false, "authorized": true}')
            with self.assertRaises(RuntimeError):
                policy.load_json(p)

    @unittest.skipUnless(os.name == 'posix', 'Linux /proc/flock proof runs in WSL')
    def test_real_lock_owner_fdinfo(self):
        import fcntl
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'lock'
            with path.open('wb') as stream:
                self.assertFalse(policy.lock_owned(path, os.getpid()))
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self.assertTrue(policy.lock_owned(path, os.getpid()))
                fcntl.flock(stream, fcntl.LOCK_UN)
                self.assertFalse(policy.lock_owned(path, os.getpid()))

    @unittest.skipUnless(os.name == 'posix', 'Linux proc self-fd enumeration')
    def test_real_self_scan_no_disappearing_scanner_fd(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            proc = root / str(os.getpid())
            proc.mkdir()
            for name in ('stat', 'maps', 'fd'):
                (proc / name).symlink_to(Path('/proc/self') / name)
            boot = root / 'sys/kernel/random/boot_id'
            boot.parent.mkdir(parents=True)
            boot.write_text('pc-fixture-boot\n')
            result = release.collect(root)
            self.assertTrue(result['scan_complete'], result['scan_issues'])
            self.assertEqual(result['device_holders'], [])
            self.assertEqual(result['device_mappings'], [])

    def test_unload_requires_real_worker_exit_gate(self):
        obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        obj.package = 'a10-isolated-idle-20261023-v1'
        obj.release_checked = False
        obj.worker = None
        obj.command = lambda *a, **k: self.fail('unload was reached')
        with self.assertRaisesRegex(RuntimeError, 'worker exit'):
            obj.remove(obj.package)

    def test_owner_validation_mismatch_before_hardware(self):
        with patch.object(policy.os, 'geteuid', return_value=1000, create=True):
            with patch.object(Path, 'read_text', return_value='boot'):
                with self.assertRaisesRegex(RuntimeError, 'root'):
                    policy.verify_owner({}, {})

    def test_bundle_missing_code_or_extra_payload_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for files in ({}, {'unknown.py': {'bytes': 0, 'sha256': '0' * 64}}):
                manifest = dict(schema='A10_ISOLATED_IDLE_BUNDLE_V1', scope=policy.SCOPE,
                                compute_authorized=False, files=files)
                path = root / 'manifest.json'
                path.write_text(json.dumps(manifest))
                with self.assertRaisesRegex(RuntimeError, 'inventory'):
                    policy.verify_bundle(root, policy.digest(path))


class ControllerLifecycleTests(unittest.TestCase):
    """Exercise the actual orchestration; all board I/O is explicit PC fixtures."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.obj = trial.IsolatedIdleTrial.__new__(trial.IsolatedIdleTrial)
        obj = self.obj
        obj.source = self.root / 'source'
        obj.source.mkdir()
        for name in ('a1-vadd.bit.bin', 'a1-vadd.dtbo', 'shell.json'):
            (obj.source / name).write_bytes(b'PC_FIXTURE_NOT_FIRMWARE')
        obj.target = self.root / 'firmware'
        obj.package = 'a10-isolated-idle-20261023-v1'
        obj.driver = obj.source / 'zocl.refcount.ko'
        obj.boot = str(uuid.uuid4())
        obj.identity = dict(boot_id=obj.boot, window_id=obj.package,
                            lease_sha256='a' * 64, request_sha256='b' * 64)
        obj.worker = None
        obj.release_checked = False
        obj.gdm_isolated = False
        obj.held_locks = [io.StringIO(), io.StringIO()]
        self.lock_handles = list(obj.held_locks)
        self.events = []
        self.fail_stage = None
        self.central = self.root / 'central'
        (self.central / 'active').mkdir(parents=True)
        (self.central / 'history').mkdir()
        (self.central / 'active/lease.json').write_text('PC_FIXTURE')
        obj.guard = lambda *a: True
        obj.emit = lambda event, **data: self.events.append(event)
        obj.park = park
        obj.kernel_checkpoint = lambda phase: self.events.append('kernel:' + phase)
        obj.observation = lambda: self.fail('fake boundary must not collect actual /proc')

        def service(action):
            self.events.append('gdm:' + action)
            obj.gdm_isolated = action == 'stop'

        def command(argv, state_changing=False):
            self.events.append(tuple(argv))
            if argv == ['dfx-mgr-client', '-listPackage']:
                return f'{policy.DEFAULT} 0->0\n{obj.package} 0->1\n'
            if argv == ['dfx-mgr-client', '-remove', '1']:
                self.assertEqual(obj.worker.state, 'RELEASE_PRECHECK_PASSED')
                self.assertIn('worker_reaped', self.events)
            return ''

        def no_users(*, module_loaded):
            self.events.append('no_users:' + str(module_loaded))

        def state(phase):
            row = dict(overlays={}, zocl_bound=[], zocl_binding_details=[], render_nodes=[],
                       accelerator_card_nodes=[], device_holders=[], module_refcount=None,
                       fpga_state='operating', vart_sha256='f' * 64)
            if phase in ('initial', 'default_restored', 'graphical_restored'):
                row['overlays'] = {policy.DEFAULT + '_image_1': 'applied'}
            if phase in ('module_unbound', 'test_removed'):
                row['module_refcount'] = 0
            if phase in ('test_loaded', 'worker_exited_topology'):
                main = dict(name='axi:zyxclmm_drm', path='/fake/axi/zyxclmm_drm', driver='zocl-drm')
                intc = dict(name='ZOCL_CU_INTC.0.auto', path=main['path'] + '/ZOCL_CU_INTC.0.auto',
                            driver='zocl_irq_intc')
                row.update(overlays={obj.package + '_image_1': 'applied'},
                           zocl_bound=sorted([main['name'], intc['name']]),
                           zocl_binding_details=sorted([main, intc], key=lambda r: r['name']),
                           render_nodes=['/dev/dri/renderD128'], module_refcount=0)
                if phase == 'worker_exited_topology':
                    child = dict(name='CU.0.auto', path=main['path'] + '/CU.0.auto', driver='cu_drv')
                    if self.fail_stage == 'cu_parent':
                        child['path'] = '/unrelated/CU.0.auto'
                    row['zocl_binding_details'].append(child)
                    row['zocl_bound'].append(child['name'])
            self.events.append('snapshot:' + phase)
            return row

        obj.service, obj.command, obj.no_users, obj.snapshot = service, command, no_users, state
        obj.wait_prepl_quiet = lambda: no_users(module_loaded=False)
        owner = self

        class Boundary:
            state = 'NEW'

            def __init__(self, *a, **kw):
                owner.events.append('worker_construct')

            def start(self, *a, **kw):
                owner.events.append('worker_start')
                self.state = 'RUNNING'

            def wait_normal(self, timeout):
                if owner.fail_stage == 'worker':
                    raise Quarantined('worker failed')
                owner.events.append('worker_reaped')
                self.state = 'EXITED_NORMAL'
                return dict(status='PC_FIXTURE_ONLY', real_submissions=0)

            def check_release(self, observe):
                owner.assertEqual(self.state, 'EXITED_NORMAL')
                if owner.fail_stage == 'release':
                    raise Quarantined('VMA/refcount/kernel gate failed')
                owner.events.append('release_passed')
                self.state = 'RELEASE_PRECHECK_PASSED'

        original_read = Path.read_text

        def read_text(path, *a, **kw):
            if str(path).replace('\\', '/') == '/sys/module/zocl/srcversion':
                return '15F2AC2306CB3CB7257CFCB\n'
            return original_read(path, *a, **kw)

        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(trial, 'CENTRAL', self.central))
        stack.enter_context(patch.object(trial, 'BOOT_FILES', {}))
        stack.enter_context(patch.object(trial, 'LIBRARIES', {}))
        stack.enter_context(patch.object(trial, 'IdleWorkerBoundary', Boundary))
        stack.enter_context(patch.object(Path, 'read_text', read_text))

    def test_normal_order_restores_default_before_unlock(self):
        self.obj.execute_lifecycle(self.obj.snapshot('initial'))
        expected = [('dfx-mgr-client', '-remove', '0'), ('insmod', str(self.obj.driver)),
                    ('dfx-mgr-client', '-load', self.obj.package), 'worker_start', 'worker_reaped',
                    'release_passed', ('dfx-mgr-client', '-remove', '1'), ('rmmod', 'zocl'),
                    ('dfx-mgr-client', '-load', policy.DEFAULT), 'gdm:start']
        indices = [self.events.index(event) for event in expected]
        self.assertEqual(indices, sorted(indices))
        self.assertTrue(all(stream.closed for stream in self.lock_handles))
        self.assertFalse((self.central / 'active').exists())
        receipt = policy.load_json(self.obj.source / 'idle-receipt.json')
        self.assertEqual(receipt['A10'], 'NOT_PASSED_POSTCOMPUTE_VERIFICATION_OPEN')
        self.assertEqual(receipt['compute_runs'], 0)

    def assert_no_teardown_or_success_after_failure(self, stage, exception):
        self.fail_stage = stage
        with self.assertRaises(exception):
            self.obj.execute_lifecycle(self.obj.snapshot('initial'))
        self.assertNotIn(('dfx-mgr-client', '-remove', '1'), self.events)
        self.assertNotIn(('rmmod', 'zocl'), self.events)
        self.assertNotIn('gdm:start', self.events)
        self.assertFalse((self.obj.source / 'idle-receipt.json').exists())
        self.assertTrue((self.central / 'active').exists())
        self.assertTrue(all(not stream.closed for stream in self.lock_handles))

    def test_worker_failure_keeps_all_teardown_blocked(self):
        self.assert_no_teardown_or_success_after_failure('worker', Quarantined)

    def test_post_exit_release_failure_keeps_all_teardown_blocked(self):
        self.assert_no_teardown_or_success_after_failure('release', Quarantined)

    def test_foreign_cu_parent_cannot_reach_teardown(self):
        self.assert_no_teardown_or_success_after_failure('cu_parent', RuntimeError)

    def test_top_level_failure_parks_held_manager(self):
        obj = SimpleNamespace(run=lambda: (_ for _ in ()).throw(RuntimeError('fixture failure')),
                              held_locks=[object()], park=park)
        with patch.object(trial, 'IsolatedIdleTrial', return_value=obj), self.assertRaises(Quarantined):
            trial.main(['--execute-authorized-idle-once', '--source', str(self.obj.source),
                        '--review-sha256', 'c' * 64])


if __name__ == '__main__':
    unittest.main()
