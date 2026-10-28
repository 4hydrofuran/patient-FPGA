import cpu01b_observer as ob
"""A12 single-projection owner: independent DSO sequence lanes, strict phase order."""
import json
import socket
import time
from cpu01b_supervisor_base import OwnedWorker as BaseWorker

class PermissionOrder:

    def __init__(self):
        self.sequence = {'router': 0, 'backend': 0}
        self.router = False
        self.device = False
        self.closed = False
        self.weights = 0
        self.last_job = 0

    def check(self, r, pid):
        phase = r['phase']
        if phase not in ('router_open', 'device_open', 'weight_load', 'submit', 'router_close'):
            raise ValueError('unknown phase')
        lane = 'router' if phase.startswith('router_') else 'backend'
        if r['pid'] != pid or type(r['sequence']) is not int or r['sequence'] != self.sequence[lane] + 1:
            raise ValueError('stale/foreign per-DSO permit')
        if self.closed:
            raise ValueError('permit after router close')
        if phase == 'router_open' and (self.router or r['job'] != 0):
            raise ValueError('duplicate router open')
        if phase != 'router_open' and (not self.router):
            raise ValueError('router not opened')
        if phase == 'device_open' and (self.device or r['job'] != 0):
            raise ValueError('duplicate device open')
        if phase in ('weight_load', 'submit') and (not self.device):
            raise ValueError('device not opened')
        if phase == 'weight_load' and r['job'] != self.weights + 1:
            raise ValueError('weight order')
        if phase == 'submit' and (not self.weights or r['job'] <= self.last_job):
            raise ValueError('job replay/order')
        if phase == 'router_close' and r['job'] != 0:
            raise ValueError('close job')
        self.sequence[lane] += 1
        return lane

    def commit(self, r):
        phase = r['phase']
        if phase == 'router_open':
            self.router = True
        elif phase == 'device_open':
            self.device = True
        elif phase == 'weight_load':
            self.weights += 1
        elif phase == 'submit':
            self.last_job = r['job']
        elif phase == 'router_close':
            self.closed = True

class OwnedWorker(BaseWorker):

    def _permissions(self):
        order = PermissionOrder()
        with self.manager_sock.makefile('r', encoding='utf-8') as stream:
            try:
                for line in stream:
                    with ob.scope('permission'):
                        if len(line) > 4096:
                            raise ValueError('oversized permit')
                        with ob.span('request.parse'):
                            r = json.loads(line)
                        with ob.span('request.order'):
                            lane = order.check(r, self.process.pid)
                        ob.bind(r)
                        self.sequence += 1
                        gate_start = time.monotonic_ns()
                        with ob.span('owner.total'):
                            if self.owner_check:
                                self.owner_check()
                        owner_end = time.monotonic_ns()
                        with ob.span('health.total'):
                            health_observation = self.health()
                        health_end = time.monotonic_ns()
                        phase = r['phase']
                        closing = phase == 'router_close'
                        hook = getattr(self, 'before_permission', None)
                        with ob.span('decision'):
                            if hook:
                                hook(r)
                        with ob.span('decision'):
                            allowed = not self.quarantined and (closing or (not self.delivery_cancelled and time.monotonic() < self.expires))
                        with ob.span('decision'):
                            if phase == 'submit':
                                with ob.span('decision'):
                                    allowed = allowed and self.runs < self.max_runs
                                with ob.span('decision'):
                                    if allowed:
                                        self.runs += 1
                        with ob.span('decision'):
                            if phase == 'weight_load':
                                with ob.span('decision'):
                                    allowed = allowed and self.loads < self.max_loads
                                with ob.span('decision'):
                                    if allowed:
                                        self.loads += 1
                        with ob.span('decision'):
                            if allowed:
                                order.commit(r)
                        record_start = time.monotonic_ns()
                        self.record(event='PERMISSION', request=r, allow=allowed, sequence_lane=lane, observed_global_messages=self.sequence, health_observation=health_observation, owner_check_ms=(owner_end - gate_start) / 1000000.0, health_check_ms=(health_end - owner_end) / 1000000.0)
                        record_end = time.monotonic_ns()
                        if not hasattr(self, 'permission_metrics'):
                            self.permission_metrics = {}
                        for key, value in [('calls', 1), ('owner_check_ms', (owner_end - gate_start) / 1000000.0), ('health_check_ms', (health_end - owner_end) / 1000000.0), ('durable_permission_record_ms', (record_end - record_start) / 1000000.0)]:
                            self.permission_metrics[key] = self.permission_metrics.get(key, 0) + value
                        with ob.span('reply.encode'):
                            _01b_reply = (json.dumps(dict(sequence=r['sequence'], allow=allowed)) + '\n').encode()
                        with ob.span('reply.send'):
                            self.manager_sock.sendall(_01b_reply)
            except BaseException as exc:
                self.quarantined = True
                self.record(event='PERMISSION_FAULT_RETAIN_OWNER', reason=type(exc).__name__ + ': ' + str(exc))
                try:
                    self.manager_sock.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
