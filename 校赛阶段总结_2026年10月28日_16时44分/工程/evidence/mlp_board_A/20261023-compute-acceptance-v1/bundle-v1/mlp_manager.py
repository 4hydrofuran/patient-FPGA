"""One N32 postcompute-release controller; PLAN_ONLY unless separately authorized.

Reuses the unchanged, board-proven idle management and safety gates. This manager
never imports a native worker or XRT. No retries, force unload or reboot.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import time
from manager_support import pulse, latch_stop

from accelerator_release_gate_v2 import start_ticks
from idle_board_trial import RESTORE, check_loaded, check_removed
from mlp_base import IsolatedIdleTrial, check_topology
from mlp_kernel_gate import MinimalGate
from mlp_boundary_v2 import MlpBoundary
from mlp_policy import (ASSETS, PLAN_SHA, BOOT_FILES, CENTRAL, DEFAULT,
                                   KERNEL, LIBRARIES, LOCKS, MACHINE, PROTOCOL, SCOPE,
                                   digest, load_json, need, trusted_file, validate_review,
                                   verify_bundle, verify_owner)


class MlpTrial(IsolatedIdleTrial):
    def __init__(self, source, review_sha):
        self.source = Path(source).resolve()
        need(digest(self.source/'review.json') == review_sha, 'single review SHA mismatch')
        self.review = validate_review(load_json(self.source/'review.json'))
        self.manifest = verify_bundle(self.source, self.review['bundle_sha256'])
        need(digest(self.source/'prior-a10-audit.json') == self.review['prior_a10_audit_sha256'], 'prior idle audit differs')
        prior = load_json(self.source/'prior-a10-audit.json')
        need(prior['status'] == 'PASS_BOARD_SINGLE_N32_POSTCOMPUTE_RELEASE_WITH_LIMITATIONS' and prior['kernel'] == KERNEL and
             prior['machine_sha256'] == MACHINE, 'prior isolated idle evidence required')
        self.boot, self.package = self.review['boot_id'], self.review['window_id']
        self.target = Path('/lib/firmware/xilinx')/self.package
        self.driver, self.driver_sha256 = self.source/'zocl.refcount.ko', ASSETS['zocl.refcount.ko']
        self.review_sha = review_sha
        need(not any(os.path.lexists(self.source/n) for n in
                     ('attempt.json', 'lifecycle.jsonl', 'worker-result.json', 'mlp-receipt.json',
                      'worker-baseline.json', 'worker-baseline.raw.txt', 'native-attempt.json')),
             'consumed single-compute directory: no replay')
        self.log, self.held_locks, self.identity = None, [], None
        self.kernel_gate, self.worker = MinimalGate(), None
        self.release_checked = self.gdm_isolated = self.pl_mutation_started = False

    def park(self, reason):
        try:
            latch_stop(self, reason)
            self.emit('QUARANTINED_MANAGER_AND_LOCKS_RETAINED', reason=reason,
                      compute_authorized=True, max_submissions=23, automatic_cleanup=False)
        finally:
            while True:
                time.sleep(30)

    def guard(self, identity=None):
        if identity is not None:
            need(all(identity.get(k)==v for k,v in self.identity.items()), 'MLP worker identity differs')
            if 'inherited_device_lock_fd' in identity:
                need(identity['inherited_device_lock_fd']==self.held_locks[1].fileno() and
                     identity['manager_start_ticks']==start_ticks(Path('/proc/self')), 'borrowed descriptor differs')
        verify_owner(self.identity, self.review)
        if self.gdm_isolated:
            import subprocess
            state = subprocess.run(['systemctl', 'is-active', 'gdm.service'], capture_output=True, timeout=3)
            need(state.stdout.strip() == b'inactive', 'graphical isolation lost')
        self.snapshot('identity_health_guard')
        return True

    def claim(self):
        import fcntl
        trusted_file(CENTRAL)
        need(not os.path.lexists(CENTRAL/'active'), 'existing lease; no takeover')
        for path in LOCKS:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            stream = os.fdopen(fd, 'r+')
            self.held_locks.append(stream)
            trusted_file(path)
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = CENTRAL/'active'
        active.mkdir(mode=0o700)
        lease = dict(owner='A', scope=SCOPE, identity=MACHINE+':'+self.boot, pid=os.getpid(),
                     owner_start_ticks=start_ticks(Path('/proc/self')), window=self.package,
                     compute_authorized=True, max_submissions=23,
                     expires_monotonic_ns=time.monotonic_ns()+600_000_000_000)
        with (active/'lease.json').open('x', encoding='utf-8') as stream:
            json.dump(lease, stream); stream.flush(); os.fsync(stream.fileno())
        self.identity = dict(boot_id=self.boot, window_id=self.package, lease_sha256=digest(active/'lease.json'),
                             request_sha256=self.review_sha, protocol=PROTOCOL, manager_pid=os.getpid())
        self.guard()
        self.emit('LEASE_AND_DUAL_LOCKS_ACQUIRED', lease_sha256=self.identity['lease_sha256'], max_submissions=23)

    def prepare_worker_baseline(self):
        self.guard()
        self.kernel_checkpoint('before_single_worker')
        raw = self.kernel_gate.previous.encode('utf-8')
        need(0 < len(raw) <= 1048576 and not self.kernel_gate.blocked, 'worker baseline unavailable')
        stamp = time.monotonic_ns()
        with (self.source/'worker-baseline.raw.txt').open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        ready = {k: self.identity[k] for k in ('boot_id', 'window_id', 'manager_pid', 'lease_sha256', 'request_sha256')}
        ready.update(raw_sha256=digest(self.source/'worker-baseline.raw.txt'), read_monotonic_ns=stamp,
                     kernel_gate_allowed=True)
        with (self.source/'worker-baseline.json').open('x', encoding='utf-8') as stream:
            json.dump(ready, stream, sort_keys=True); stream.flush(); os.fsync(stream.fileno())
        self.identity['worker_baseline_sha256'] = digest(self.source/'worker-baseline.json')
        self.identity['plan_sha256'] = PLAN_SHA
        self.emit('PARENT_REVIEWED_WORKER_BASELINE', **ready,
                  worker_baseline_sha256=self.identity['worker_baseline_sha256'])

    def execute_lifecycle(self, initial):
        self.service('stop')
        self.wait_prepl_quiet()
        self.target.mkdir(mode=0o755)
        for name in ('a11-mlp.bit.bin', 'a11-mlp.dtbo', 'shell.json'):
            with (self.source/name).open('rb') as src, (self.target/name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
            need(digest(self.target/name) == digest(self.source/name), 'staged payload differs')
        self.remove(DEFAULT)
        check_removed(self.snapshot('default_removed'), False)
        self.command(['insmod', str(self.driver)], True)
        check_removed(self.snapshot('module_unbound'), True)
        need(Path('/sys/module/zocl/srcversion').read_text().strip() == '15F2AC2306CB3CB7257CFCB', 'module source differs')
        self.command(['dfx-mgr-client', '-load', self.package], True)
        check_loaded(self.snapshot('test_loaded'), self.package)
        self.no_users(module_loaded=True)
        self.prepare_worker_baseline()
        request = {k: self.identity[k] for k in ('boot_id', 'window_id', 'lease_sha256', 'request_sha256',
                                                'worker_baseline_sha256', 'plan_sha256')}
        self.worker = MlpBoundary(request, self.source/'worker-result.json',
                                             guard=self.guard, quarantine=self.park, emit=self.emit)
        self.worker.start(['/usr/bin/python3', '-B', '-I', str(self.source/'mlp_worker.py'),
                           '--source', str(self.source)],
                          device_lock_fd=self.held_locks[1].fileno(),
                          stdout_path=self.source/'worker.stdout.jsonl', stderr_path=self.source/'worker.stderr.txt')
        self.worker.pulse = lambda: pulse(self)
        result = self.worker.wait_normal(240)
        check_topology(self.snapshot('worker_exited_topology'), self.package)
        self.worker.check_release(self.observation)
        self.release_checked = True
        self.remove(self.package)
        check_removed(self.snapshot('test_removed'), True)
        self.no_users(module_loaded=True)
        self.command(['rmmod', 'zocl'], True)
        check_removed(self.snapshot('module_removed'), False)
        self.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = self.snapshot('default_restored')
        need(final['overlays'] == initial['overlays'] and final['module_refcount'] is None and
             not final['zocl_bound'] and not final['render_nodes'] and not final['device_holders'] and
             final['vart_sha256'] == initial['vart_sha256'], 'default restoration differs')
        self.service('start')
        self.snapshot('graphical_restored')
        self.kernel_checkpoint('final')
        for path, sha in {**BOOT_FILES, **LIBRARIES}.items():
            need(digest(path) == sha, 'platform file changed')
        self.guard()
        history = CENTRAL/'history'/self.package
        need(history.parent.is_dir() and not os.path.lexists(history), 'history target unavailable')
        (CENTRAL/'active').rename(history)
        receipt = dict(status=('PASS_MLP_23_AND_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT' if result['status']=='NORMAL_CLOSED_A11_MINIMAL' else 'FAILED_COMPUTE_NORMAL_RELEASE_REQUIRES_INDEPENDENT_AUDIT'),
                       boot_id=self.boot, kernel=KERNEL, worker_result=result, final=final,
                       lease_archive=str(history), compute_runs=result['real_submissions'],
                       explicit_requested_peak_bytes=2162688,
                       A11='NOT_PASSED_UNTIL_INDEPENDENT_FINAL_READBACK_AND_REQUIREMENT_AUDIT',
                       normal_kernel_restore='NOT_TESTED_IN_THIS_ENTRY')
        with (self.source/'mlp-receipt.json').open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2); stream.flush(); os.fsync(stream.fileno())
        self.emit('MLP_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED' if result['status']=='NORMAL_CLOSED_A11_MINIMAL' else 'FAILED_MLP_DEFAULT_PL_RESTORED', receipt=receipt)
        for stream in reversed(self.held_locks):
            stream.close()
        self.held_locks.clear()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-mlp-once', action='store_true')
    ap.add_argument('--source', type=Path)
    ap.add_argument('--review-sha256')
    args = ap.parse_args(argv)
    if not args.execute_authorized_mlp_once:
        print(json.dumps(dict(mode='PLAN_ONLY', scope=SCOPE, max_submissions=23,
                              requires_new_authorization=True, board_accepted=False)))
        return 0
    need(args.source is not None and args.review_sha256, 'new source/review required')
    trial = MlpTrial(args.source, args.review_sha256)
    try:
        trial.run()  # unchanged boot/hash/lease/thermal/memory and exclusive-attempt checks
    except BaseException as exc:
        if trial.held_locks:
            trial.park('MAINTENANCE_FAILURE: ' + type(exc).__name__ + ': ' + str(exc))
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
