"""PC process/negative tests only. No XRT, UART, SSH or FPGA access."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import accelerator_release_gate_v2 as release
from xrt_worker_boundary import IdleWorkerBoundary


# A short-lived PC fixture, NOT the native worker and NOT board evidence.
CHILD = r'''
import argparse, json, os, pathlib, sys, time
p = argparse.ArgumentParser()
p.add_argument('--mode', default='normal')
p.add_argument('--gate-file')
p.add_argument('--probe-fd', type=int)
p.add_argument('--a10-boundary-request')
p.add_argument('--a10-boundary-result')
a = p.parse_args()
if a.probe_fd is not None:
    try: os.fstat(a.probe_fd); inherited = True
    except OSError: inherited = False
else: inherited = None
if a.gate_file:
    until = time.monotonic() + 4
    while not pathlib.Path(a.gate_file).exists() and time.monotonic() < until:
        time.sleep(0.01)
if a.mode == 'nonzero': sys.exit(3)
if a.mode == 'missing': sys.exit(0)
r = json.loads(a.a10_boundary_request)
r.update(worker_pid=os.getpid(), status='NORMAL_CLOSED_NO_COMPUTE',
         normal_handles_closed=True, real_submissions=0, explicit_bo_allocations=0,
         inherited_probe_fd=inherited)
changes = {'wrong_pid': ('worker_pid', -1), 'old_boot': ('boot_id', 'old'),
           'old_request': ('request_sha256', 'e'*64), 'old_lease': ('lease_sha256', 'e'*64),
           'old_window': ('window_id', 'consumed'), 'wrong_manager': ('manager_pid', -1),
           'false_zero': ('real_submissions', False), 'compute': ('real_submissions', 1),
           'bo': ('explicit_bo_allocations', 1), 'not_closed': ('normal_handles_closed', False)}
if a.mode in changes:
    key, value = changes[a.mode]; r[key] = value
with open(a.a10_boundary_result, 'x') as f: json.dump(r, f)
'''


class Parked(Exception):
    pass


def park(reason):
    raise Parked(reason)


def clear_snapshot():
    now = time.monotonic_ns()
    return dict(schema=release.SCHEMA, boot_id="test-boot", boot_id_after="test-boot",
                scan_complete=True, scan_issues=[], device_holders=[], device_mappings=[],
                inspected_processes=[dict(pid=os.getpid(), start_ticks=123)],
                scan_started_ns=now, scan_finished_ns=now)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jobs = []

    def tearDown(self):
        # Fixtures have no devices and exit themselves when this file appears;
        # never kill even the fake workers in the timeout tests.
        (self.root / "fixture-gate").touch()
        for job in self.jobs:
            if job.process is not None:
                job.process.wait(timeout=6)
            for stream in job.logs:
                stream.close()
        self.temp.cleanup()

    def job(self, guard=lambda identity: True):
        n = str(len(self.jobs))
        events = []
        job = IdleWorkerBoundary(dict(boot_id="test-boot", window_id="fresh-test-" + n,
                                      lease_sha256="a" * 64, request_sha256="b" * 64),
                                 self.root / (n + ".result.json"), guard=guard,
                                 quarantine=park, emit=lambda event, **data: events.append((event, data)))
        job.events = events
        self.jobs.append(job)
        return job

    def start(self, job, mode="normal", extra=()):
        n = str(self.jobs.index(job))
        # Windows venv python.exe is a redirector with a different child PID.
        # Exercise the real interpreter; keep the production identity check strict.
        job.start([sys._base_executable, "-B", "-c", CHILD, "--mode", mode, *extra],
                  stdout_path=self.root / (n + ".stdout"), stderr_path=self.root / (n + ".stderr"))

    def normal(self):
        job = self.job()
        self.start(job)
        self.assertEqual(job.wait_normal(5)["real_submissions"], 0)
        return job

    def test_real_pc_child_normal_exit_then_fresh_gate(self):
        job = self.normal()
        job.check_release(lambda: (clear_snapshot(), 0, True))
        self.assertEqual(job.state, "RELEASE_PRECHECK_PASSED")
        self.assertLess([x[0] for x in job.events].index("WORKER_REAPED"),
                        [x[0] for x in job.events].index("RELEASE_PRECHECK_PASSED_NOT_UNLOADED"))

    def test_timeout_never_kills_and_is_latched(self):
        job = self.job()
        self.start(job, extra=("--gate-file", str(self.root / "fixture-gate")))
        with patch.object(job.process, "kill", side_effect=AssertionError("kill forbidden")), \
                patch.object(job.process, "terminate", side_effect=AssertionError("terminate forbidden")):
            with self.assertRaisesRegex(Parked, "TIMEOUT"):
                job.wait_normal(0.01)
        self.assertIsNone(job.process.poll())
        with self.assertRaises(Parked):
            job.check_release(lambda: (clear_snapshot(), 0, True))
        with self.assertRaises(Parked):
            job.wait_normal(1)

    def test_abnormal_missing_or_wrong_result_refused(self):
        for mode in ("nonzero", "missing", "wrong_pid", "old_boot", "old_window", "old_lease",
                     "old_request", "wrong_manager", "false_zero", "compute", "bo", "not_closed"):
            with self.subTest(mode=mode):
                job = self.job()
                self.start(job, mode)
                with self.assertRaises(Parked):
                    job.wait_normal(5)
                self.assertEqual(job.state, "QUARANTINED")

    def test_no_release_before_waitpid_even_with_file(self):
        job = self.job()
        with self.assertRaisesRegex(Parked, "PROCESS_EXIT"):
            job.check_release(lambda: (clear_snapshot(), 0, True))

    def test_cannot_replay_or_reuse_existing_result(self):
        job = self.normal()
        with self.assertRaisesRegex(Parked, "REPLAY"):
            self.start(job)
        other = self.job()
        other.result_path.write_text("preserved")
        with self.assertRaisesRegex(Parked, "already exists"):
            self.start(other)
        self.assertIsNone(other.process)
        self.assertEqual(other.result_path.read_text(), "preserved")

    def test_guard_failure_before_launch_and_after_exit(self):
        job = self.job(lambda identity: False)
        with self.assertRaises(Parked):
            self.start(job)
        self.assertIsNone(job.process)
        job = self.normal()
        job.guard = lambda identity: False
        with self.assertRaises(Parked):
            job.check_release(lambda: (clear_snapshot(), 0, True))

    def test_stale_snapshot_and_kernel_failure_stay_blocked(self):
        old = clear_snapshot()
        job = self.normal()
        with self.assertRaisesRegex(Parked, "STALE"):
            job.check_release(lambda: (old, 0, True))
        job = self.normal()
        with self.assertRaisesRegex(Parked, "KERNEL_GATE"):
            job.check_release(lambda: (clear_snapshot(), 0, False))
        with self.assertRaises(Parked):
            job.check_release(lambda: (clear_snapshot(), 0, True))

    def test_launch_closes_fds_without_forking_native_context(self):
        job = self.job()
        from subprocess import Popen
        with patch("xrt_worker_boundary.subprocess.Popen", wraps=Popen) as spawned:
            self.start(job)
        job.wait_normal(5)
        self.assertIs(spawned.call_args.kwargs["close_fds"], True)
        self.assertIs(spawned.call_args.kwargs["shell"], False)
        self.assertNotIn("pass_fds", spawned.call_args.kwargs)

    def test_log_failure_still_calls_quarantine(self):
        job = self.job()
        def broken_log(*args, **kwargs):
            raise OSError("synthetic full evidence disk")
        job.emit = broken_log
        with self.assertRaisesRegex(Parked, "EVIDENCE_WRITE_FAILED"):
            self.start(job)
        self.assertEqual(job.state, "QUARANTINED")

    def test_bad_identity_fails_before_start(self):
        for request in ({}, dict(boot_id="b", window_id="w", lease_sha256=False, request_sha256="a" * 64)):
            with self.assertRaises(ValueError):
                IdleWorkerBoundary(request, self.root / "unused", guard=lambda x: True,
                                   quarantine=park, emit=lambda *a, **k: None)

    @unittest.skipUnless(os.name == "posix", "POSIX dual-lock timeout retention checked in WSL")
    def test_timeout_keeps_both_manager_locks(self):
        import fcntl
        from contextlib import ExitStack
        with ExitStack() as stack:
            paths = [self.root / "deployment.lock", self.root / "shared.lock"]
            for path in paths:
                stream = stack.enter_context(path.open("wb"))
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            job = self.job()
            self.start(job, extra=("--gate-file", str(self.root / "fixture-gate")))
            with self.assertRaises(Parked):
                job.wait_normal(0.01)
            for path in paths:
                with path.open("rb") as competing:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (self.root / "fixture-gate").touch()
            job.process.wait(timeout=5)  # fixture exits itself, NOT a hardware recovery

    @unittest.skipUnless(os.name == "posix", "POSIX flock inheritance checked in WSL PC run")
    def test_actual_posix_lock_stays_parent_owned_not_inherited(self):
        import fcntl
        with (self.root / "lock").open("wb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.set_inheritable(lock.fileno(), True)
            job = self.job()
            self.start(job, extra=("--probe-fd", str(lock.fileno()),
                                   "--gate-file", str(self.root / "fixture-gate")))
            with (self.root / "lock").open("rb") as competing:
                with self.assertRaises(BlockingIOError):
                    fcntl.flock(competing, fcntl.LOCK_EX | fcntl.LOCK_NB)
            (self.root / "fixture-gate").touch()
            result = job.wait_normal(5)
            self.assertIs(result["inherited_probe_fd"], False)


class ReleaseTests(unittest.TestCase):
    def check(self, snapshot, refs=0, kernel=True):
        release.require_release(snapshot, refs, kernel, boot_id="test-boot")

    def test_deleted_maps_and_primary_cards(self):
        for path in ("/dev/dri/renderD129 (deleted)", "/dev/dri/card1", "/dev/zocl", "/dev/uio0"):
            row = "7000-8000 rw-s 00000000 00:06 33 " + path
            self.assertEqual(release.mapped_accelerators(row), [row])
            s = clear_snapshot()
            s["device_mappings"] = [row]
            with self.assertRaisesRegex(RuntimeError, "VMA"):
                self.check(s)

    def test_missing_or_partial_observation_refuses(self):
        for key in ("schema", "scan_complete", "boot_id", "boot_id_after", "scan_issues",
                    "device_holders", "device_mappings", "inspected_processes"):
            s = clear_snapshot()
            del s[key]
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                self.check(s)
        for key, value in (("scan_complete", False), ("scan_issues", ["permission denied"]),
                           ("device_holders", ["render"]), ("inspected_processes", [])):
            s = clear_snapshot()
            s[key] = value
            with self.assertRaises(RuntimeError):
                self.check(s)

    def test_refcount_requires_actual_integer_zero(self):
        for value in (None, False, True, 0.0, "0", 1, -1):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                self.check(clear_snapshot(), value)
        self.check(clear_snapshot(), 0)

    def test_kernel_gate_is_not_a_truthy_value(self):
        for value in (False, None, 1, "allowed"):
            with self.assertRaises(RuntimeError):
                self.check(clear_snapshot(), kernel=value)

    def test_readonly_proc_fixture_scan_and_permission_race(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            boot = root / "sys/kernel/random/boot_id"
            boot.parent.mkdir(parents=True)
            boot.write_text("test-boot\n")
            proc = root / "123"
            (proc / "fd").mkdir(parents=True)
            (proc / "stat").write_text("123 (worker) " + " ".join(["S"] + ["0"] * 18 + ["456"] + ["0"] * 4))
            (proc / "maps").write_text("7000-8000 rw-p 0 00:00 0\n")
            self.check(release.collect(root))
            with patch.object(release, "start_ticks", side_effect=PermissionError("denied")):
                s = release.collect(root)
            self.assertFalse(s["scan_complete"])
            with self.assertRaises(RuntimeError):
                self.check(s)
            with patch.object(release, "start_ticks", side_effect=[456, 789]):
                s = release.collect(root)
            self.assertFalse(s["scan_complete"])
            (proc / "maps").unlink()
            self.assertFalse(release.collect(root)["scan_complete"])

    def test_real_peer_vma_snapshot_blocks_even_after_fds_closed(self):
        root = Path(__file__).resolve().parents[3]
        source = root / "A10_refcount_交付包_20261023/A10_refcount_handoff_20261023/evidence/02_repaired_trial/final_fault_profile.json"
        data = json.loads(source.read_text(encoding="utf-8"))
        stopped = data["postcompute_stop"]
        rows = release.mapped_accelerators(stopped["maps"])
        self.assertTrue(rows)
        self.assertTrue(any("(deleted)" in row for row in rows))
        s = clear_snapshot()
        s["device_mappings"] = rows
        with self.assertRaisesRegex(RuntimeError, "VMA"):
            self.check(s, 0)
        # Even clearing mappings cannot erase the recorded kernel gate failure.
        s["device_mappings"] = []
        with self.assertRaisesRegex(RuntimeError, "KERNEL_GATE"):
            self.check(s, 0, False)


if __name__ == "__main__":
    unittest.main()
