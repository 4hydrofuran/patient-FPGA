"""Exact one-N32 scope bootstrap; no retries, reset or automatic recovery."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path('/var/lib/kv260-a10/a10-isolated-single-20261023-v1')
BOOT = 'c5baeabe-273d-447e-b323-ff07dd7af201'
MANIFEST_SHA = 'ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7'
BASELINE_SHA = '79e2f2229502fca93f22bfe9b2bcc6c34d56851d65c17653babba516ccef2255'
PRIOR_IDLE_RECEIPT = '/var/lib/kv260-a10/a10-isolated-idle-20261023-v4/idle-receipt.json'
PRIOR_IDLE_SHA = 'c9e0a9d1522109bacc49e561a03f730683d2d7455ab66f96222ac831d35e4d37'
PRIOR_AUDIT_SHA = '8570faefd6c3ec1e57df8c293a33c3faae219c02ee86adee2bac228780fa5d2a'


def verify_fresh_log(proc):
    if proc.returncode != 0 or proc.stderr or hashlib.sha256(proc.stdout).hexdigest() != BASELINE_SHA:
        raise RuntimeError('BASELINE_CHANGED_REVIEW_REQUIRED_NO_TRIAL')
    return proc.stdout


def main():
    if len(sys.argv) != 2 or sys.argv[1] != BOOT or os.geteuid() != 0:
        raise RuntimeError('EXACT_AUTHORIZED_BOOT_AND_ROOT_REQUIRED')
    if (ROOT.is_symlink() or ROOT.stat().st_uid != 0 or ROOT.stat().st_mode & 0o022 or
            hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest() != MANIFEST_SHA):
        raise RuntimeError('ROOT_BUNDLE_PIN_DIFFERS')
    sys.path.insert(0, str(ROOT))
    from single_compute_policy import (KERNEL, MACHINE, SCOPE, digest, need, trusted_file,
                                       validate_review, verify_bundle)
    from accelerator_release_gate_v2 import collect, require_no_users
    need(os.uname().machine == 'aarch64' and os.uname().release == KERNEL, 'exact ARM64 kernel required')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT and
         digest('/etc/machine-id') == MACHINE, 'board/boot changed')
    manifest = verify_bundle(ROOT, MANIFEST_SHA)
    for name in manifest['files']:
        trusted_file(ROOT/name)
    need(not os.path.lexists('/var/lock/kv260-a1/active') and not Path('/sys/module/zocl').exists(),
         'active maintenance or module; no takeover')
    need(digest(PRIOR_IDLE_RECEIPT) == PRIOR_IDLE_SHA and digest(ROOT/'prior-idle-audit.json') == PRIOR_AUDIT_SHA,
         'prior passed idle evidence differs')
    for name in ('baseline.raw.txt', 'review.json', 'attempt.json', 'native-attempt.json'):
        need(not os.path.lexists(ROOT/name), 'authorization/attempt already reserved')
    scan = collect(allow_ps_display=True)
    raw = verify_fresh_log(subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3))
    stamp = time.monotonic_ns()
    require_no_users(scan, True, boot_id=BOOT)
    review = validate_review(dict(schema='A10_ISOLATED_SINGLE_REVIEW_V1', scope=SCOPE,
        authorized=True, compute_authorized=True, allow_gdm_stop_restore=True,
        max_submissions=1, n=32, explicit_bo_budget_bytes=49344,
        boot_id=BOOT, kernel=KERNEL, machine_sha256=MACHINE, window_id=ROOT.name,
        baseline_sha256=BASELINE_SHA, bundle_sha256=MANIFEST_SHA,
        prior_idle_audit_sha256=PRIOR_AUDIT_SHA, baseline_read_uptime_ns=stamp,
        authorization='USER_ALLOWED_CONTINUE_A10_ONE_N32_POSTCOMPUTE_RELEASE_20261023_NO_STRESS_OR_RETRY'))
    os.umask(0o077)
    with (ROOT/'baseline.raw.txt').open('xb') as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    with (ROOT/'review.json').open('x', encoding='utf-8') as stream:
        json.dump(review, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
    pin = digest(ROOT/'review.json')
    print(json.dumps(dict(event='ONE_N32_REVIEW_RESERVED', boot_id=BOOT,
                          review_sha256=pin, baseline_sha256=BASELINE_SHA)), flush=True)
    os.execv('/usr/bin/python3', ['/usr/bin/python3', '-B', '-I', str(ROOT/'isolated_single_manager_entry.py'),
              '--execute-authorized-single-once', '--source', str(ROOT), '--review-sha256', pin])


if __name__ == '__main__':
    main()
