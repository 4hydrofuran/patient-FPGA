"""PC-only request-boundary journal experiment; never a board entry point.

The inherited permission loop, fresh owner/health checks and sequence decisions
remain unchanged. This experiment changes durability semantics deliberately:
an incomplete BEGIN is uncertain, and must never authorize replay or release.
"""
from collections import deque
import hashlib
import json
import os
import platform
import re
import threading


class RequestJournalBlocked(RuntimeError):
    pass


class RequestJournalCandidate:
    """Mixin for the frozen CPU-control fixture's OwnedWorker only.

    A caller must independently validate the native result before end_request;
    counts passed here are assertions, not hardware completion evidence.
    No board binding, automatic recovery, permit batching or cached health.
    """
    def __init__(self, *args, **kwargs):
        if (kwargs.get('real', False) is not False or os.name != 'posix'
                or platform.machine().lower() not in ('x86_64', 'amd64')):
            raise RequestJournalBlocked('PC-only candidate refuses real workers')
        self._request_lock = threading.RLock()
        self._active_request = None
        self._request_failed = False
        self._used_request_ids = set()
        self._recent_submits = deque(maxlen=64)
        super().__init__(*args, **kwargs)

    def _fail(self, reason):
        self._request_failed = True
        self.quarantined = True
        self._durable(event='REQUEST_FAULT_PC_CANDIDATE_RETAIN_OWNER', reason=reason,
                      incomplete_request=self._active_request is not None,
                      recent_submits=list(self._recent_submits), release_platform_lease=False)
        raise RequestJournalBlocked(reason + '; retain owner, no replay')

    def _durable(self, **row):
        try:
            super().record(**row)
        except BaseException:
            self._request_failed = True
            self.quarantined = True
            raise

    def begin_request(self, request_id, max_submits):
        with self._request_lock:
            if (self._request_failed or self.quarantined or self.closed or self.delivery_cancelled
                    or self._active_request is not None):
                self._fail('request cannot begin in current state')
            if (type(request_id) is not str or re.fullmatch(r'[A-Za-z0-9_-]{1,48}', request_id) is None
                    or request_id in self._used_request_ids or len(self._used_request_ids) >= 3
                    or type(max_submits) is not int or not 1 <= max_submits <= 5000
                    or self.runs + max_submits > self.max_runs):
                self._fail('invalid/reused request identity or budget')
            self._durable(event='REQUEST_BEGIN_PC_CANDIDATE', request_id=request_id,
                          max_submits=max_submits, base_permits=self.runs,
                          incomplete_means='UNKNOWN_RETAIN_OWNER_NO_REPLAY',
                          production_default=False)
            self._active_request = dict(id=request_id, budget=max_submits, base=self.runs,
                                        permits=0, digest=hashlib.sha256())
            self._used_request_ids.add(request_id)
            self._recent_submits.clear()

    def before_permission(self, request):
        with self._request_lock:
            if self._request_failed:
                self._fail('candidate failure latched')
            if request['phase'] == 'submit':
                active = self._active_request
                if active is None or active['permits'] >= active['budget']:
                    self._fail('submit outside bounded request')
            if request['phase'] == 'router_close' and self._active_request is not None:
                self._fail('close before request completion validation')

    def record(self, **row):
        with self._request_lock:
            request = row.get('request', {})
            if row.get('event') == 'PERMISSION' and request.get('phase') == 'submit' and row.get('allow') is True:
                active = self._active_request
                if (self._request_failed or active is None
                        or self.runs - active['base'] != active['permits'] + 1
                        or active['permits'] >= active['budget']):
                    self._fail('submit accounting differs before permission reply')
                # Constant-size fields only; do not retain nested health snapshots.
                item = dict(sequence=request['sequence'], job=request['job'], pid=request['pid'])
                encoded = json.dumps(item, sort_keys=True, separators=(',', ':')).encode() + b'\n'
                active['digest'].update(encoded)
                active['permits'] += 1
                self._recent_submits.append(item)
                return
            if (row.get('event') == 'PERMISSION' and row.get('allow') is False
                    or row.get('event') in ('PERMISSION_FAULT_RETAIN_OWNER', 'BAD_WORKER_PROTOCOL',
                                            'CANCEL_PENDING_NO_KILL', 'LATE_RESULT_DISCARDED')):
                self._request_failed = True
                self.quarantined = True
                row = dict(row, candidate_incomplete=self._active_request is not None,
                           recent_submits=list(self._recent_submits), release_platform_lease=False)
            self._durable(**row)

    def end_request(self, request_id, *, cumulative_completions, pending, state_cleared, outcome):
        with self._request_lock:
            active = self._active_request
            if (self._request_failed or self.quarantined or self.delivery_cancelled or active is None
                    or request_id != active['id'] or type(cumulative_completions) is not int
                    or cumulative_completions != self.runs or type(pending) is not int or pending != 0
                    or state_cleared is not True or outcome != 'VALIDATED'
                    or active['permits'] == 0 or self.runs - active['base'] != active['permits']):
                self._fail('request result incomplete or not independently validated')
            self._durable(event='REQUEST_END_PC_CANDIDATE', request_id=request_id,
                          permit_count=active['permits'], cumulative_permits=self.runs,
                          caller_asserted_cumulative_completions=cumulative_completions,
                          pending=pending, state_cleared=state_cleared,
                          permit_sha256=active['digest'].hexdigest(),
                          recent_submits=list(self._recent_submits),
                          overwritten_submits=max(0, active['permits'] - 64),
                          completion_domain='PC_CONTROL_FIXTURE_NOT_HARDWARE')
            self._active_request = None

    def close(self, timeout=3):
        with self._request_lock:
            if self._request_failed or self._active_request is not None:
                self._request_failed = True
                self.quarantined = True
                self._durable(event='CANDIDATE_CLOSE_REFUSED_RETAIN_OWNER',
                              incomplete_request=self._active_request is not None,
                              release_platform_lease=False)
                return False
        return super().close(timeout=timeout)
