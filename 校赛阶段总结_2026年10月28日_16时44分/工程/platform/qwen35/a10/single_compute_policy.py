"""Separate one-call postcompute-release scope; idle approval cannot authorize it."""
import os
from pathlib import Path
import re
import time
import uuid

from accelerator_release_gate_v2 import start_ticks
from isolated_idle_policy import (ASSETS, BOOT_FILES, CENTRAL, CONSUMED_BOOTS, DEFAULT,
                                  KERNEL, LIBRARIES, LOCKS, MACHINE, XCLBIN_UUID,
                                  digest, load_json, lock_owned, need, trusted_file)

SCOPE = 'A10_N32_POSTCOMPUTE_RELEASE_ONCE'
PROTOCOL = 'a10-isolated-single-compute-worker-v1'
N, WORDS, JOB = 32, 4112, 7
BO_BYTES, BO_COUNT = WORDS * 4, 3
SOURCES = ('single_compute_policy.py', 'single_compute_worker.py', 'single_compute_boundary.py',
           'single_compute_entry.py', 'isolated_single_trial.py', 'isolated_single_manager_entry.py',
           'isolated_idle_trial.py', 'isolated_idle_policy.py', 'xrt_worker_boundary.py',
           'accelerator_release_gate_v2.py', 'idle_board_trial.py', 'minimal_gate.py', 'kernel_log_gate.py')


def vector():
    a = [(0x80000000 + JOB*8191 + n*65537) % (1 << 32) for n in range(N)]
    b = [(0x7fffffff - JOB*127 + n*17) % (1 << 32) for n in range(N)]
    return dict(schema='A10_FIXED_N32_VECTOR_V1', job=JOB, n=N, words=WORDS,
                input_a=a, input_b=b, expected=[(x+y) % (1 << 32) for x, y in zip(a, b)],
                guard_value=0xdeadbeef, reference='PC integer addition modulo 2^32; not recorded hardware output')


def validate_review(review):
    need(review.get('schema') == 'A10_ISOLATED_SINGLE_REVIEW_V1' and review.get('scope') == SCOPE,
         'new single-compute review required; idle authorization is not accepted')
    need(all(review.get(k) is True for k in ('authorized', 'compute_authorized', 'allow_gdm_stop_restore')),
         'new explicit single-compute authorization missing')
    for key, value in (('max_submissions', 1), ('n', N), ('explicit_bo_budget_bytes', BO_COUNT*BO_BYTES)):
        need(type(review.get(key)) is int and review[key] == value, 'scope limit differs: ' + key)
    boot = review.get('boot_id')
    need(type(boot) is str and str(uuid.UUID(boot)) == boot and boot not in CONSUMED_BOOTS,
         'fresh reviewed boot required')
    need(review.get('kernel') == KERNEL and review.get('machine_sha256') == MACHINE, 'platform differs')
    need(re.fullmatch(r'a10-isolated-single-20261023-v[1-9][0-9]*', review.get('window_id', '')),
         'new single-compute window required')
    for key in ('baseline_sha256', 'bundle_sha256', 'prior_idle_audit_sha256'):
        need(re.fullmatch(r'[0-9a-f]{64}', review.get(key, '')), 'required pin missing: ' + key)
    need(type(review.get('baseline_read_uptime_ns')) is int and review['baseline_read_uptime_ns'] > 0,
         'fresh baseline timestamp required')
    return review


def verify_bundle(source, expected_sha):
    source = Path(source)
    need(digest(source/'manifest.json') == expected_sha, 'single-compute bundle pin differs')
    manifest = load_json(source/'manifest.json')
    need(manifest.get('schema') == 'A10_ISOLATED_SINGLE_BUNDLE_V1' and manifest.get('scope') == SCOPE
         and manifest.get('authorization_included') is False, 'wrong or preauthorized package')
    need(type(manifest.get('max_submissions')) is int and manifest['max_submissions'] == 1 and
         manifest.get('board_accepted') is False, 'candidate must be one-call and not preaccepted')
    need(set(manifest.get('files', {})) == set(ASSETS) | set(SOURCES) | {'shell.json', 'vector.json', 'prior-idle-audit.json'},
         'single-compute package inventory differs')
    for name, meta in manifest['files'].items():
        path = source/name
        need(not path.is_symlink() and path.is_file() and path.stat().st_size == meta['bytes'] and
             digest(path) == meta['sha256'], 'payload differs: ' + name)
    need(all(manifest['files'][n]['sha256'] == sha for n, sha in ASSETS.items()), 'hardware asset differs')
    need(load_json(source/'vector.json') == vector(), 'fixed input/reference changed')
    return manifest


def verify_owner(identity, review, *, parent=False):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and os.uname().release == KERNEL,
         'root and exact ARM64 kernel required')
    need(boot == identity['boot_id'] == review['boot_id'] and identity['window_id'] == review['window_id'],
         'boot/window differs')
    need(identity['protocol'] == PROTOCOL, 'compute boundary protocol differs')
    pid = identity['manager_pid']
    need(type(pid) is int and pid == (os.getppid() if parent else os.getpid()), 'manager PID differs')
    lease_path = CENTRAL/'active/lease.json'
    for path in (CENTRAL, CENTRAL/'active', lease_path, *LOCKS):
        trusted_file(path)
    need(digest(lease_path) == identity['lease_sha256'], 'lease changed')
    lease = load_json(lease_path)
    need(lease.get('scope') == SCOPE and lease.get('compute_authorized') is True and
         type(lease.get('max_submissions')) is int and lease['max_submissions'] == 1 and
         lease.get('window') == review['window_id'] and lease.get('pid') == pid and
         lease.get('identity') == MACHINE + ':' + boot, 'wrong lease scope/identity')
    need(lease['owner_start_ticks'] == start_ticks(Path('/proc')/str(pid)), 'manager PID reused')
    need(type(lease.get('expires_monotonic_ns')) is int and time.monotonic_ns() < lease['expires_monotonic_ns'],
         'lease expired')
    need(all(lock_owned(p, pid) for p in LOCKS), 'both manager locks required')
    need('libxrt_' not in (Path('/proc')/str(pid)/'maps').read_text(), 'manager loaded XRT')
    return True


def validate_result(result, identity, worker_pid):
    expected = dict(identity, worker_pid=worker_pid, status='NORMAL_CLOSED_ONE_N32',
                    normal_handles_closed=True, real_submissions=1, explicit_bo_allocations=3,
                    explicit_requested_peak_bytes=BO_COUNT*BO_BYTES, n=N, job=JOB,
                    pass_numeric=True, completion_state=4, guards_checked=WORDS-N)
    for key, value in expected.items():
        need(type(result.get(key)) is type(value) and result.get(key) == value, 'result differs: ' + key)
    v = vector()
    for key in ('input_a', 'input_b'):
        need(result.get(key) == v[key], 'input differs: ' + key)
    need(result.get('actual_output') == v['expected'] and result.get('changed_guard_indices') == [] and
         result.get('groups') == [3, 3, 3], 'actual output/guards/groups not verified')
    need(result.get('physical_bo_peak_bytes') is None, 'physical peak was not measured')
    return result
