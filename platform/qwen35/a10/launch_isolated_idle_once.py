"""Root bootstrap for the one scoped idle trial, NOT a generic board executor.

Exact reviewed current-boot kernel bytes must still match before an exclusive
review is created. No baseline auto-approval and no retry or automatic cleanup.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/var/lib/kv260-a10/a10-isolated-idle-20261023-v4')
BOOT = 'c5baeabe-273d-447e-b323-ff07dd7af201'
MANIFEST_SHA = '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06'
# Independent current capture matches the preserved post-cleanup raw log exactly.
BASELINE_SHA = 'f7e39b399f7357d4cb2ddd9abe6bed8f1358357904244fd900d0d46661518ca1'
PRIOR = Path('/var/lib/kv260-a10/a10-isolated-idle-20261023-v3')
PRIOR_CLEANUP_SHA = 'be5ce68cceb048b85a0a6d877e7ab2e9c8df2a252da8f12cebff78082fd2ee04'
PRIOR_LEASE_SHA = '51cc97732d7d4d0645e015e70c757a55009242760cb2668eeebc3580d12c19f1'


def verify_fresh_log(proc):
    if (proc.returncode != 0 or proc.stderr or
            hashlib.sha256(proc.stdout).hexdigest() != BASELINE_SHA):
        raise RuntimeError('BASELINE_CHANGED_REVIEW_REQUIRED_NO_TRIAL')
    return proc.stdout


def main():
    if len(sys.argv) != 2 or sys.argv[1] != BOOT or os.geteuid() != 0:
        raise RuntimeError('EXACT_AUTHORIZED_BOOT_AND_ROOT_REQUIRED')
    if (ROOT.is_symlink() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o022 or
            hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest() != MANIFEST_SHA):
        raise RuntimeError('ROOT_BUNDLE_PIN_DIFFERS')
    sys.path.insert(0, str(ROOT))
    from isolated_idle_policy import (KERNEL, MACHINE, SCOPE, digest, need,
                                      trusted_file, validate_review, verify_bundle)
    from accelerator_release_gate_v2 import collect, require_no_users
    need(os.uname().machine == 'aarch64' and os.uname().release == KERNEL, 'exact ARM64 kernel required')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT and
         digest('/etc/machine-id') == MACHINE, 'board/boot changed')
    manifest = verify_bundle(ROOT, MANIFEST_SHA)
    for name in manifest['files']:
        trusted_file(ROOT / name)
    need(not os.path.lexists('/var/lock/kv260-a1/active') and
         not Path('/sys/module/zocl').exists(), 'active maintenance or module: no takeover')
    need(digest(PRIOR / 'prepl-cleanup.json') == PRIOR_CLEANUP_SHA and
         digest('/var/lock/kv260-a1/history/a10-isolated-idle-20261023-v3-prepl-aborted/lease.json')
         == PRIOR_LEASE_SHA and not (PRIOR / 'worker-result.json').exists(),
         'prior explicit pre-PL cleanup evidence changed')
    old_proc = Path('/proc/3887')
    if old_proc.exists():
        from accelerator_release_gate_v2 import start_ticks
        need(start_ticks(old_proc) != 144649, 'prior manager still alive: no takeover')
    for name in ('baseline.raw.txt', 'review.json', 'attempt.json'):
        need(not os.path.lexists(ROOT / name), 'authorization/attempt already reserved')
    scan = collect(allow_ps_display=True)
    # Pre-mutation scan. This does not override the manager's later kernel gate.
    raw = verify_fresh_log(subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3))
    read_ns = time.monotonic_ns()
    require_no_users(scan, True, boot_id=BOOT)
    review = validate_review(dict(schema='A10_ISOLATED_IDLE_REVIEW_V1', scope=SCOPE,
                                   compute_authorized=False, authorized=True, allow_gdm_stop_restore=True,
                                   boot_id=BOOT, kernel=KERNEL, machine_sha256=MACHINE,
                                   window_id=ROOT.name, baseline_sha256=BASELINE_SHA,
                                   bundle_sha256=MANIFEST_SHA, baseline_read_uptime_ns=read_ns,
                                   authorization='USER_FRESH_V4_SINGLE_IDLE_XRT_AND_DEFAULT_PL_RECOVERY_20261023'))
    os.umask(0o077)
    with (ROOT / 'baseline.raw.txt').open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    with (ROOT / 'review.json').open('x', encoding='utf-8') as stream:
        json.dump(review, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    review_sha = digest(ROOT / 'review.json')
    print(json.dumps(dict(event='ONE_IDLE_REVIEW_RESERVED', boot_id=BOOT,
                          review_sha256=review_sha, baseline_sha256=BASELINE_SHA)), flush=True)
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-B', '-I',
             str(ROOT / 'isolated_idle_manager_entry.py'), '--execute-authorized-idle-once',
             '--source', str(ROOT), '--review-sha256', review_sha])


if __name__ == '__main__':
    main()
