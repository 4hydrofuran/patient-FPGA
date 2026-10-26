"""Resumable cleanup control; no hardware or network operations on import.

Only observation exhaustion is resumable. Mutation failures/unknown completion
are latched for manual reconciliation. Completed steps are never replayed.
"""
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import time

STEPS = ('takeover', 'remove_test', 'unload_module', 'load_default', 'start_graphics', 'finalize')


class ObservationDeferred(RuntimeError):
    """No action was started; a later explicit resume may obtain fresh reads."""


class UnknownCommand(RuntimeError):
    """May still be executing. Never retry, kill its child or release locks."""


def need(ok, message):
    if not ok:
        raise RuntimeError(message)


def observe_release(sample, emit, validate, boot, sleep=time.sleep):
    """Accept one *complete* strict scan, not an unchanged global process set.

    Exclusive locks, history, resource and kernel gates belong to the caller.
    A narrowly recognized incomplete proc snapshot can be sampled again, at
    most four times. No device user/ref/error is waived, even in partial scans.
    """
    for attempt in range(1, 5):
        scan, count, loaded = sample()
        emit(attempt, scan, count)
        need(scan.get('boot_id') == boot == scan.get('boot_id_after'), 'BOOT_CHANGED_OR_UNKNOWN')
        need(scan.get('schema') == 'a10-accelerator-scan-v2', 'SCAN_SCHEMA_UNKNOWN')
        need(scan.get('device_holders') == [] and scan.get('device_mappings') == [], 'DEVICE_OWNER_OR_UNKNOWN')
        need((type(count) is int and count == 0) if loaded else count is None, 'REFERENCE_STATE_UNSAFE')
        if scan.get('scan_complete') is True:
            validate(scan, count, loaded)  # Existing strict gate, not replaced.
            return scan
        need(scan.get('scan_complete') is False, 'SCAN_COMPLETENESS_UNKNOWN')
        issues = scan.get('scan_issues')
        need(type(issues) is list and bool(issues), 'MALFORMED_INCOMPLETE_SCAN')
        for issue in issues:
            reason = issue.get('reason', '')
            missing = re.fullmatch(r"FileNotFoundError: \[Errno 2\] No such file or directory: '/proc/(\d+)/(?:stat|maps|fd(?:/\d+)?)'", reason)
            need(reason == 'PROCESS_SET_CHANGED' or
                 (missing is not None and issue.get('pid') == int(missing.group(1))), 'NON_TRANSIENT_SCAN_ERROR')
        if attempt < 4:
            sleep(.5)
    raise ObservationDeferred('FOUR_INCOMPLETE_OBSERVATIONS_NO_ACTION_STARTED')


class Controller:
    def __init__(self, io):
        self.io = io
        self.index = 0
        self.state = 'READY'
        self.reason = None
        self.generation = 0
        self.consumed = set()
        self.inflight = None

    def status(self):
        return dict(state=self.state, reason=self.reason, generation=self.generation,
                    next_step=STEPS[self.index] if self.index < len(STEPS) else None,
                    completed_steps=list(STEPS[:self.index]), inflight=self.inflight,
                    compute_runs=0, acceptance='CLEANUP_ONLY_NOT_A11_PASS')

    def resume(self, authorization_id, generation):
        need(type(authorization_id) is str and re.fullmatch(r'[A-Za-z0-9_-]{8,80}', authorization_id), 'AUTHORIZATION_ID_REQUIRED')
        need(type(generation) is int and generation == self.generation, 'STALE_GENERATION')
        need(self.state in ('READY', 'PAUSED_READONLY'), 'NOT_RESUMABLE_RECONCILE_MANUALLY')
        need(authorization_id not in self.consumed, 'AUTHORIZATION_ALREADY_CONSUMED')
        self.consumed.add(authorization_id)
        self.generation += 1
        self.state, self.reason = 'RUNNING', None
        self.io.emit('CONTROL_RESUME', authorization_id=authorization_id, generation=self.generation,
                     next_step=STEPS[self.index])
        while self.index < len(STEPS):
            step = STEPS[self.index]
            try:
                self.io.gate(step)
            except ObservationDeferred as exc:
                self.state, self.reason = 'PAUSED_READONLY', str(exc)
                self.io.emit('CONTROL_PAUSED', **self.status())
                return self.status()
            except Exception as exc:
                return self.hard_stop(step, exc)
            try:
                # Write-ahead record; a crash here must not replay this step.
                self.inflight = step
                self.io.emit('STEP_BEGIN', step=step)
                self.io.apply(step)
                self.io.emit('STEP_COMMITTED', step=step)
                self.inflight = None
                self.index += 1
            except Exception as exc:
                return self.hard_stop(step, exc)
        self.state = 'COMPLETE_NEEDS_INDEPENDENT_READBACK'
        self.io.emit('CONTROL_COMPLETE', **self.status())
        return self.status()

    def hard_stop(self, step, error):
        self.state = 'HARD_STOP_RECONCILE_ONLY'
        self.reason = type(error).__name__ + ': ' + str(error)
        self.io.emit('CONTROL_HARD_STOP', step=step, **self.status())
        return self.status()


