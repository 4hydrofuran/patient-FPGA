"""Linux local cooperative control; supervisor never touches hardware or leases.

The worker keeps ownership while blocked. No terminate/kill/reset/retry API.
Control is a datagram socket in a private directory, not a command shell.
"""
import json
import multiprocessing as mp
import os
from pathlib import Path
import selectors
import socket
import stat
import struct
import time

MAX_MESSAGE = 4096


class CloseRequested(Exception):
    pass


class ControlLost(Exception):
    pass


class WorkerLink:
    def __init__(self, pipe, close_event, heartbeat, lifetime, journal=None):
        self.pipe, self.close_event, self.heartbeat = pipe, close_event, heartbeat
        self.deadline = time.monotonic() + lifetime
        self.cleaning = False
        self.journal = Path(journal) if journal is not None else None

    def publish(self, phase, **fields):
        raw = json.dumps(dict(phase=phase, monotonic_ns=time.monotonic_ns(), **fields)).encode()
        if len(raw) > MAX_MESSAGE:
            raise ValueError('Worker event too large')
        if self.journal is not None:
            fd = os.open(self.journal, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW)
            with os.fdopen(fd, 'ab') as stream:
                stream.write(raw + b'\n'); stream.flush(); os.fsync(stream.fileno())
        self.pipe.send_bytes(raw)

    def checkpoint(self):
        if time.monotonic() - self.heartbeat.value > 3:
            raise ControlLost('Supervisor heartbeat lost; retain ownership, no new mutation')
        if not self.cleaning and (self.close_event.is_set() or time.monotonic() >= self.deadline):
            raise CloseRequested('Cooperative close requested or maintenance deadline reached')


def _worker(entry, config, pipe, close_event, heartbeat, lifetime, journal=None):
    link = WorkerLink(pipe, close_event, heartbeat, lifetime, journal)
    try:
        code = entry(config, link)
    except BaseException as exc:
        try:
            link.publish('QUARANTINED_UNEXPECTED_ENTRY_FAILURE', error=(type(exc).__name__ + ': ' + str(exc))[:1000])
        except (BrokenPipeError, EOFError, OSError, ValueError):
            pass
        # Unexpected failure cannot certify cleanup. In particular, a broken
        # control pipe must not turn into process exit and release real flocks.
        while True:
            time.sleep(.1)
    finally:
        pipe.close()
    raise SystemExit(code)


def validate_request(request, binding, uid, expected_uid):
    if uid != expected_uid or not isinstance(request, dict):
        raise ValueError('Peer identity refused')
    if set(request) != {'binding', 'operation'} or request['binding'] != binding:
        raise ValueError('Wrong or stale window binding')
    if request['operation'] not in ('status', 'close'):
        raise ValueError('Only status and cooperative close are supported')
    return request['operation']


