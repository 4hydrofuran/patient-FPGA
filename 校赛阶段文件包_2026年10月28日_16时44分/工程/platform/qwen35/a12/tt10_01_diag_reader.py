"""A-private Linux reader for completed diagnostics in one new owned window.

Only the allowlisted diag files receive fsync/fadvise. Raw bytes are never
changed. The caller must prove a completed, quiescent request before each scan.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
from functools import wraps

CHUNK = 1048576
MAX_FILE = 33554432
MAX_MANIFEST = 1048576
CASES = ('diag_exact', 'warm_prefix', 'diag_full_R0', 'diag_hit')


class DiagnosticBlocked(RuntimeError):
    pass


def latched(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except BaseException as exc:
            self.blocked = True
            if not getattr(self, '_failure_recorded', False):
                self._failure_recorded = True
                try:
                    self.observe('READ_FAILED', fatal=True, operation=method.__name__,
                        reason=type(exc).__name__ + ': ' + str(exc))
                except BaseException:
                    pass  # Preserve the original failure; the owner remains latched.
            raise
    return call


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns,
            st.st_uid, stat.S_IMODE(st.st_mode), st.st_nlink)


def leaf(name):
    if not isinstance(name, str) or not name or name in ('.', '..') or '/' in name or '\\' in name or '\x00' in name:
        raise DiagnosticBlocked('diagnostic filename is not a simple leaf')
    return name


def directory(path):
    """Open every ancestor without following symlinks, retaining the last FD."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise DiagnosticBlocked('absolute diagnostic root required')
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for part in path.parts[1:]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return fd
    except BaseException:
        os.close(fd)
        raise


