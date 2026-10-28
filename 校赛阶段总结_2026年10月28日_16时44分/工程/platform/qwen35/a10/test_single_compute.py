"""PC-only ctypes-memory and real child/lock tests; no XRT library or board."""
import copy
import ctypes as C
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

import isolated_single_trial as controller
import single_compute_policy as policy
import single_compute_worker as worker
from single_compute_boundary import SingleComputeBoundary
from test_xrt_worker_boundary import clear_snapshot


class Parked(BaseException):
    pass


def park(reason):
    raise Parked(reason)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeAPI:
    """Explicit PC memory substitute; never included in a candidate bundle."""
    def __init__(self, *, fail=None, fault=None, clock=None):
        self.calls, self.arrays, self.handles, self.args = [], [], [], {}
        self.fail, self.fault, self.clock = fail, fault, clock or Clock()
        self.polls = 0

    def __getattr__(self, name):
        def call(*args):
            self.calls.append(name)
            self.clock.now += 0.0001
            if self.fail == name:
                return 0 if name in ('xrtDeviceOpen', 'xrtPLKernelOpenExclusive', 'xrtBOAlloc', 'xrtBOMap', 'xrtRunOpen') else -1
            if name == 'xrtDeviceOpen':
                return 11
            if name == 'xrtDeviceGetXclbinUUID':
                data = bytes(16) if self.fault == 'uuid' else uuid.UUID(policy.XCLBIN_UUID).bytes
                for n, value in enumerate(data):
                    args[1][n] = value
            if name == 'xrtPLKernelOpenExclusive':
                return 22
            if name == 'xrtKernelArgGroupId':
                return 4 if self.fault == 'group' else 3
            if name == 'xrtBOAlloc':
                assert args[1:] == (policy.BO_BYTES, 0, 3)
                self.arrays.append((C.c_uint32*policy.WORDS)())
                self.handles.append(100+len(self.arrays))
                return self.handles[-1]
            if name == 'xrtBOAddress':
                if self.fault == 'high_address':
                    return 0x80000000
                if self.fault == 'overlap':
                    return 0x445b0000
                return 0x445b0000+self.handles.index(args[0])*0x8000
            if name == 'xrtBOSize':
                return policy.BO_BYTES+4 if self.fault == 'size' else policy.BO_BYTES
            if name == 'xrtBOMap':
                return C.addressof(self.arrays[self.handles.index(args[0])])
            if name == 'xrtRunOpen':
                return 33
            if name == 'xrtRunSetArg':
                self.args[args[1]] = args[2].value
                assert isinstance(args[2], C.c_uint32 if args[1] == 3 else C.c_void_p)
            if name == 'xrtRunStart':
                assert self.args == {0: 101, 1: 102, 2: 103, 3: 32}
                for n in range(policy.N):
                    # The mock's explicit PC arithmetic is not board evidence.
                    self.arrays[2][n] = C.c_uint32(self.arrays[0][n]+self.arrays[1][n]).value
                if self.fault == 'numeric':
                    self.arrays[2][0] ^= 1
                if self.fault == 'guard':
                    self.arrays[2][-1] = 0
            if name == 'xrtRunState':
                self.polls += 1
                if self.fault == 'timeout':
                    return 3
                if self.fault == 'error_state':
                    return 5
                return 3 if self.polls == 1 else 4
            return 0
        return call


