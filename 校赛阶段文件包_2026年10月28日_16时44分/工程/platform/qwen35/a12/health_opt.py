"""A-maintained health candidate: persistent read-only kmsg and fresh observations.

No device/XRT, permission, lifecycle or persistence policy is implemented here.
Any unreadable/malformed/lost record latches shut. Callers serialize access.
"""
import errno
import hashlib
import os
import re
from pathlib import Path
import threading
import time


class HealthBlocked(RuntimeError):
    pass


class PersistentKmsg:
    def __init__(self, path='/dev/kmsg', *, read=None, close=None, clock=time.monotonic_ns):
        self.fd = None
        if read is None:
            self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            read = lambda: os.read(self.fd, 1048576)
            close = lambda: os.close(self.fd)
        self._read, self._close, self.clock = read, close, clock
        self.previous_sequence = None
        self.raw = ''
        self.blocked = False
        self.closed = False
        self.records = 0
        self.drains = 0
        self.last_new_records = 0

    def fail(self, reason):
        self.blocked = True
        raise HealthBlocked(reason)

    @staticmethod
    def render(record):
        if not record or not record.endswith(b'\n'):
            raise ValueError('incomplete kmsg record')
        header, body = record.split(b';', 1)
        fields = header.split(b',')
        if len(fields) < 4 or fields[3] != b'-':
            raise ValueError('unsupported kmsg header/fragment')
        if any(not v.isdigit() for v in fields[:3]):
            raise ValueError('invalid kmsg numeric header')
        priority, sequence, microseconds = map(int, fields[:3])
        if not 0 <= priority <= 191 or not 0 <= sequence < 2**64:
            raise ValueError('kmsg numeric range')
        lines = body[:-1].split(b'\n')
        if not lines or any(not line.startswith(b' ') for line in lines[1:]):
            raise ValueError('invalid kmsg continuation metadata')
        # --raw dmesg excludes dictionary metadata; verify bytes at each boundary.
        sec, usec = divmod(microseconds, 1000000)
        # kmsg hex-escapes tabs, newlines, backslashes and non-ASCII bytes.
        # Decode once (never recursively) to match dmesg --raw on the pinned board.
        message=re.sub(rb'\\x([0-9a-fA-F]{2})',lambda m:bytes([int(m[1],16)]),lines[0]).decode('utf-8',errors='strict')
        # Pinned dmesg --raw emits non-kernel facilities as <7>.
        # Exact full-snapshot comparison is mandatory before accepting this reader.
        display_priority=priority if priority<8 else 7
        prefix=f'<{display_priority}>[{sec:5d}.{usec:06d}] '
        return sequence, prefix+message.replace('\n','\n'+' '*len(prefix))+'\n'

    def drain(self):
        if self.blocked or self.closed:
            self.fail('kmsg reader blocked/closed')
        start = self.clock()
        pieces = []
        size = 0
        self.last_new_records = 0
        try:
            for _ in range(8192):
                if self.clock() - start > 1000000000:
                    self.fail('kmsg drain deadline')
                try:
                    data = self._read()
                except BlockingIOError as exc:
                    if exc.errno != errno.EAGAIN:
                        raise
                    break
                sequence, rendered = self.render(data)
                if self.previous_sequence is not None and sequence != self.previous_sequence + 1:
                    self.fail('kmsg sequence lost/replayed')
                self.previous_sequence = sequence
                size += len(data)
                if size > 8388608:
                    self.fail('kmsg drain byte budget')
                pieces.append(rendered)
                self.records += 1
                self.last_new_records += 1
            else:
                self.fail('kmsg drain record budget')
            self.raw += ''.join(pieces)
            if len(self.raw.encode('utf-8')) > 8388608:
                self.fail('kmsg lifetime byte budget')
            if not self.raw:
                self.fail('empty kmsg baseline')
            self.drains += 1
            return self.raw
        except BaseException:
            self.blocked = True
            raise

    def assert_full_snapshot(self, raw):
        if self.drain() != raw:
            self.fail('kmsg/dmesg exact snapshot mismatch')

    def close(self):
        if not self.closed:
            self.closed = True
            if self._close:
                self._close()


class StableTemperatures:
    def __init__(self, root=Path('/sys/class/hwmon')):
        self.root = Path(root)
        self.paths = tuple(sorted(self.root.glob('hwmon*/temp*_input')))
        if not self.paths:
            raise HealthBlocked('temperature paths absent')
        self.identities = {p: (p.stat().st_dev, p.stat().st_ino) for p in self.paths}

    def read(self):
        values = []
        for p in self.paths:
            st = p.stat()
            if (st.st_dev, st.st_ino) != self.identities[p]:
                raise HealthBlocked('temperature path replaced')
            value = int(p.read_text())
            if not 0 < value < 55000:
                raise HealthBlocked('temperature gate')
            values.append(value)
        return values

    def verify_topology(self):
        if tuple(sorted(self.root.glob('hwmon*/temp*_input'))) != self.paths:
            raise HealthBlocked('temperature topology changed')


class HealthSchedule:
    """Per-permit observations stay fresh; idle checks do not contend with them."""
    def __init__(self, lock=None, clock=time.monotonic_ns):
        self.lock = lock or threading.RLock()
        self.clock = clock
        self.last_success_ns = 0
        self.blocked = False
        self.metrics = dict(fresh_calls=0, idle_checks=0, idle_skips=0,
                            lock_wait_ms=0.0, observation_ms=0.0)

    def fresh(self, observe):
        start = self.clock()
        with self.lock:
            acquired = self.clock()
            if self.blocked:
                raise HealthBlocked('health schedule latched')
            try:
                result = observe()
            except BaseException:
                self.blocked = True
                raise
            self.last_success_ns = self.clock()
            self.metrics['fresh_calls'] += 1
            self.metrics['lock_wait_ms'] += (acquired - start) / 1e6
            self.metrics['observation_ms'] += (self.last_success_ns - acquired) / 1e6
            return result

    def idle(self, observe, owner_check, max_age_ns=250000000):
        if self.blocked:
            raise HealthBlocked('health schedule latched')
        if not self.lock.acquire(blocking=False):
            self.metrics['idle_skips'] += 1
            return False
        try:
            if self.clock() - self.last_success_ns < max_age_ns:
                self.metrics['idle_skips'] += 1
                return False
            owner_check()
            self.fresh(observe)
            self.metrics['idle_checks'] += 1
            return True
        finally:
            self.lock.release()
