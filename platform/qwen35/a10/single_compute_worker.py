"""Isolated one-N32 XRT worker. Default is PLAN_ONLY; no automatic recovery.

Native handles stay in this child. The manager must reap its normal exit and
independently prove no residual FD/VMA/refcount before removing the overlay.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

from minimal_gate import MinimalGate
from single_compute_policy import (ASSETS, BO_BYTES, BO_COUNT, JOB, KERNEL, LIBRARIES, N,
                                   PROTOCOL, WORDS, XCLBIN_UUID, digest, load_json, need,
                                   trusted_file, validate_review, verify_bundle, verify_owner, vector)


class SingleNativeAPI:
    def __init__(self):
        self.lib = C.CDLL('/usr/lib/libxrt_coreutil.so.2.18.0', use_errno=True)
        p, i, u, z, q = C.c_void_p, C.c_int, C.c_uint32, C.c_size_t, C.c_uint64
        signatures = {
            'xrtDeviceOpen': (p, [u]), 'xrtDeviceClose': (i, [p]),
            'xrtDeviceLoadXclbinFile': (i, [p, C.c_char_p]), 'xrtDeviceGetXclbinUUID': (i, [p, p]),
            'xrtPLKernelOpenExclusive': (p, [p, p, C.c_char_p]), 'xrtKernelClose': (i, [p]),
            'xrtKernelArgGroupId': (i, [p, i]), 'xrtBOAlloc': (p, [p, z, q, u]),
            'xrtBOFree': (i, [p]), 'xrtBOMap': (p, [p]), 'xrtBOAddress': (q, [p]),
            'xrtBOSize': (z, [p]), 'xrtBOSync': (i, [p, i, z, z]),
            'xrtRunOpen': (p, [p]), 'xrtRunClose': (i, [p]),
            'xrtRunSetArg': (i, [p, i]),  # C varargs use explicit ctypes below
            'xrtRunStart': (i, [p]), 'xrtRunState': (i, [p]),
        }
        for name, (result, args) in signatures.items():
            call = getattr(self.lib, name)
            call.restype, call.argtypes = result, args
            setattr(self, name, call)


def memory(phase, live_bytes):
    return dict(phase=phase, proc_status=Path('/proc/self/status').read_text(),
                smaps_rollup=Path('/proc/self/smaps_rollup').read_text(),
                meminfo=Path('/proc/meminfo').read_text(), explicit_requested_live_bytes=live_bytes,
                explicit_requested_budget_bytes=BO_COUNT*BO_BYTES, physical_bo_peak_bytes=None,
                implicit_xrt_allocations_bytes=None, process_exit_release_proven=False)


def run_single(api, xclbin, inputs, emit, checkpoint, quarantine, *,
               clock=time.monotonic, sleep=time.sleep, memory_reader=memory):
    # Keep references reachable for any uncertain result, even after failed open.
    device = kernel = run = None
    buffers, mapped, addresses = [], [], []
    started, submitted, states = clock(), None, []
    native_us = []

    def invoke(name, *args, kind='zero'):
        need(clock()-started < 10, 'single worker soft deadline')
        emit('XRT_CALL_BEGIN', call=name)
        before = clock()
        value = getattr(api, name)(*args)
        after = clock()
        duration = (after-before)*1e6
        native_us.append((name, duration))
        emit('XRT_CALL_END', call=name, result=value, native_call_us=duration,
             timing_scope='native API only, excludes event writes; not pure DMA bandwidth')
        need(0 <= duration and after-started < 10, 'native call exceeded soft deadline')
        if kind == 'handle':
            ok = type(value) is int and value > 0 and value != C.c_void_p(-1).value
        elif kind == 'nonnegative':
            ok = type(value) is int and value >= 0
        else:
            ok = type(value) is int and value == 0
        need(ok, name + ' failed/unknown')
        return value

    try:
        need(inputs == vector(), 'fixed N32 input/reference differs')
        checkpoint('before_native')
        emit('MEMORY_OBSERVATION', **memory_reader('before_device_open', 0))
        device = invoke('xrtDeviceOpen', 0, kind='handle')
        invoke('xrtDeviceLoadXclbinFile', device, str(xclbin).encode())
        loaded = (C.c_ubyte*16)()
        invoke('xrtDeviceGetXclbinUUID', device, loaded)
        need(str(uuid.UUID(bytes=bytes(loaded))) == XCLBIN_UUID, 'loaded UUID differs')
        kernel = invoke('xrtPLKernelOpenExclusive', device, loaded, b'krnl_vadd:{krnl_vadd_1}', kind='handle')
        groups = [invoke('xrtKernelArgGroupId', kernel, n, kind='nonnegative') for n in range(BO_COUNT)]
        need(groups == [3, 3, 3], 'metadata groups differ')
        for group in groups:
            buffer = invoke('xrtBOAlloc', device, BO_BYTES, 0, group, kind='handle')
            buffers.append(buffer)
            address = invoke('xrtBOAddress', buffer, kind='nonnegative')
            need(invoke('xrtBOSize', buffer, kind='nonnegative') == BO_BYTES, 'BO size differs')
            need(address % 4 == 0 and 0 <= address < 0x80000000 and BO_BYTES <= 0x80000000-address,
                 'BO outside pinned HP0 addressability')
            need(all(address+BO_BYTES <= a or a+BO_BYTES <= address for a in addresses), 'BO addresses overlap')
            addresses.append(address)
            pointer = invoke('xrtBOMap', buffer, kind='handle')
            mapped.append((C.c_uint32*WORDS).from_address(pointer))
        emit('BO_CREATED', groups=groups, addresses=addresses, bytes_each=BO_BYTES,
             explicit_requested_live_bytes=len(buffers)*BO_BYTES, maximum_budget_probe=False)
        emit('MEMORY_OBSERVATION', **memory_reader('explicit_bos_live', len(buffers)*BO_BYTES))
        a, b, out = mapped
        for n in range(WORDS):
            a[n] = inputs['input_a'][n] if n < N else 0
            b[n] = inputs['input_b'][n] if n < N else 0
            out[n] = (~inputs['expected'][n]) & 0xffffffff if n < N else inputs['guard_value']
        emit('INPUTS_PREPARED_NOT_SUBMITTED', job=JOB, n=N, input_a=list(a[:N]), input_b=list(b[:N]),
             output_poison=list(out[:N]), guard_words=WORDS-N)
        sync_wall_begin = clock()
        sync_index = len(native_us)
        for buffer in buffers:
            invoke('xrtBOSync', buffer, 0, BO_BYTES, 0)
        sync_in_wall_us = (clock()-sync_wall_begin)*1e6
        sync_in_call_us = sum(t for name, t in native_us[sync_index:] if name == 'xrtBOSync')
        run = invoke('xrtRunOpen', kernel, kind='handle')
        for n, buffer in enumerate(buffers):
            invoke('xrtRunSetArg', run, n, C.c_void_p(buffer))
        invoke('xrtRunSetArg', run, 3, C.c_uint32(N))
        checkpoint('before_submit')
        emit('SINGLE_SUBMISSION_BEGIN', n=N, maximum_count=1)
        submitted = clock()  # a failing start is still a possible submission
        invoke('xrtRunStart', run)
        while True:
            need(clock()-submitted < 1, 'COMPUTE_SOFT_DEADLINE_NO_ABORT_NO_RELEASE')
            # Bounded, 2-ms sleeps; not an unbounded CPU busy-wait.
            state = api.xrtRunState(run)
            need(clock()-submitted < 1, 'STATE_CALL_DEADLINE_NO_ABORT_NO_RELEASE')
            need(type(state) is int and state in (1, 2, 3, 4, 7), 'NON_COMPLETED_RUN_STATE_' + str(state))
            if not states or states[-1] != state:
                states.append(state)
                emit('RUN_STATE_OBSERVED', state=state)
            if state == 4:
                break
            sleep(0.002)
        completed = clock()
        emit('POSITIVE_COMPLETION', state=4, observed_states=states, submit_poll_us=(completed-submitted)*1e6)
        checkpoint('after_positive_completion')
        invoke('xrtBOSync', buffers[2], 1, BO_BYTES, 0)
        sync_out_call_us = native_us[-1][1]
        actual = list(out[:N])
        changed = [n for n in range(N, WORDS) if out[n] != inputs['guard_value']]
        numeric = actual == inputs['expected'] and not changed
        result = dict(job=JOB, n=N, input_a=list(a[:N]), input_b=list(b[:N]), actual_output=actual,
                      changed_guard_indices=changed, guards_checked=WORDS-N, pass_numeric=numeric,
                      completion_state=4, observed_states=states, groups=groups, addresses=addresses,
                      real_submissions=1, explicit_bo_allocations=BO_COUNT,
                      explicit_requested_peak_bytes=BO_COUNT*BO_BYTES, physical_bo_peak_bytes=None,
                      sync_in_native_call_total_us=sync_in_call_us, sync_in_inclusive_wall_us=sync_in_wall_us,
                      sync_out_native_call_us=sync_out_call_us, performance_conclusion=None)
        emit('ACTUAL_OUTPUT', **result)  # preserves a mismatch before stopping
        need(numeric, 'numeric/guard mismatch; no teardown authorization')
        checkpoint('before_normal_handle_close')
        invoke('xrtRunClose', run)
        run = None
        # Python pointer views own no native lifetime. Do not touch them after free.
        mapped.clear()
        a = b = out = None
        while buffers:
            invoke('xrtBOFree', buffers[-1])
            buffers.pop()
        invoke('xrtKernelClose', kernel)
        kernel = None
        invoke('xrtDeviceClose', device)
        device = None
        emit('MEMORY_OBSERVATION', **memory_reader('after_api_close_before_process_exit', 0))
        checkpoint('after_handle_close_before_exit')
        result.update(status='NORMAL_CLOSED_ONE_N32', normal_handles_closed=True)
        return result
    except BaseException as exc:
        quarantine('SINGLE_NATIVE_UNKNOWN_RETAIN_PROCESS: ' + type(exc).__name__ + ': ' + str(exc))
        raise RuntimeError('quarantine must not return')


def worker_baseline(source, identity, review, *, now_ns=None):
    """Validate the exact parent-approved log; no native access or new approval."""
    need(digest(source/'worker-baseline.json') == identity['worker_baseline_sha256'], 'worker baseline pin differs')
    ready = load_json(source/'worker-baseline.json')
    for key in ('boot_id', 'window_id', 'manager_pid', 'lease_sha256', 'request_sha256'):
        need(type(ready.get(key)) is type(identity[key]) and ready[key] == identity[key],
             'worker baseline identity differs: ' + key)
    stamp = ready.get('read_monotonic_ns')
    now_ns = time.monotonic_ns() if now_ns is None else now_ns
    need(ready.get('kernel_gate_allowed') is True and type(stamp) is int and stamp > 0 and
         0 <= now_ns-stamp <= 10_000_000_000, 'worker baseline not freshly approved by manager')
    need(0 < (source/'worker-baseline.raw.txt').stat().st_size <= 1048576 and
         digest(source/'worker-baseline.raw.txt') == ready['raw_sha256'], 'worker baseline bytes differ')
    gate = MinimalGate()
    need(gate.observe_action(review['boot_id'], (source/'worker-baseline.raw.txt').read_bytes().decode(),
                             ready['raw_sha256'], 'none')['allowed'], 'worker baseline rejected')
    return gate


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-isolated-single', action='store_true')
    ap.add_argument('--source', type=Path)
    ap.add_argument('--a10-boundary-request')
    ap.add_argument('--a10-boundary-result', type=Path)
    args = ap.parse_args(argv)
    if not args.execute_isolated_single:
        print(json.dumps(dict(mode='PLAN_ONLY', native_calls=0, max_compute_submissions=1, requires_new_scope=True)))
        return 0
    need(args.source is not None and args.a10_boundary_request and args.a10_boundary_result,
         'new manager protocol required')
    source = args.source.resolve()
    review = validate_review(load_json(source/'review.json'))
    identity = json.loads(args.a10_boundary_request)
    need(identity['protocol'] == PROTOCOL and identity['request_sha256'] == digest(source/'review.json'),
         'wrong request/review identity')
    need(args.a10_boundary_result.resolve() == source/'worker-result.json' and
         not os.path.lexists(args.a10_boundary_result) and not os.path.lexists(source/'native-attempt.json'),
         'unexpected path or consumed worker')
    for p in (source, source/'review.json', source/'manifest.json', source/'worker-baseline.json',
              source/'worker-baseline.raw.txt'):
        trusted_file(p)
    verify_bundle(source, review['bundle_sha256'])
    verify_owner(identity, review, parent=True)
    for p, sha in LIBRARIES.items():
        need(digest(p) == sha, 'native library changed')
    gate = worker_baseline(source, identity, review)
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT})
    os.umask(0o077)
    with (source/'native-attempt.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(identity, worker_pid=os.getpid(), max_submissions=1), stream)
        stream.flush(); os.fsync(stream.fileno())
    os.nice(10)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'

    def emit(event, **data):
        print(json.dumps(dict(event=event, monotonic_ns=time.monotonic_ns(), worker_pid=os.getpid(),
                              window_id=review['window_id'], **data)), flush=True)

    def quarantine(reason):
        try:
            emit('SINGLE_WORKER_PARKED_NO_AUTOMATIC_CLOSE', reason=reason)
        finally:
            while True:
                time.sleep(30)

    def checkpoint(phase):
        verify_owner(identity, review, parent=True)
        p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
        need(p.returncode == 0 and not p.stderr, 'worker kernel read unavailable')
        current = gate.observe_action(review['boot_id'], p.stdout.decode(), None, 'none')
        emit('WORKER_KERNEL_GATE', phase=phase, **current)
        need(current['allowed'], 'worker kernel gate refused')

    try:
        checkpoint('before_library_load')
        emit('SINGLE_WORKER_NATIVE_BEGIN', boot_id=review['boot_id'], kernel=KERNEL)
        result = run_single(SingleNativeAPI(), source/'vadd.xclbin', load_json(source/'vector.json'),
                            emit, checkpoint, quarantine)
        result.update(identity, worker_pid=os.getpid())
        with args.a10_boundary_result.open('x', encoding='utf-8') as stream:
            json.dump(result, stream); stream.flush(); os.fsync(stream.fileno())
        emit('SINGLE_WORKER_RETURNING_NORMALLY', real_submissions=1, process_exit_release_proven=False)
    except BaseException as exc:
        quarantine('SINGLE_RESULT_OR_NATIVE_UNKNOWN: ' + str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
