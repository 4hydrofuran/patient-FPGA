"""A11 diagnostic child: one synchronous open, optional close, no run/load API.

An open return with null context is a completed diagnostic, not a compute
failure with unknown DMA. Exit normally so the OS can release residual XRT
mappings. The parent must independently prove release before PL removal.
"""
import ctypes as C
import json
import os
from pathlib import Path
import time


def diagnose(lib, config):
    ctx = C.c_void_p()
    lib.sp_linear_open_v1.argtypes = [C.c_char_p, C.POINTER(C.c_void_p)]
    lib.sp_linear_open_v1.restype = C.c_int32
    lib.sp_linear_close_v1.argtypes = [C.c_void_p]
    lib.sp_linear_close_v1.restype = C.c_int32
    started = time.monotonic_ns()
    rc = lib.sp_linear_open_v1(os.fsencode(config), C.byref(ctx))
    opened = time.monotonic_ns()
    if type(rc) is not int or rc not in range(10):
        raise RuntimeError('invalid open return')
    if (rc == 0) != bool(ctx.value):
        raise RuntimeError('open return/context disagreement')
    close_rc = lib.sp_linear_close_v1(ctx) if rc == 0 else None
    if rc == 0 and close_rc != 0:
        raise RuntimeError('close failed: ' + str(close_rc))
    return dict(status='OPEN_DIAGNOSTIC_RETURNED_NO_COMPUTE', open_status_code=rc,
                close_status_code=close_rc, real_submissions=0,
                explicit_bo_allocations=None, physical_bo_peak_bytes=None,
                open_ms=(opened-started)/1e6,
                close_ms=(time.monotonic_ns()-opened)/1e6 if rc == 0 else None,
                normal_handles_closed=(rc == 0),
                release_proven=False, A11='NOT_PASSED')


def execute(source, identity, checkpoint, write, quarantine):
    checkpoint()
    try:
        lib = C.CDLL(str(source/'libsp_linear_a11_trial.so'))
        result = diagnose(lib, source/'trial-config.json')
        # No exception-triggered unloading/termination. Every diagnostic return
        # passes a fresh health gate and is committed before normal process exit.
        checkpoint()
        result.update(identity, worker_pid=os.getpid())
        write(source/'worker-result.json', result)
        print(json.dumps(dict(event='OPEN_DIAGNOSTIC_RETURNED', **result)), flush=True)
    except BaseException as exc:
        quarantine(type(exc).__name__ + ': ' + str(exc))
    return 0