class ControlServer:
    """Local Unix socket only; retained controller/locks, explicit resume only.

    No arbitrary commands, TCP listener or automatic health/retry loop. A status
    query observes controller memory only. uid is injected only by PC tests;
    board caller fixes it to root. Unknown mutations stay latched.
    """
    def __init__(self, controller, directory, uid=0):
        self.controller = controller
        self.directory = Path(directory)
        self.uid = uid
        info = self.directory.lstat()
        need(stat.S_ISDIR(info.st_mode) and info.st_uid == uid and not info.st_mode & 0o077, 'UNTRUSTED_CONTROL_DIRECTORY')
        self.path = self.directory/'control.sock'
        need(not os.path.lexists(self.path), 'CONTROL_ENDPOINT_ALREADY_EXISTS_NO_TAKEOVER')
        self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket.bind(str(self.path))
        os.chmod(self.path, 0o600)
        self.inode = self.path.stat().st_ino
        self.socket.listen(1)
        self.socket.settimeout(1)

    def dispatch(self, request, peer_uid):
        need(peer_uid == self.uid, 'UNAUTHORIZED_CONTROL_PEER')
        need(type(request) is dict, 'INVALID_REQUEST')
        if request == {'action': 'status'}:
            return self.controller.status()
        need(set(request) == {'action','authorization_id','generation'} and request['action'] == 'resume', 'ACTION_NOT_ALLOWED')
        return self.controller.resume(request['authorization_id'], request['generation'])

    def serve_one(self):
        try:
            connection, _ = self.socket.accept()
        except socket.timeout:
            return
        with connection:
            connection.settimeout(1)
            try:
                _, uid, _ = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
                data = b''
                while not data.endswith(b'\n') and len(data) <= 2048:
                    part = connection.recv(2049-len(data))
                    if not part:
                        break
                    data += part
                need(len(data) <= 2048 and data.endswith(b'\n'), 'INCOMPLETE_OR_OVERSIZE_REQUEST')
                reply = self.dispatch(json.loads(data), uid)
            except Exception as exc:
                reply = {'error': type(exc).__name__+': '+str(exc), 'status': self.controller.status()}
            try:
                connection.sendall(json.dumps(reply).encode()+b'\n')
            except OSError:
                pass  # A disconnected client does not cancel/replay an action.

    def close(self):
        self.socket.close()
        info = self.path.lstat()
        need(stat.S_ISSOCK(info.st_mode) and info.st_ino == self.inode, 'CONTROL_ENDPOINT_CHANGED')
        self.path.unlink()  # Only this exact private socket, never a lock file.

    def run(self, authorization_id):
        self.controller.resume(authorization_id, 0)
        while self.controller.state != 'COMPLETE_NEEDS_INDEPENDENT_READBACK':
            self.serve_one()
        self.close()
