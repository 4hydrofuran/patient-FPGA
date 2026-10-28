"""PC-tested component for a future, freshly authorized idle XRT controller.

NOT a board entry point. Does not import XRT or know PL/module commands.
The caller owns the lease/dual lock fds for the entire lifecycle, supplies an
identity/lock/consumer-isolation check, and a non-returning quarantine callback.
That callback must retain the controller and locks, not unwind them on failure.
No child kill/terminate, retries, inherited lock fds, or timeout-as-success.
Only the no-compute protocol is accepted; the old N32 executor is not reused.
"""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import time

from accelerator_release_gate_v2 import require_release


PROTOCOL = "a10-isolated-idle-worker-v1"


class IdleWorkerBoundary:
    def __init__(self, request, result_path, *, guard, quarantine, emit):
        required = {"boot_id", "window_id", "lease_sha256", "request_sha256"}
        if set(request) != required or not all(type(v) is str and v for v in request.values()):
            raise ValueError("incomplete fresh worker identity")
        for key in ("lease_sha256", "request_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", request[key]):
                raise ValueError("invalid digest")
        self.identity = dict(request, protocol=PROTOCOL, manager_pid=os.getpid())
        self.result_path = Path(result_path)
        self.guard, self.quarantine, self.emit = guard, quarantine, emit
        self.state, self.process, self.exited_ns = "NEW", None, None
        self.logs = []

    def block(self, reason):
        self.state = "QUARANTINED"
        try:
            self.emit("WORKER_BOUNDARY_BLOCKED", reason=reason,
                      worker_pid=self.process.pid if self.process is not None else None,
                      no_kill=True, retain_manager_lease_and_locks=True)
        finally:
            # A full/broken evidence disk must not skip quarantine either.
            self.quarantine(reason)  # Must not return in a hardware controller.
        raise RuntimeError("INTEGRATION_ERROR_QUARANTINE_RETURNED")

    def event(self, name, **data):
        try:
            self.emit(name, **data)
        except Exception as exc:
            self.block("EVIDENCE_WRITE_FAILED: " + str(exc))

    def checked_guard(self):
        try:
            if self.guard(dict(self.identity)) is not True:
                raise RuntimeError("boot/lease/dual-lock/consumer isolation not verified")
        except Exception as exc:
            self.block("CONTROLLER_GUARD: " + str(exc))

    def start(self, reviewed_argv, *, stdout_path, stderr_path, cwd=None):
        """Caller must pin/review the worker, dependencies and fresh manifest.

        stdout/stderr are files, not undrained pipes. Files are reserved with x
        before spawning. This generic launcher is not authorization to execute
        arbitrary input from a handoff. No callable is forked from the manager.
        """
        if self.state != "NEW":
            self.block("WORKER_REPLAY_FORBIDDEN")
        self.state = "START_RESERVED"
        self.checked_guard()
        try:
            if not reviewed_argv or not all(type(v) is str for v in reviewed_argv):
                raise ValueError("reviewed argv required")
            if os.path.lexists(self.result_path):
                raise ValueError("result already exists (no replay)")
            for path in (stdout_path, stderr_path):
                self.logs.append(Path(path).open("xb"))
            argv = list(reviewed_argv) + ["--a10-boundary-request", json.dumps(self.identity),
                                         "--a10-boundary-result", str(self.result_path.resolve())]
            self.process = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                            stdout=self.logs[0], stderr=self.logs[1],
                                            close_fds=True, cwd=cwd, shell=False)
            self.state = "RUNNING"
        except Exception as exc:
            self.block("WORKER_START_UNKNOWN: " + str(exc))
        self.event("ISOLATED_WORKER_STARTED", worker_pid=self.process.pid,
                   identity=self.identity, inherited_lock_fds=False)

    def wait_normal(self, timeout_s):
        if self.state != "RUNNING":
            self.block("WORKER_NOT_RUNNING")
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or timeout_s <= 0:
            self.block("INVALID_SOFT_DEADLINE")
        self.checked_guard()
        try:
            # Popen.wait raises on timeout but does not kill the worker. Never
            # replace with subprocess.run(timeout=...) or a Popen context manager.
            code = self.process.wait(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            self.block("WORKER_TIMEOUT_NO_KILL_NO_UNLOAD")
        except Exception as exc:
            self.block("WORKER_WAIT_UNKNOWN: " + str(exc))
        self.exited_ns = time.monotonic_ns()
        self.event("WORKER_REAPED", worker_pid=self.process.pid, exit_code=code,
                   monotonic_ns=self.exited_ns)
        try:
            for stream in self.logs:
                stream.close()
        except OSError as exc:
            self.block("EVIDENCE_CLOSE_FAILED: " + str(exc))
        if code != 0:
            self.block("WORKER_ABNORMAL_EXIT")
        self.checked_guard()
        try:
            if self.result_path.is_symlink() or self.result_path.stat().st_size > 16384:
                raise ValueError("invalid result file")
            result = json.loads(self.result_path.read_text(encoding="utf-8"))
            expected = dict(self.identity, worker_pid=self.process.pid,
                            status="NORMAL_CLOSED_NO_COMPUTE", normal_handles_closed=True,
                            real_submissions=0, explicit_bo_allocations=0)
            for key, value in expected.items():
                if type(result.get(key)) is not type(value) or result.get(key) != value:
                    raise ValueError("missing/mismatched worker result: " + key)
        except (OSError, ValueError, TypeError, AttributeError) as exc:
            self.block("WORKER_RESULT_UNPROVEN: " + str(exc))
        self.state = "EXITED_NORMAL"
        return result

    def check_release(self, observe, *, max_age_s=2):
        """One immediate pre-remove observation; not a reusable permission token.

        observe returns (complete process snapshot, actual module refcount,
        continuously latched kernel gate result). Caller must re-check kernel
        before/after each later mutation and keep lease/locks throughout.
        """
        if self.state != "EXITED_NORMAL":
            self.block("NORMAL_PROCESS_EXIT_REQUIRED_BEFORE_REMOVE")
        self.checked_guard()
        try:
            if type(max_age_s) not in (int, float) or not math.isfinite(max_age_s) or not 0 < max_age_s <= 2:
                raise ValueError("invalid release observation age limit")
            snapshot, refs, allowed = observe()
            now = time.monotonic_ns()
            begin, end = snapshot.get("scan_started_ns"), snapshot.get("scan_finished_ns")
            if (type(begin) is not int or type(end) is not int or
                    not self.exited_ns <= begin <= end <= now or now - begin > max_age_s * 1e9):
                raise ValueError("STALE_OR_PRE_EXIT_PROCESS_SCAN")
            require_release(snapshot, refs, allowed, boot_id=self.identity["boot_id"])
        except Exception as exc:
            self.block("RELEASE_REFUSED: " + str(exc))
        self.checked_guard()
        self.state = "RELEASE_PRECHECK_PASSED"
        self.event("RELEASE_PRECHECK_PASSED_NOT_UNLOADED", worker_pid=self.process.pid,
                   scan=snapshot, module_refcount=refs)
        return snapshot

