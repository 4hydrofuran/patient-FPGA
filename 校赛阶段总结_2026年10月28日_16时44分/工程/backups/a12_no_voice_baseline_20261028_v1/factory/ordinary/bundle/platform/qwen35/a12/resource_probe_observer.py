"""Bounded phase observations, separate from unchanged per-permit health checks."""
import json
import os
from pathlib import Path
import time
from resource_probe_policy import ProbeBlocked, admission, require


def memory_snapshot(pids):
    memory = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, rest = line.split(':', 1)
        if key in ('MemAvailable', 'CmaFree', 'CmaTotal', 'Cached', 'Dirty', 'Writeback'):
            memory[key] = int(rest.split()[0])
    processes = {}
    for label, pid in pids.items():
        proc = Path('/proc') / str(pid)
        before = proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19]
        values = {}
        for line in proc.joinpath('status').read_text().splitlines():
            key, _, rest = line.partition(':')
            if key in ('VmRSS', 'VmHWM'):
                values[key] = int(rest.split()[0])
        require('VmRSS' in values, 'RSS unavailable')
        # Three requests only: PSS at phase boundaries, never a per-file/per-projection loop.
        pss = None
        for line in proc.joinpath('smaps_rollup').read_text().splitlines():
            if line.startswith('Pss:'):
                pss = int(line.split()[1])
        require(pss is not None, 'PSS unavailable')
        require(proc.joinpath('stat').read_text().rsplit(')', 1)[1].split()[19] == before,
                'process identity changed during observation')
        processes[label] = dict(pid=pid, start_ticks=int(before), rss_kib=values, pss_kib=pss)
    return dict(memory_kib=memory, processes=processes)


class ResourceObserver:
    MAX_ROWS = 24
    MAX_ROW_BYTES = 8192

    def __init__(self, owner, worker, directory, *, sample=memory_snapshot, clock=time.monotonic_ns):
        self.owner, self.worker, self.sample, self.clock = owner, worker, sample, clock
        self.rows = self.bytes = 0
        self.minimum = {}
        self.blocked = False
        self.reason = None
        self.closed = False
        self.path = Path(directory) / 'probe-resources.jsonl'
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        self.identity = os.fstat(self.fd)
        try:
            parent = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            try:
                os.fsync(parent)
            finally:
                os.close(parent)
        except BaseException:
            os.close(self.fd)
            self.closed = True
            raise

    def _write(self, row):
        require(self.rows < self.MAX_ROWS, 'observation row budget exhausted')
        current, named = os.fstat(self.fd), self.path.lstat()
        require((current.st_dev, current.st_ino) == (named.st_dev, named.st_ino) ==
                (self.identity.st_dev, self.identity.st_ino) and current.st_nlink == named.st_nlink == 1 and
                current.st_size == self.bytes, 'observation journal identity/extent changed')
        data = (json.dumps(row, allow_nan=False, separators=(',', ':')) + '\n').encode()
        require(len(data) <= self.MAX_ROW_BYTES, 'observation row too large')
        view = memoryview(data)
        while view:
            n = os.write(self.fd, view)
            require(n > 0, 'observation short write made no progress')
            view = view[n:]
        os.fsync(self.fd)  # Phase boundaries only; original permission journal unchanged.
        self.rows += 1
        self.bytes += len(data)

    def latch(self, exc):
        self.blocked = True
        if self.reason is None:
            self.reason = type(exc).__name__ + ': ' + str(exc)
        self.owner.platform.health_schedule.blocked = True

    def checkpoint(self, phase, *, prefix=False):
        require(not self.closed and not self.blocked, 'resource probe already blocked/closed')
        begin = self.clock()
        snapshot = None
        try:
            self.owner.owner_check()
            self.owner.health()
            snapshot = self.sample(dict(manager=os.getpid(), worker=self.worker.process.pid))
            for key in ('CmaFree', 'MemAvailable'):
                self.minimum[key] = min(self.minimum.get(key, snapshot['memory_kib'][key]),
                                        snapshot['memory_kib'][key])
            admission(snapshot['memory_kib'], prefix=prefix)
            end = self.clock()
            self._write(dict(event=phase, sequence=self.rows, begin_monotonic_ns=begin,
                             end_monotonic_ns=end, observation_ms=(end-begin)/1e6,
                             permission_runs=self.worker.runs, weight_loads=self.worker.loads,
                             permission_messages=self.worker.sequence, prefix_reserve=prefix,
                             allowed=True, **snapshot))
            return snapshot
        except BaseException as exc:
            self.latch(exc)
            try:
                self._write(dict(event=phase, allowed=False, failure_latched=True,
                                 reason=self.reason, sample=snapshot, monotonic_ns=self.clock()))
            except BaseException:
                pass
            raise

    def close(self):
        if not self.closed:
            self.closed = True
            os.close(self.fd)