class NativeTests(unittest.TestCase):
    def execute(self, api, checkpoint=lambda p: None, emit_delay=0):
        events = []
        def emit(event, **data):
            events.append(dict(event=event, **data))
            api.clock.now += emit_delay
        result = worker.run_single(api, Path('PC_FIXTURE_NOT_XCLBIN'), policy.vector(), emit, checkpoint, park,
                                   clock=api.clock, sleep=api.clock.sleep,
                                   memory_reader=lambda phase, live: dict(phase=phase, explicit_requested_live_bytes=live))
        return result, events

    def test_one_submission_real_mapped_PC_arrays_close_order_and_ledger(self):
        api = FakeAPI()
        result, events = self.execute(api)
        self.assertEqual(api.calls.count('xrtRunStart'), 1)
        self.assertEqual(api.calls.count('xrtBOAlloc'), 3)
        self.assertEqual(api.calls[-6:], ['xrtRunClose', 'xrtBOFree', 'xrtBOFree', 'xrtBOFree', 'xrtKernelClose', 'xrtDeviceClose'])
        self.assertEqual(result['actual_output'], policy.vector()['expected'])
        self.assertEqual(result['guards_checked'], 4080)
        self.assertEqual(result['observed_states'], [3, 4])
        self.assertEqual([r['explicit_requested_live_bytes'] for r in events if r['event'] == 'MEMORY_OBSERVATION'],
                         [0, 49344, 0])
        self.assertIsNone(result['physical_bo_peak_bytes'])

    def test_every_failed_native_call_prevents_any_followup_close(self):
        normal = FakeAPI()
        self.execute(normal)
        for name in sorted(set(normal.calls)):
            api = FakeAPI(fail=name)
            with self.subTest(call=name), self.assertRaises(Parked):
                self.execute(api)
            self.assertEqual(api.calls[-1], name)

    def test_wrong_uuid_group_size_or_address_stops_before_submission(self):
        for fault in ('uuid', 'group', 'size', 'high_address', 'overlap'):
            api = FakeAPI(fault=fault)
            with self.subTest(fault=fault), self.assertRaises(Parked):
                self.execute(api)
            self.assertNotIn('xrtRunStart', api.calls)
            self.assertNotIn('xrtBOFree', api.calls)

    def test_numeric_guard_or_error_state_never_grants_teardown(self):
        for fault in ('numeric', 'guard', 'error_state'):
            api = FakeAPI(fault=fault)
            with self.subTest(fault=fault), self.assertRaises(Parked):
                self.execute(api)
            self.assertEqual(api.calls.count('xrtRunStart'), 1)
            self.assertNotIn('xrtRunClose', api.calls)

    def test_timeout_never_restarts_aborts_or_closes(self):
        api = FakeAPI(fault='timeout')
        with self.assertRaisesRegex(Parked, 'DEADLINE'):
            self.execute(api)
        self.assertEqual(api.calls.count('xrtRunStart'), 1)
        self.assertLessEqual(api.polls, 500)
        self.assertNotIn('xrtRunClose', api.calls)

    def test_kernel_checkpoint_failure_stops_before_next_native_action(self):
        for phase in ('before_native', 'before_submit', 'after_positive_completion', 'before_normal_handle_close'):
            api = FakeAPI()
            def checkpoint(current):
                if current == phase:
                    raise RuntimeError('PC injected kernel failure')
            with self.subTest(phase=phase), self.assertRaises(Parked):
                self.execute(api, checkpoint)
            self.assertNotIn('xrtRunClose', api.calls)
            if phase in ('before_native', 'before_submit'):
                self.assertNotIn('xrtRunStart', api.calls)

    def test_sync_timing_excludes_event_logging_and_labels_wall_time(self):
        result, _ = self.execute(FakeAPI(), emit_delay=0.005)
        self.assertAlmostEqual(result['sync_in_native_call_total_us'], 300, places=6)
        self.assertAlmostEqual(result['sync_out_native_call_us'], 100, places=6)
        self.assertGreater(result['sync_in_inclusive_wall_us'], 30000)

    def test_default_worker_and_manager_do_not_read_board_or_load_XRT(self):
        with patch.object(worker, 'SingleNativeAPI', side_effect=AssertionError('native forbidden')), \
                patch.object(Path, 'read_text', side_effect=AssertionError('read forbidden')), \
                patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(worker.main([]), 0)
            self.assertEqual(controller.main([]), 0)

    def test_actual_native_bindings_have_no_abort_reset_or_repeat_entry(self):
        class Function:
            pass
        class Library:
            def __init__(self):
                self.names = []
            def __getattr__(self, name):
                self.names.append(name)
                return Function()
        lib = Library()
        with patch.object(worker.C, 'CDLL', return_value=lib):
            api = worker.SingleNativeAPI()
        self.assertEqual(api.xrtRunSetArg.argtypes, [C.c_void_p, C.c_int])
        self.assertEqual(api.xrtBOAlloc.argtypes, [C.c_void_p, C.c_size_t, C.c_uint64, C.c_uint32])
        self.assertFalse(any('Abort' in n or 'Reset' in n or 'Wait' in n for n in lib.names))