class DiagnosticReader:
    def __init__(self, root, observe, *, expected_uid=0):
        if not hasattr(os, 'posix_fadvise') or not hasattr(os, 'O_NOFOLLOW'):
            raise DiagnosticBlocked('Linux fsync/fadvise and no-follow opens required')
        self.root = Path(root)
        self.observe = observe
        self.uid = expected_uid
        self.blocked = False
        self.closed = False
        self.cases = {}
        self.total_bytes = 0
        self.total_files = 0
        self.root_fd = directory(self.root)
        try:
            self.root_id = self._dir_identity(self.root_fd)
            self._root_check()
        except BaseException:
            os.close(self.root_fd)
            raise

    def _dir_identity(self, fd):
        st = os.fstat(fd)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != self.uid or st.st_mode & 0o022:
            raise DiagnosticBlocked('diagnostic directory owner/mode differs')
        return st.st_dev, st.st_ino

    def _root_check(self):
        if self.closed or self.blocked:
            raise DiagnosticBlocked('diagnostic reader closed or latched')
        fd = directory(self.root)
        try:
            if self._dir_identity(fd) != self.root_id:
                raise DiagnosticBlocked('diagnostic window root replaced')
        finally:
            os.close(fd)

    def _case_check(self, name):
        self._root_check()
        c = self.cases[name]
        for parent, child, expected in ((self.root_fd, name, c['case_id']), (c['case_fd'], 'diag', c['diag_id'])):
            st = os.stat(child, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(st.st_mode) or (st.st_dev, st.st_ino) != expected or st.st_uid != self.uid or st.st_mode & 0o022:
                raise DiagnosticBlocked('diagnostic directory replaced or writable by others')

    def _regular(self, st):
        if not stat.S_ISREG(st.st_mode) or st.st_uid != self.uid or st.st_nlink != 1 or st.st_mode & 0o022:
            raise DiagnosticBlocked('diagnostic requires private owned regular file with one link')
        return identity(st)

    @latched
    def begin(self, name, *, completed, quiescent):
        if name not in CASES or name in self.cases or completed is not True or quiescent is not True:
            raise DiagnosticBlocked('new completed and quiescent diagnostic case required')
        self._root_check()
        case_fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.root_fd)
        try:
            diag_fd = os.open('diag', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=case_fd)
            try:
                self.cases[name] = dict(case_fd=case_fd, diag_fd=diag_fd,
                    case_id=self._dir_identity(case_fd), diag_id=self._dir_identity(diag_fd),
                    allowed={'manifest.json': None}, files={}, identities={}, finished=False)
            except BaseException:
                os.close(diag_fd)
                raise
        except BaseException:
            os.close(case_fd)
            raise
        raw = self.read(name, 'manifest.json', capture=True, maximum=MAX_MANIFEST)
        manifest = json.loads(raw)
        sizes = {}
        def allow(n, size):
            n = leaf(n)
            if n in sizes or n == 'manifest.json' or type(size) is not int or not 0 < size <= MAX_FILE:
                raise DiagnosticBlocked('duplicate or out-of-budget diagnostic file')
            sizes[n] = size
        for row in manifest['projections']:
            if not isinstance(row['id'], str) or not row['id']:
                raise DiagnosticBlocked('projection ID missing')
            for key in ('T', 'K', 'N'):
                if type(row[key]) is not int or row[key] <= 0:
                    raise DiagnosticBlocked('invalid projection dimensions')
            allow(row['input'], row['T'] * row['K'] * 4)
            allow(row['output'], row['T'] * row['N'] * 4)
        positions = set()
        for row in manifest['logits']:
            if type(row['position']) is not int or row['position'] < 0 or row['position'] in positions:
                raise DiagnosticBlocked('logit position invalid or duplicated')
            positions.add(row['position'])
            # Runtime's pinned Qwen3.5 vocabulary: 248320 float32 logits.
            allow(row['file'], 993280)
        allow('hybrid-state.bin', self._size(name, 'hybrid-state.bin'))
        if len(sizes) > 8191 or sum(sizes.values()) > 1073741824:
            raise DiagnosticBlocked('diagnostic case exceeds file/byte budget')
        self.cases[name]['allowed'].update(sizes)
        self.cases[name]['manifest'] = manifest
        if set(os.listdir(self.cases[name]['diag_fd'])) != set(self.cases[name]['allowed']):
            raise DiagnosticBlocked('diagnostic filename set differs from manifest and state')
        return manifest

    def _size(self, name, filename):
        st = os.stat(leaf(filename), dir_fd=self.cases[name]['diag_fd'], follow_symlinks=False)
        self._regular(st)
        return st.st_size

    @latched
    def read(self, name, filename, update=None, *, capture=False, maximum=MAX_FILE):
        filename = leaf(filename)
        c = self.cases[name]
        if filename not in c['allowed'] or filename in c['files'] or c['finished']:
            raise DiagnosticBlocked('file not allowlisted or already consumed')
        fd = None
        try:
            self._case_check(name)
            before = os.stat(filename, dir_fd=c['diag_fd'], follow_symlinks=False)
            signature = self._regular(before)
            expected = c['allowed'][filename]
            if not 0 < before.st_size <= maximum or expected is not None and before.st_size != expected:
                raise DiagnosticBlocked('diagnostic file size differs or exceeds budget')
            if capture and filename != 'manifest.json':
                raise DiagnosticBlocked('only the bounded manifest may be captured')
            self.observe('FILE_BEFORE', case=name, file=filename, file_bytes=before.st_size)
            fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=c['diag_fd'])
            if self._regular(os.fstat(fd)) != signature:
                raise DiagnosticBlocked('diagnostic changed during open')
            os.fsync(fd)
            self.observe('FILE_SYNCED', case=name, file=filename)
            h = hashlib.sha256()
            total = 0
            pieces = []
            while True:
                block = os.read(fd, CHUNK)
                if not block:
                    break
                total += len(block)
                if total > before.st_size:
                    raise DiagnosticBlocked('diagnostic grew during read')
                h.update(block)
                if update is not None:
                    update(block)
                if capture:
                    pieces.append(block)
                self.observe('READ_PROGRESS', case=name, file=filename, file_read_bytes=total,
                    total_read_bytes=self.total_bytes + total)
            if total != before.st_size or self._regular(os.fstat(fd)) != signature:
                raise DiagnosticBlocked('diagnostic truncated or changed during read')
            self._case_check(name)
            if self._regular(os.stat(filename, dir_fd=c['diag_fd'], follow_symlinks=False)) != signature:
                raise DiagnosticBlocked('diagnostic path replaced during read')
            self.observe('FILE_READ', case=name, file=filename, file_read_bytes=total)
            # Same FD as the full read; offset=0,length=0 means through EOF.
            # Successful advice is logged, never interpreted as recovered CMA.
            advice_result = os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
            self.observe('FILE_ADVISED', case=name, file=filename, file_read_bytes=total,
                advice='POSIX_FADV_DONTNEED', advice_python_return=advice_result,
                advice_succeeded=True, recovery_proven=False)
            if self._regular(os.fstat(fd)) != signature or self._regular(os.stat(filename, dir_fd=c['diag_fd'], follow_symlinks=False)) != signature:
                raise DiagnosticBlocked('diagnostic changed during advice')
            self.total_bytes += total
            self.total_files += 1
            c['files'][filename] = dict(bytes=total, sha256=h.hexdigest())
            c['identities'][filename] = signature
            return b''.join(pieces) if capture else c['files'][filename]
        finally:
            if fd is not None:
                os.close(fd)

    @latched
    def finish(self, name):
        c = self.cases[name]
        if set(c['files']) != set(c['allowed']):
            raise DiagnosticBlocked('not all original diagnostic files consumed')
        self.verify(name)
        c['finished'] = True
        return dict(files=dict(c['files']), raw_files=len(c['files']),
            raw_bytes=sum(x['bytes'] for x in c['files'].values()),
            full_originals_retained=True, original_directory=str(self.root / name / 'diag'), read_passes_per_file=1,
            advice_is_not_recovery_proof=True)

    @latched
    def verify(self, name=None):
        for n in ([name] if name else self.cases):
            self._case_check(n)
            c = self.cases[n]
            if set(os.listdir(c['diag_fd'])) != set(c['allowed']):
                raise DiagnosticBlocked('diagnostic filename set changed')
            for filename, signature in c['identities'].items():
                if self._regular(os.stat(filename, dir_fd=c['diag_fd'], follow_symlinks=False)) != signature:
                    raise DiagnosticBlocked('completed diagnostic identity changed')

    def close(self):
        if not self.closed:
            for c in self.cases.values():
                os.close(c['diag_fd'])
                os.close(c['case_fd'])
            os.close(self.root_fd)
            self.closed = True


