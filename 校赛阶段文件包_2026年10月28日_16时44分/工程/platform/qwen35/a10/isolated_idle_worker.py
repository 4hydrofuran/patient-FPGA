"""Native XRT idle worker; no BO, run, register-write, reset or PL-manager API.

Default invocation prints its scope only. Never import this module into a
hardware manager after changing it to load native libraries at import time.
"""
import argparse
import ctypes as C
import json
import os
from pathlib import Path
import signal
import time
import uuid

from isolated_idle_policy import (ASSETS, KERNEL, LIBRARIES, XCLBIN_UUID, digest,
                                  load_json, need, trusted_file, validate_review,
                                  verify_bundle, verify_owner)
from xrt_worker_boundary import PROTOCOL


class IdleNativeAPI:
    def __init__(self):
        self.lib = C.CDLL('/usr/lib/libxrt_coreutil.so.2.18.0', use_errno=True)
        p, i, u = C.c_void_p, C.c_int, C.c_uint32
        signatures = {
            'xrtDeviceOpen': (p, [u]), 'xrtDeviceClose': (i, [p]),
            'xrtDeviceLoadXclbinFile': (i, [p, C.c_char_p]),
            'xrtDeviceGetXclbinUUID': (i, [p, p]),
            'xrtPLKernelOpenExclusive': (p, [p, p, C.c_char_p]),
            'xrtKernelClose': (i, [p]), 'xrtKernelArgGroupId': (i, [p, i]),
        }
        for name, (result, args) in signatures.items():
            call = getattr(self.lib, name)
            call.restype, call.argtypes = result, args
            setattr(self, name, call)


def run_idle(api, xclbin, emit, quarantine, clock=time.monotonic):
    # Keep the device/kernel handles reachable on an unknown/error return.
    device = kernel = None
    started = clock()

    def call(name, *args, handle=False, group=False):
        need(clock() - started < 10, 'idle initialization soft deadline')
        emit('XRT_CALL_BEGIN', call=name)
        value = getattr(api, name)(*args)
        emit('XRT_CALL_END', call=name, result=value)
        need(clock() - started < 10, 'native call exceeded soft deadline')
        need(bool(value) if handle else (type(value) is int and (value >= 0 if group else value == 0)),
             name + ' failed/unknown')
        return value

    try:
        device = call('xrtDeviceOpen', 0, handle=True)
        call('xrtDeviceLoadXclbinFile', device, str(xclbin).encode())
        loaded = (C.c_ubyte * 16)()
        call('xrtDeviceGetXclbinUUID', device, loaded)
        need(str(uuid.UUID(bytes=bytes(loaded))) == XCLBIN_UUID, 'xclbin UUID mismatch')
        kernel = call('xrtPLKernelOpenExclusive', device, loaded, b'krnl_vadd:{krnl_vadd_1}', handle=True)
        groups = [call('xrtKernelArgGroupId', kernel, n, group=True) for n in range(3)]
        need(groups == [3, 3, 3], 'metadata group differs')
        call('xrtKernelClose', kernel)
        kernel = None
        call('xrtDeviceClose', device)
        device = None
        emit('IDLE_HANDLES_CLOSED_PROCESS_EXIT_STILL_REQUIRED', groups=groups)
        return dict(status='NORMAL_CLOSED_NO_COMPUTE', normal_handles_closed=True,
                    real_submissions=0, explicit_bo_allocations=0, groups=groups,
                    xclbin_uuid=XCLBIN_UUID, hidden_xrt_allocations_measured=False)
    except BaseException as exc:
        # Even DeviceOpen failure is not proof that no native state was touched.
        quarantine('IDLE_NATIVE_UNKNOWN_RETAIN_PROCESS: ' + type(exc).__name__ + ': ' + str(exc))
        raise RuntimeError('quarantine must not return')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-isolated-idle', action='store_true')
    ap.add_argument('--source', type=Path)
    ap.add_argument('--a10-boundary-request')
    ap.add_argument('--a10-boundary-result', type=Path)
    args = ap.parse_args(argv)
    if not args.execute_isolated_idle:
        print(json.dumps(dict(mode='PLAN_ONLY', native_calls=0, compute_supported=False)))
        return 0
    need(args.source is not None and args.a10_boundary_request and args.a10_boundary_result,
         'manager protocol required')
    source = args.source.resolve()
    review = validate_review(load_json(source / 'review.json'))
    identity = json.loads(args.a10_boundary_request)
    need(identity.get('protocol') == PROTOCOL, 'wrong worker protocol')
    need(identity.get('request_sha256') == digest(source / 'review.json'), 'review identity differs')
    need(args.a10_boundary_result.resolve() == source / 'worker-result.json', 'unexpected result path')
    need(not os.path.lexists(args.a10_boundary_result), 'old result: replay forbidden')
    for path in (source, source / 'review.json', source / 'manifest.json'):
        trusted_file(path)
    verify_bundle(source, review['bundle_sha256'])
    verify_owner(identity, review, parent=True)
    need(digest(source / 'vadd.xclbin') == ASSETS['vadd.xclbin'], 'xclbin changed')
    for path, sha in LIBRARIES.items():
        need(digest(path) == sha, 'native library changed')
    # Block ordinary termination signals before any native initialization; an
    # uncertain ioctl must not lose its process as an implicit recovery action.
    signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT})
    os.nice(10)
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[key] = '1'

    def emit(event, **data):
        print(json.dumps(dict(event=event, monotonic_ns=time.monotonic_ns(),
                              worker_pid=os.getpid(), window_id=review['window_id'], **data)), flush=True)

    def quarantine(reason):
        try:
            emit('IDLE_WORKER_PARKED_NO_AUTOMATIC_CLOSE', reason=reason)
        finally:
            while True:
                time.sleep(30)

    try:
        emit('IDLE_WORKER_NATIVE_BEGIN', boot_id=identity['boot_id'], kernel=KERNEL)
        api = IdleNativeAPI()  # The ONLY native library load in this workflow.
        result = run_idle(api, source / 'vadd.xclbin', emit, quarantine)
        result.update(identity, worker_pid=os.getpid())
        with args.a10_boundary_result.open('x', encoding='utf-8') as stream:
            json.dump(result, stream)
            stream.flush()
            os.fsync(stream.fileno())
        emit('IDLE_WORKER_RETURNING_NORMALLY', explicit_bo_allocations=0, real_submissions=0)
    except BaseException as exc:
        quarantine('IDLE_NATIVE_OR_RESULT_UNKNOWN: ' + str(exc))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