def review():
    return dict(schema='A10_ISOLATED_SINGLE_REVIEW_V1', scope=policy.SCOPE, compute_authorized=True,
                authorized=True, allow_gdm_stop_restore=True, max_submissions=1, n=32,
                explicit_bo_budget_bytes=49344, boot_id=str(uuid.uuid4()), kernel=policy.KERNEL,
                machine_sha256=policy.MACHINE, window_id='a10-isolated-single-20261023-v9001',
                baseline_sha256='a'*64, bundle_sha256='b'*64, prior_idle_audit_sha256='c'*64,
                baseline_read_uptime_ns=time.monotonic_ns())


class PolicyTests(unittest.TestCase):
    def test_scope_cannot_expand_or_reuse_idle_approval(self):
        policy.validate_review(review())
        changes = (dict(scope='A10_XRT_IDLE_ISOLATED_ONCE'), dict(compute_authorized=False),
                   dict(max_submissions=2), dict(max_submissions=True), dict(n=64),
                   dict(explicit_bo_budget_bytes=1000000), dict(prior_idle_audit_sha256=''),
                   dict(window_id='a10-isolated-idle-20261023-v4'), dict(authorized=False))
        for change in changes:
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                policy.validate_review(dict(review(), **change))

    def test_vector_matches_preserved_historical_inputs_not_using_actual_as_reference(self):
        root = Path(__file__).resolve().parents[3]
        old = policy.load_json(root/'evidence/board_platform/A10_20261023_peer_intake/received_board_files/actual_output.json')
        v = policy.vector()
        self.assertEqual(v['input_a'], old['input_a'])
        self.assertEqual(v['input_b'], old['input_b'])
        self.assertEqual(v['expected'], [C.c_uint32(a+b).value for a, b in zip(v['input_a'], v['input_b'])])

    def test_worker_baseline_rejects_tamper_wrong_identity_or_stale_approval(self):
        with tempfile.TemporaryDirectory(prefix='a10-baseline-pc-') as td:
            root = Path(td)
            raw = root/'worker-baseline.raw.txt'
            meta = root/'worker-baseline.json'
            identity = dict(boot_id=str(uuid.uuid4()), window_id='pc-window', manager_pid=42,
                            lease_sha256='a'*64, request_sha256='b'*64)
            def setup(**changes):
                raw.write_bytes(b'<6>[1.0] PC fixture baseline\n')
                ready = dict(identity, raw_sha256=policy.digest(raw), read_monotonic_ns=100,
                             kernel_gate_allowed=True)
                ready.update(changes)
                meta.write_text(json.dumps(ready))
                return dict(identity, worker_baseline_sha256=policy.digest(meta))
            approved = setup()
            self.assertFalse(worker.worker_baseline(root, approved, identity, now_ns=101).blocked)
            for changes in (dict(kernel_gate_allowed=False), dict(manager_pid=43),
                            dict(read_monotonic_ns=True), dict(read_monotonic_ns=200),
                            dict(raw_sha256='0'*64)):
                with self.subTest(changes=changes), self.assertRaises(RuntimeError):
                    worker.worker_baseline(root, setup(**changes), identity, now_ns=101)
            approved = setup()
            with self.assertRaises(RuntimeError):
                worker.worker_baseline(root, approved, identity, now_ns=10_000_000_101)
            raw.write_bytes(b'changed')
            with self.assertRaises(RuntimeError):
                worker.worker_baseline(root, approved, identity, now_ns=101)
            approved = setup()
            meta.write_text('{}')
            with self.assertRaises(RuntimeError):
                worker.worker_baseline(root, approved, identity, now_ns=101)


