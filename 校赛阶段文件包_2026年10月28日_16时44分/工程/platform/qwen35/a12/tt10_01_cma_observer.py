"""Synchronous diagnostic observations using the existing owner gate and latch."""
import json
import os
from pathlib import Path
import time
from tt10_01_diag_reader import DiagnosticBlocked

MEM_GATE = 1114112
CMA_GATE = 98304


def memory_snapshot(pids, *, full):
    observed = time.monotonic_ns()
    memory = {s.split(':')[0]: int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    required = ('MemAvailable', 'CmaFree', 'CmaTotal', 'Cached', 'Dirty', 'Writeback')
    if not all(k in memory for k in required):
        raise DiagnosticBlocked('required diagnostic memory counters missing')
    processes = {}
    for label, pid in pids.items():
        proc = Path('/proc') / str(pid)
        before = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
        status = {}
        for row in proc.joinpath('status').read_text().splitlines():
            key, _, value = row.partition(':')
            if key in ('VmRSS', 'RssAnon', 'RssFile', 'RssShmem'):
                status[key] = int(value.split()[0])
        if 'VmRSS' not in status:
            raise DiagnosticBlocked('process RSS unavailable')
        pss = None
        if full:
            smaps = proc / 'smaps_rollup'
            for row in smaps.read_text().splitlines():
                if row.startswith('Pss:'):
                    pss = int(row.split()[1])
            if pss is None:
                raise DiagnosticBlocked('process PSS unavailable')
        if proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] != before:
            raise DiagnosticBlocked('observed process identity changed')
        processes[label] = dict(pid=pid, start_ticks=int(before), rss_kib=status, pss_kib=pss,
            pss_observation='FRESH' if full else 'NOT_SAMPLED_THIS_FILE_EVENT')
    return dict(observed_monotonic_ns=observed, memory_kib={k: memory[k] for k in required}, processes=processes)


