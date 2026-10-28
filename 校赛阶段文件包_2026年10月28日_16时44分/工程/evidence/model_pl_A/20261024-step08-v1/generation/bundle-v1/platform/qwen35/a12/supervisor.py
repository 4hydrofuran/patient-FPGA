"""Persistent A12 manager-side child ownership and synchronous permission protocol.

No platform load/unload/reboot implementation here. Hardware use requires an
already reviewed platform window, dual flocks, fresh lease and health callback.
Deadlines cancel delivery, never terminate the process or release its resources.
"""
import json
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import threading
import time


class OwnedWorker:
    def __init__(self, argv, *, directory, env, inherited_fds=(), health,
                 max_runs, max_loads, expires, real=False, owner_check=None):
        if real and owner_check is None:
            raise ValueError('real device worker requires fresh lock/lease owner check')
        if max_runs <= 0 or max_loads <= 0 or expires <= time.monotonic():
            raise ValueError('invalid bounded worker window')
        if owner_check:
            owner_check()
        self.directory=Path(directory);self.directory.mkdir(exist_ok=False,parents=True)
        self.real=real;self.health=health;self.owner_check=owner_check
        self.max_runs=max_runs;self.max_loads=max_loads;self.expires=expires
        self.runs=self.loads=self.sequence=0
        self.quarantined=False;self.delivery_cancelled=False;self.closed=False
        self.messages=queue.Queue();self.records=[];self._lock=threading.Lock()
        self.manager_sock, child_sock=socket.socketpair()
        child_env=dict(env,SP_A12_CONTROL_FD=str(child_sock.fileno()))
        self.stderr=(self.directory/'stderr.txt').open('x',encoding='utf-8')
        # The child inherits the SAME flock descriptions, not separately opened aliases.
        self.process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=self.stderr,text=True,encoding='utf-8',env=child_env,
            pass_fds=(*inherited_fds,child_sock.fileno()),bufsize=1)
        child_sock.close()
        self.permission_thread=threading.Thread(target=self._permissions,daemon=True)
        self.reader_thread=threading.Thread(target=self._reader,daemon=True)
        self.permission_thread.start();self.reader_thread.start()

    def record(self, **row):
        with self._lock:
            row=dict(monotonic_ns=time.monotonic_ns(),**row);self.records.append(row)
            with (self.directory/'events.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps(row,ensure_ascii=False)+'\n');stream.flush();os.fsync(stream.fileno())

    def _permissions(self):
        with self.manager_sock.makefile('r',encoding='utf-8') as stream:
            try:
                for line in stream:
                    if len(line)>4096:raise ValueError('oversized permit')
                    r=json.loads(line);self.sequence+=1
                    if r['sequence']!=self.sequence or r['pid']!=self.process.pid:
                        raise ValueError('stale/foreign permit')
                    phase=r['phase']
                    if phase not in ('router_open','device_open','weight_load','submit','router_close'):
                        raise ValueError('unknown phase')
                    if self.owner_check:self.owner_check()
                    closing=phase=='router_close'
                    self.health()
                    allowed=(not self.quarantined and (closing or
                             (not self.delivery_cancelled and time.monotonic()<self.expires)))
                    if phase=='submit':
                        allowed=allowed and self.runs<self.max_runs
                        if allowed:self.runs+=1
                    if phase=='weight_load':
                        allowed=allowed and self.loads<self.max_loads
                        if allowed:self.loads+=1
                    self.record(event='PERMISSION',request=r,allow=allowed)
                    reply=dict(sequence=self.sequence,allow=allowed)
                    self.manager_sock.sendall((json.dumps(reply)+'\n').encode())
            except BaseException as exc:
                self.quarantined=True
                self.record(event='PERMISSION_FAULT_RETAIN_OWNER',reason=type(exc).__name__+': '+str(exc))
                # Denial/disconnect never kills the worker or drops inherited lock FDs.
                try:self.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:pass

    def _reader(self):
        with (self.directory/'stdout.jsonl').open('x',encoding='utf-8') as log:
            for line in self.process.stdout:
                log.write(line);log.flush()
                try:self.messages.put(json.loads(line))
                except ValueError:
                    self.quarantined=True;self.record(event='BAD_WORKER_PROTOCOL')
            self.messages.put(None)

    def send(self, request):
        if self.quarantined or self.delivery_cancelled or self.closed:
            raise RuntimeError('worker isolated/cancelled/closed; no new request')
        self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()

    def get(self, timeout):
        try:r=self.messages.get(timeout=timeout)
        except queue.Empty:
            self.cancel('deadline');raise TimeoutError('worker retained; delivery cancelled')
        if r is None:
            self.quarantined=True;raise RuntimeError('unexpected worker EOF; retain platform ownership')
        if self.delivery_cancelled:
            self.record(event='LATE_RESULT_DISCARDED');raise RuntimeError('cancelled result unusable')
        return r

    def cancel(self, reason='user'):
        self.delivery_cancelled=True
        if self.process.poll() is None:self.process.send_signal(signal.SIGUSR1)
        self.record(event='CANCEL_PENDING_NO_KILL',reason=reason)

    def close(self, timeout=3):
        if self.closed:return True
        if self.quarantined:
            self.record(event='CLOSE_REFUSED_OWNER_RETAINED');return False
        if self.process.poll() is None:
            try:
                self.process.stdin.write('{"op":"shutdown"}\n');self.process.stdin.flush()
                self.process.wait(timeout=timeout)
            except (subprocess.TimeoutExpired,BrokenPipeError):
                self.quarantined=True;self.record(event='CLOSE_PENDING_NO_KILL');return False
        if self.process.returncode!=0:
            self.quarantined=True;self.record(event='BAD_EXIT_RETAIN_PLATFORM_OWNER',exit_code=self.process.returncode);return False
        self.permission_thread.join(timeout=1);self.reader_thread.join(timeout=1)
        self.closed=True;self.stderr.close();self.process.stdin.close();self.process.stdout.close();self.manager_sock.close()
        self.record(event='WORKER_EXITED_NORMALLY',exit_code=0,
                    release_platform_lease=False,requires_full_FD_VMA_refcount_kernel_gate=True)
        return True