CHILD = r'''
import argparse,json,os,time
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('--mode',default='normal')
p.add_argument('--gate-file')
p.add_argument('--a10-boundary-request')
p.add_argument('--a10-boundary-result')
a=p.parse_args()
request=json.loads(a.a10_boundary_request)
if a.gate_file:
    while not Path(a.gate_file).exists(): time.sleep(0.005)
if a.mode=='nonzero': raise SystemExit(2)
if a.mode=='missing': raise SystemExit(0)
x=[(0x80000000+7*8191+n*65537)%(1<<32) for n in range(32)]
y=[(0x7fffffff-7*127+n*17)%(1<<32) for n in range(32)]
r=dict(request,worker_pid=os.getpid(),status='NORMAL_CLOSED_ONE_N32',normal_handles_closed=True,
       real_submissions=1,explicit_bo_allocations=3,explicit_requested_peak_bytes=49344,
       job=7,n=32,pass_numeric=True,completion_state=4,guards_checked=4080,
       input_a=x,input_b=y,actual_output=[(v+w)%(1<<32) for v,w in zip(x,y)],
       changed_guard_indices=[],groups=[3,3,3],physical_bo_peak_bytes=None,PC_FIXTURE_ONLY=True)
if a.mode=='wrong_pid': r['worker_pid']+=1
if a.mode=='bad_numeric': r['actual_output'][0]^=1
if a.mode=='two_runs': r['real_submissions']=2
if a.mode=='not_closed': r['normal_handles_closed']=False
if a.mode=='idle': r.update(status='NORMAL_CLOSED_NO_COMPUTE',real_submissions=0)
if a.mode=='wrong_baseline': r['worker_baseline_sha256']='0'*64
Path(a.a10_boundary_result).write_text(json.dumps(r))
'''


class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='a10-single-pc-')
        self.addCleanup(self.temp.cleanup)
        self.root, self.jobs = Path(self.temp.name), []
        self.addCleanup(self.close_jobs)

    def close_jobs(self):
        (self.root/'fixture-gate').touch()  # lets ONLY the no-XRT PC fixture exit itself
        for job in self.jobs:
            if job.process is not None:
                job.process.wait(timeout=5)
            for stream in job.logs:
                stream.close()

    def job(self):
        request = dict(boot_id='pc-boot', window_id='pc-window', lease_sha256='a'*64,
                       request_sha256='b'*64, worker_baseline_sha256='c'*64)
        obj = SingleComputeBoundary(request, self.root/(str(len(self.jobs))+'.json'),
                                    guard=lambda identity: True, quarantine=park, emit=lambda *a, **k: None)
        self.jobs.append(obj)
        return obj

    def start(self, job, mode='normal', gate=False):
        argv = [sys._base_executable, '-B', '-I', '-c', CHILD, '--mode', mode]
        if gate:
            argv += ['--gate-file', str(self.root/'fixture-gate')]
        n = str(self.jobs.index(job))
        job.start(argv, stdout_path=self.root/(n+'.out'), stderr_path=self.root/(n+'.err'))

    def test_real_PC_child_exit_required_before_release(self):
        job = self.job()
        self.start(job)
        result = job.wait_normal(5)
        self.assertTrue(result['PC_FIXTURE_ONLY'])
        def observe():
            s = clear_snapshot()
            s.update(boot_id='pc-boot', boot_id_after='pc-boot')
            return s, 0, True
        job.check_release(observe)
        self.assertEqual(job.state, 'RELEASE_PRECHECK_PASSED')

    def test_bad_result_identity_counts_or_actual_output_never_release(self):
        for mode in ('nonzero', 'missing', 'wrong_pid', 'bad_numeric', 'two_runs', 'not_closed', 'idle', 'wrong_baseline'):
            job = self.job()
            self.start(job, mode)
            with self.subTest(mode=mode), self.assertRaises(Parked):
                job.wait_normal(5)
            self.assertEqual(job.state, 'QUARANTINED')

    def test_timeout_no_kill_no_replay_no_release(self):
        job = self.job()
        self.start(job, gate=True)
        with patch.object(job.process, 'kill', side_effect=AssertionError('kill forbidden')), \
                patch.object(job.process, 'terminate', side_effect=AssertionError('terminate forbidden')):
            with self.assertRaisesRegex(Parked, 'TIMEOUT'):
                job.wait_normal(0.01)
        self.assertIsNone(job.process.poll())
        with self.assertRaises(Parked):
            job.check_release(lambda: self.fail('must not scan/release'))
        with self.assertRaises(Parked):
            self.start(job)

    @unittest.skipUnless(os.name == 'posix', 'actual temporary Linux flock')
    def test_timeout_keeps_dual_locks_in_parent(self):
        import fcntl
        from contextlib import ExitStack
        with ExitStack() as stack:
            paths = [self.root/'deployment.lock', self.root/'shared.lock']
            for path in paths:
                stream = stack.enter_context(path.open('wb'))
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            job = self.job()
            self.start(job, gate=True)
            with self.assertRaises(Parked):
                job.wait_normal(0.01)
            for path in paths:
                with path.open('rb') as other:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (self.root/'fixture-gate').touch()
            job.process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