class NumericalStreams:
    """Keep hash states, not raw arrays. Each input byte is visited once."""
    def __init__(self):
        self.projections = {}
        self.logits = {}
        self.records = 0
        self.state = None

    def scan(self, reader, name, *, completed, quiescent):
        manifest = reader.begin(name, completed=completed, quiescent=quiescent)
        for row in manifest['projections']:
            for kind in ('input', 'output'):
                key = str((row['id'], kind))
                h = self.projections.setdefault(key, hashlib.sha256())
                reader.read(name, row[kind], h.update)
            self.records += 1
        for row in manifest['logits']:
            key = str(row['position'])
            if key in self.logits:
                raise DiagnosticBlocked('duplicate logit position across prefix and suffix')
            self.logits[key] = reader.read(name, row['file'])['sha256']
        self.state = reader.read(name, 'hybrid-state.bin')['sha256']
        return reader.finish(name)

    def compare(self, joined):
        if not self.projections or not joined.projections or not self.logits or not joined.logits or self.state is None or joined.state is None:
            raise DiagnosticBlocked('complete numerical streams and states required')
        a = {k: v.hexdigest() for k, v in self.projections.items()}
        b = {k: v.hexdigest() for k, v in joined.projections.items()}
        al, bl = self.logits, joined.logits
        differences = {k: [a.get(k), b.get(k)] for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
        ld = {k: [al.get(k), bl.get(k)] for k in al.keys() | bl.keys() if al.get(k) != bl.get(k)}
        return dict(equal=not differences and not ld and self.state == joined.state,
            projection_difference=differences, logits_difference=ld, prefill_state_equal=self.state == joined.state,
            projection_streams=len(a), full_logit_vectors=len(al), reference_projection_records=self.records,
            actual_projection_records=joined.records, reference_projection_sha256=a, restored_projection_sha256=b,
            reference_logits_sha256=al, restored_logits_sha256=bl,
            reference_state_sha256=self.state, restored_state_sha256=joined.state)