class PhaseObserver:
    def __init__(self, owner, worker, root, *, real, sample=memory_snapshot, clock=time.monotonic_ns):
        self.owner, self.worker, self.real = owner, worker, real
        self.sample, self.clock = sample, clock
        self.blocked = False
        self.closed = False
        self.busy = False
        self.expected_counts = (worker.runs, worker.loads, worker.sequence)
        self.last_gate_ns = 0
        self.last_gate_bytes = 0
        self.events = 0
        self.journal_bytes = 0
        self.advised_bytes = 0
        self.journal_advice_calls = 0
        self.fd = os.open(Path(root) / 'diagnostic-resources.jsonl',
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.journal_path = Path(root) / 'diagnostic-resources.jsonl'
        st = os.fstat(self.fd)
        self.journal_identity = st.st_dev, st.st_ino

    def _record(self, row, *, durable=False):
        st = os.stat(self.journal_path, follow_symlinks=False)
        if (st.st_dev, st.st_ino) != self.journal_identity or st.st_nlink != 1 or st.st_size != self.journal_bytes:
            raise DiagnosticBlocked('diagnostic observation journal replaced or changed')
        data = (json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':')) + '\n').encode()
        done = 0
        while done < len(data):
            n = os.write(self.fd, data[done:])
            if n <= 0:
                raise DiagnosticBlocked('diagnostic observation short write')
            done += n
        self.journal_bytes += done
        # Bound the cache of this newly-created writer-owned observation journal
        # too. Only its completed full pages are advised; original bytes remain.
        if durable or self.journal_bytes - self.advised_bytes >= 1048576:
            os.fsync(self.fd)
            page = os.sysconf('SC_PAGE_SIZE')
            end = self.journal_bytes // page * page
            if end > self.advised_bytes:
                os.posix_fadvise(self.fd, self.advised_bytes, end - self.advised_bytes, os.POSIX_FADV_DONTNEED)
                self.advised_bytes = end
                self.journal_advice_calls += 1

    def quiescent(self):
        w = self.worker
        if self.busy or w.process.poll() is not None or w.quarantined or w.delivery_cancelled or (w.runs, w.loads, w.sequence) != self.expected_counts:
            raise DiagnosticBlocked('completed quiescent worker or unchanged permit count not proven')
        return True

    def event(self, phase, *, force=False, fatal=False, **data):
        if self.closed:
            raise DiagnosticBlocked('diagnostic observer closed')
        p = self.owner.platform
        with p.gate_lock:
            row = dict(event=phase, monotonic_ns=self.clock(), sequence=self.events,
                host_permission_runs=self.worker.runs, weight_load_permissions=self.worker.loads,
                permission_messages=self.worker.sequence, **data)
            self.events += 1
            try:
                if fatal or self.blocked or p.health_schedule.blocked:
                    raise DiagnosticBlocked(data.get('reason', 'diagnostic/owner failure latched'))
                self.quiescent()
                count = data.get('total_read_bytes', self.last_gate_bytes)
                fresh = force or row['monotonic_ns'] - self.last_gate_ns >= 250000000 or count - self.last_gate_bytes >= 16777216
                row['sample'] = self.sample(dict(manager=os.getpid(), worker=self.worker.process.pid), full=fresh)
                mem = row['sample']['memory_kib']
                row['required_MemAvailable_kib'] = MEM_GATE
                row['required_CmaFree_kib'] = CMA_GATE
                if mem['MemAvailable'] < MEM_GATE or mem['CmaFree'] < CMA_GATE:
                    raise DiagnosticBlocked('diagnostic resource gate below unchanged minimum')
                if phase == 'FILE_BEFORE':
                    # Conservative phase admission, separately from the original
                    # minimum: file cache plus bounded manifest/hash/read workspace.
                    extra = (data['file_bytes'] + 1023) // 1024 + 8192
                    row['diagnostic_phase_planning_headroom_kib'] = extra
                    row['required_phase_CmaFree_kib'] = CMA_GATE + extra
                    row['required_phase_MemAvailable_kib'] = MEM_GATE + 8192
                    if mem['CmaFree'] < CMA_GATE + extra or mem['MemAvailable'] < MEM_GATE + 8192:
                        raise DiagnosticBlocked('diagnostic read phase lacks file/workspace headroom')
                if fresh:
                    self.owner.owner_check()
                    self.owner.health()  # Original fresh kernel, identity, temperature and reserve checks.
                    self.last_gate_ns = self.clock()
                    self.last_gate_bytes = count
                row['fresh_owner_health'] = fresh
                row['allowed'] = True
                self._record(row, durable=force)
            except BaseException as exc:
                self.blocked = True
                p.health_schedule.blocked = True
                row.update(allowed=False, failure_latched=True, reason=type(exc).__name__ + ': ' + str(exc))
                self._record(row, durable=True)
                raise

    def before_request(self, request):
        self.event('BEFORE_APPLICATION_SEND' if 'application' in request else 'BEFORE_DIAGNOSTIC_SEND',
            force=True, request_id=request['id'])
        self.busy = True

    def completed(self, result):
        if not self.busy or result.get('status') != 'OK' or result.get('state_cleared_before_response') is not True or result.get('state_position_after_clear') != -1:
            raise DiagnosticBlocked('completed result and clear state not proven')
        if self.real and result['bridge']['a12_route']['host_verified_completions'] != self.worker.runs:
            raise DiagnosticBlocked('completed PL count differs from permits')
        self.busy = False
        self.expected_counts = (self.worker.runs, self.worker.loads, self.worker.sequence)
        self.event('RESULT_QUIESCENT', force=True, request_id=result['id'])

    def close(self):
        if not self.closed:
            try:
                self._record(dict(event='DIAGNOSTIC_OBSERVER_CLOSED', monotonic_ns=self.clock(),
                    failure_latched=self.blocked, journal_bytes_before_close=self.journal_bytes,
                    journal_advice_calls=self.journal_advice_calls, cache_recovery_claimed=False), durable=True)
            finally:
                os.close(self.fd)
                self.closed = True


class ApplicationSendGate:
    """Run fresh admission at send(), inside the original application clock."""
    def __init__(self, worker, phase):
        self.worker, self.phase = worker, phase

    def send(self, request):
        self.phase.before_request(dict(request, application=True))
        return self.worker.send(request)

    def __getattr__(self, name):
        return getattr(self.worker, name)