class Supervisor:
    def __init__(self, directory, binding, entry, config=None, lifetime=600):
        if os.name != 'posix' or not hasattr(socket, 'SCM_CREDENTIALS'):
            raise RuntimeError('Linux Unix credentials required')
        self.directory = Path(directory)
        info = self.directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('Control directory must be owned, private, and not a symlink')
        self.path = self.directory / 'control.sock'
        self.close_receipt = self.directory / 'close-request.json'
        self.journal = self.directory / 'worker-events.jsonl'
        if any(os.path.lexists(path) for path in (self.path, self.close_receipt, self.journal)):
            raise FileExistsError('Never replace an existing endpoint')
        if not isinstance(binding, str) or not 16 <= len(binding) <= 200:
            raise ValueError('Explicit immutable window binding required')
        if not isinstance(lifetime, (float, int)) or not 0 < lifetime <= 600:
            raise ValueError('Maintenance lifetime must be positive and at most 600s')
        self.binding, self.uid = binding, os.getuid()
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
        self.socket.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.socket.setblocking(False)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.socket, selectors.EVENT_READ)
        ctx = mp.get_context('spawn')
        parent, child = ctx.Pipe(duplex=False)
        self.pipe = parent
        self.close_event, self.heartbeat = ctx.Event(), ctx.Value('d', time.monotonic(), lock=False)
        fd = os.open(self.journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        self.worker = ctx.Process(target=_worker, args=(entry, config, child, self.close_event, self.heartbeat, lifetime, str(self.journal)))
        self.state = dict(phase='STARTING', close_requested=False, safe_release=False,
                          worker_exit_code=None, worker_pid=None, mutation_authority='WORKER_ONLY')
        self.eof = False
        self.last_progress = time.monotonic()
        self.worker.start()
        child.close()
        self.state['worker_pid'] = self.worker.pid

    def tick(self, timeout=0.02):
        self.heartbeat.value = time.monotonic()
        # Bound event work so a busy worker cannot starve control requests.
        for _ in range(16):
            if self.eof or not self.pipe.poll():
                break
            try:
                raw = self.pipe.recv_bytes(MAX_MESSAGE)
            except EOFError:
                self.eof = True
                break
            event = json.loads(raw)
            if not isinstance(event, dict) or not isinstance(event.get('phase'), str):
                raise ValueError('Malformed worker event')
            # A worker cannot certify independent release through this protocol.
            event.pop('safe_release', None)
            event.pop('close_requested', None)
            event.pop('worker_pid', None)
            event.pop('worker_exit_code', None)
            self.state.update(event)
            self.last_progress = time.monotonic()
        if self.worker.exitcode is not None:
            self.state['worker_exit_code'] = self.worker.exitcode
        self.state['worker_event_age_s'] = time.monotonic() - self.last_progress
        for _, _mask in self.selector.select(timeout):
            data, ancillary, flags, address = self.socket.recvmsg(MAX_MESSAGE, socket.CMSG_SPACE(12))
            try:
                if flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
                    raise ValueError('Oversized request')
                peers = [struct.unpack('3i', value[:12]) for level, kind, value in ancillary
                         if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS]
                if len(peers) != 1:
                    raise ValueError('Missing peer credentials')
                operation = validate_request(json.loads(data), self.binding, peers[0][1], self.uid)
                if operation == 'close':
                    if not self.close_event.is_set():
                        # Persist intent before worker observes it. Status has
                        # no scanner, hardware callback, or filesystem writes.
                        with self.close_receipt.open('x', encoding='utf-8') as stream:
                            json.dump(dict(binding=self.binding, operation='close', peer_pid=peers[0][0],
                                           peer_uid=peers[0][1], monotonic_ns=time.monotonic_ns()), stream)
                            stream.flush()
                            os.fsync(stream.fileno())
                        fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                        try:
                            os.fsync(fd)
                        finally:
                            os.close(fd)
                    self.close_event.set()
                    self.state['close_requested'] = True
                reply = dict(accepted=True, **self.state)
            except (ValueError, TypeError, UnicodeError, OSError) as exc:
                reply = dict(accepted=False, error=str(exc), safe_release=False)
            if address:
                try:
                    self.socket.sendto(json.dumps(reply).encode(), address)
                except (BlockingIOError, ConnectionRefusedError, FileNotFoundError):
                    pass
        return dict(self.state)

    def close_endpoint_after_worker_exit(self):
        if self.worker.exitcode is None:
            raise RuntimeError('Worker still owns state; endpoint must remain available')
        self.worker.join()
        self.selector.close()
        self.socket.close()
        self.pipe.close()
        self.path.unlink()


def request(endpoint, client_path, binding, operation, timeout=1):
    """Local only; caller creates its own private directory and unique path."""
    client_path = Path(client_path)
    if os.path.lexists(client_path):
        raise FileExistsError(client_path)
    with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
        sock.bind(str(client_path))
        os.chmod(client_path, 0o600)
        try:
            sock.settimeout(timeout)
            sock.sendto(json.dumps(dict(binding=binding, operation=operation)).encode(), str(endpoint))
            return json.loads(sock.recv(MAX_MESSAGE))
        finally:
            client_path.unlink()
