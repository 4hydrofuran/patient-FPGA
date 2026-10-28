"""A12 Python-only observation. No permission decisions or device operations."""
import contextlib
import json
import os
import resource
import threading
import time

_local = threading.local()
_lock = threading.Lock()
_rows = []
_request = None
_request_usage = None
MAX_ROWS = 12000


@contextlib.contextmanager
def span(name):
    frame = getattr(_local, 'frame', None)
    if frame is None:
        yield
        return
    start, cpu = time.monotonic_ns(), time.thread_time_ns()
    try:
        yield
    finally:
        frame['spans'].append([name, start, time.monotonic_ns(), time.thread_time_ns()-cpu])


@contextlib.contextmanager
def scope(kind):
    if getattr(_local, 'frame', None) is not None:
        raise RuntimeError('Nested management observation scope')
    with _lock:
        request = _request
        if len(_rows) >= MAX_ROWS:
            raise RuntimeError('Management observation row budget')
    thread_usage = resource.getrusage(resource.RUSAGE_THREAD)
    frame = dict(kind=kind, request_id=request, tid=threading.get_native_id(),
                 start_ns=time.monotonic_ns(), cpu_start_ns=time.thread_time_ns(), spans=[])
    _local.frame = frame
    try:
        yield
        frame['outcome'] = 'RETURNED'
    except BaseException as exc:
        frame['outcome'] = 'FAILED'
        frame['exception'] = type(exc).__name__
        raise
    finally:
        frame['end_ns'] = time.monotonic_ns()
        frame['thread_cpu_ns'] = time.thread_time_ns()-frame.pop('cpu_start_ns')
        after_usage = resource.getrusage(resource.RUSAGE_THREAD)
        frame['context_switches'] = dict(voluntary=after_usage.ru_nvcsw-thread_usage.ru_nvcsw,
                                         involuntary=after_usage.ru_nivcsw-thread_usage.ru_nivcsw)
        _local.frame = None
        with _lock:
            _rows.append(frame)


def bind(request):
    frame = getattr(_local, 'frame', None)
    if frame is not None:
        frame['permit'] = dict(request)


@contextlib.contextmanager
def lock_context(lock, name):
    with span(name):
        result = lock.__enter__()
    try:
        yield result
    except BaseException:
        import sys
        if not lock.__exit__(*sys.exc_info()):
            raise
    else:
        lock.__exit__(None, None, None)


@contextlib.contextmanager
def file_context(factory, name):
    with span(name+'.open'):
        handle = factory()
        value = handle.__enter__()
    try:
        yield value
    except BaseException:
        import sys
        with span(name+'.close'):
            suppress = handle.__exit__(*sys.exc_info())
        if not suppress:
            raise
    else:
        with span(name+'.close'):
            handle.__exit__(None, None, None)


def call(name, function):
    with span(name):
        return function()


def start_request(request):
    global _request, _request_usage
    with _lock:
        if _request is not None:
            raise RuntimeError('Overlapping observed requests')
        _request = request['id']
        usage = resource.getrusage(resource.RUSAGE_SELF)
        _request_usage = dict(cpu_ns=time.process_time_ns(), user_s=usage.ru_utime, system_s=usage.ru_stime,
                              voluntary=usage.ru_nvcsw,involuntary=usage.ru_nivcsw)


def finish_request(result, path):
    global _request
    with _lock:
        if _request != result['id']:
            raise RuntimeError('Observation request mismatch')
        rows = [r for r in _rows if r['request_id'] == _request]
        _request = None
    submits = [r for r in rows if r.get('permit', {}).get('phase') == 'submit']
    phase_data = result.get('request_profile', {}).get('pl_profile', {})
    phases = phase_data.get('phases', {})
    attributable = phase_data.get('enabled') is True
    counts = {name:int(phases.get(name, {}).get('calls', 0)) for name in ('prefill','decode')}
    if attributable:
        if sum(counts.values()) != len(submits) or any(r['outcome'] != 'RETURNED' for r in submits):
            raise RuntimeError('Native phase/observed submission mismatch')
        jobs = [r['permit']['job'] for r in submits]
        if any(b <= a for a,b in zip(jobs,jobs[1:])):
            raise RuntimeError('Observed job order mismatch')
        for i,row in enumerate(submits):
            row['model_phase'] = 'prefill' if i < counts['prefill'] else 'decode'
    else:
        for row in submits:
            row['model_phase'] = 'UNATTRIBUTED_NO_NATIVE_PHASE_COUNTERS'
    totals = {}
    for row in rows:
        group = row.get('model_phase', row['kind'])
        bucket = totals.setdefault(group, dict(rows=0, wall_ns=0, thread_cpu_ns=0, spans={}))
        bucket['rows'] += 1
        bucket['wall_ns'] += row['end_ns']-row['start_ns']
        bucket['thread_cpu_ns'] += row['thread_cpu_ns']
        for name,a,b,cpu in row['spans']:
            entry = bucket['spans'].setdefault(name, dict(calls=0, wall_ns=0, thread_cpu_ns=0))
            entry['calls'] += 1;entry['wall_ns'] += b-a;entry['thread_cpu_ns'] += cpu
    usage = resource.getrusage(resource.RUSAGE_SELF)
    report = dict(schema='A12_CPU01B_MANAGEMENT_V1', request_id=result['id'], rows=rows, totals=totals,
                  native_phase_counts=counts, phase_attribution='ACTUAL_ORDER_AND_NATIVE_COUNTS' if attributable else 'UNATTRIBUTED',
                  process_usage_cumulative=dict(user_s=usage.ru_utime,system_s=usage.ru_stime,
                      voluntary_context_switches=usage.ru_nvcsw,involuntary_context_switches=usage.ru_nivcsw),
                  process_usage_delta=dict(cpu_ns=time.process_time_ns()-_request_usage['cpu_ns'],
                      user_s=usage.ru_utime-_request_usage['user_s'],system_s=usage.ru_stime-_request_usage['system_s'],
                      voluntary=usage.ru_nvcsw-_request_usage['voluntary'],involuntary=usage.ru_nivcsw-_request_usage['involuntary']),
                  semantics='Nested spans overlap; only siblings sum. Cross-process/native remainder is not pure IPC.',
                  collector='BOUNDED_MEMORY_DURING_PERMISSION; ONE_REQUEST_FILE_AFTER_CLIENT_END',
                  hardware_cycles=None)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, separators=(',',':'), allow_nan=False)
    return report


def reset_for_test():
    global _request
    with _lock:
        _rows.clear();_request=None
