"""One-N32 result protocol on the proven no-kill process/lock boundary.

The idle boundary remains unchanged and cannot accept compute results.
"""
import json
import math
import re
import subprocess
import time

from single_compute_policy import PROTOCOL, validate_result
from xrt_worker_boundary import IdleWorkerBoundary


class SingleComputeBoundary(IdleWorkerBoundary):
    def __init__(self, request, result_path, **kwargs):
        extra = request.get('worker_baseline_sha256')
        if type(extra) is not str or not re.fullmatch(r'[0-9a-f]{64}', extra):
            raise ValueError('fresh parent-reviewed worker baseline pin required')
        super().__init__({k: v for k, v in request.items() if k != 'worker_baseline_sha256'}, result_path, **kwargs)
        self.identity.update(protocol=PROTOCOL, worker_baseline_sha256=extra)

    def wait_normal(self, timeout_s):
        if self.state != 'RUNNING':
            self.block('WORKER_NOT_RUNNING')
        if type(timeout_s) not in (int, float) or not math.isfinite(timeout_s) or not 0 < timeout_s <= 15:
            self.block('INVALID_SINGLE_COMPUTE_DEADLINE')
        self.checked_guard()
        try:
            code = self.process.wait(timeout=timeout_s)  # waitpid, never a kill-on-timeout API
        except subprocess.TimeoutExpired:
            self.block('WORKER_TIMEOUT_NO_KILL_NO_UNLOAD')
        except Exception as exc:
            self.block('WORKER_WAIT_UNKNOWN: ' + str(exc))
        self.exited_ns = time.monotonic_ns()
        self.event('WORKER_REAPED', worker_pid=self.process.pid, exit_code=code, monotonic_ns=self.exited_ns)
        try:
            for stream in self.logs:
                stream.close()
        except OSError as exc:
            self.block('EVIDENCE_CLOSE_FAILED: ' + str(exc))
        if code != 0:
            self.block('WORKER_ABNORMAL_EXIT')
        self.checked_guard()
        try:
            if self.result_path.is_symlink() or self.result_path.stat().st_size > 32768:
                raise ValueError('invalid single result file')
            result = json.loads(self.result_path.read_text(encoding='utf-8'))
            validate_result(result, self.identity, self.process.pid)
        except (OSError, ValueError, RuntimeError, TypeError, AttributeError) as exc:
            self.block('WORKER_RESULT_UNPROVEN: ' + str(exc))
        self.state = 'EXITED_NORMAL'
        return result
