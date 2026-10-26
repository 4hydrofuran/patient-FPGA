"""One reviewed idle XRT process lifecycle and default-PL restoration.

Default is PLAN_ONLY. This entry never reboots, submits compute, allocates a
compute BO, rewrites boot/QSPI, repairs automatically or reuses an old lease.
Any failure after lock acquisition retains the manager and locks for review.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import struct
import subprocess
import sys
import time

from accelerator_release_gate_v2 import collect, require_no_users, require_release, start_ticks
from idle_board_trial import Trial, RESTORE, active_handle, check_loaded, check_removed
from isolated_idle_policy import (ASSETS, BOOT_FILES, CENTRAL, DEFAULT, KERNEL, LIBRARIES,
                                  LOCKS, MACHINE, SCOPE, digest, load_json, need,
                                  trusted_file, validate_review, verify_bundle, verify_owner)
from minimal_gate import MinimalGate
from xrt_worker_boundary import IdleWorkerBoundary


def check_topology(state, package):
    details = state['zocl_binding_details']
    children = [row for row in details if row['driver'] == 'cu_drv' and
                re.fullmatch(r'CU\.\d+\.auto', row['name'])]
    main = [row for row in details if row['driver'] == 'zocl-drm' and row['name'] == 'axi:zyxclmm_drm']
    need(len(main) == 1 and len(children) in (0, 1), 'unexpected CU topology')
    need(all(Path(row['path']).parent == Path(main[0]['path']) for row in children), 'CU parent differs')
    reduced = dict(state, zocl_binding_details=[r for r in details if r not in children],
                   zocl_bound=[r['name'] for r in details if r not in children])
    check_loaded(reduced, package)


class IsolatedIdleTrial(Trial):
    kernel_release = KERNEL
    temperature_limit_mC = 55000
    memory_reserve_KiB = 1048576

    def __init__(self, source, review_sha):
        self.source = Path(source).resolve()
        need(digest(self.source / 'review.json') == review_sha, 'review SHA mismatch')
        self.review = validate_review(load_json(self.source / 'review.json'))
        self.manifest = verify_bundle(self.source, self.review['bundle_sha256'])
        self.boot, self.package = self.review['boot_id'], self.review['window_id']
        self.target = Path('/lib/firmware/xilinx') / self.package
        self.driver, self.driver_sha256 = self.source / 'zocl.refcount.ko', ASSETS['zocl.refcount.ko']
        self.review_sha = review_sha
        need(not any(os.path.lexists(self.source / name) for name in
                     ('attempt.json', 'lifecycle.jsonl', 'worker-result.json', 'idle-receipt.json')),
             'consumed execution directory: replay forbidden')
        self.log = None
        self.held_locks = []
        self.identity = None
        self.kernel_gate = MinimalGate()
        self.worker = None
        self.release_checked = False
        self.gdm_isolated = False
        self.pl_mutation_started = False

    def emit(self, event, **data):
        if 'monotonic_ns' in data:
            data['observation_monotonic_ns'] = data.pop('monotonic_ns')
        row = dict(event=event, monotonic_ns=time.monotonic_ns(), boot_id=self.boot,
                   window_id=self.package, manager_pid=os.getpid())
        for key, value in data.items():
            need(key not in row or row[key] == value, 'event identity field differs: ' + key)
            row[key] = value
        text = json.dumps(row)
        self.log.write(text + '\n')
        self.log.flush()
        os.fsync(self.log.fileno())
        visible = {key: row[key] for key in ('event', 'window_id')}
        visible.update({key: row[key] for key in ('phase', 'action', 'reason') if key in row})
        print(json.dumps(visible), flush=True)

    def park(self, reason):
        try:
            self.emit('QUARANTINED_MANAGER_AND_LOCKS_RETAINED', reason=reason,
                      compute_authorized=False, automatic_cleanup=False)
        finally:
            while True:
                time.sleep(30)

    def guard(self, identity=None):
        if identity is not None:
            need(identity == self.identity, 'worker identity differs from active manager')
        verify_owner(self.identity, self.review)
        if self.gdm_isolated:
            state = subprocess.run(['systemctl', 'is-active', 'gdm.service'], capture_output=True, timeout=3)
            need(state.stdout.strip() == b'inactive', 'graphical isolation lost')
        self.snapshot('identity_health_guard')
        return True

    def kernel_checkpoint(self, phase, mutation=None):
        try:
            p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
            need(p.returncode == 0 and not p.stderr, 'kernel log unavailable')
            action, verified = 'none', False
            if phase == 'after_mutation':
                if mutation == ['insmod', str(self.driver)]:
                    action = 'insmod'
                elif mutation == ['dfx-mgr-client', '-load', self.package]:
                    self.verify_irq_dt()
                    action, verified = 'load_test', True
                elif mutation == ['dfx-mgr-client', '-load', DEFAULT]:
                    action = 'load_default'
            raw = p.stdout.decode('utf-8')
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            result = self.kernel_gate.observe_action(boot, raw, None, action, verified)
            need(result.get('action', action) == action, 'kernel action result differs')
            self.emit('KERNEL_LOG_GATE', phase=phase, raw_log=raw, **dict(result, action=action))
            need(result['allowed'], 'kernel gate refused: ' + result['reason'])
        except BaseException:
            self.kernel_gate.blocked = True
            raise

    def verify_irq_dt(self):
        base = Path('/sys/firmware/devicetree/base/axi')
        intc = base / 'interrupt-controller@80020000'
        raw = (base / 'zyxclmm_drm/interrupts-extended').read_bytes()
        parent = int.from_bytes((intc / 'phandle').read_bytes(), 'big')
        need(int.from_bytes((intc / '#interrupt-cells').read_bytes(), 'big') == 2 and len(raw) == 384,
             'IRQ dimensions differ')
        need([struct.unpack('>III', raw[n:n+12]) for n in range(0, len(raw), 12)] ==
             [(parent, n, 4) for n in range(32)], 'IRQ sequence/parent/flags differ')
        need(int.from_bytes((intc / 'xlnx,num-intr-inputs').read_bytes(), 'big') == 32,
             'IRQ count differs')
        check_loaded(self.snapshot('irq_topology'), self.package)
        self.emit('EXACT_IRQ_DT_VERIFIED', raw_hex=raw.hex(), count=32)

    def command(self, argv, state_changing=False):
        readonly = argv == ['dfx-mgr-client', '-listPackage']
        changes = [['insmod', str(self.driver)], ['rmmod', 'zocl'],
                   ['dfx-mgr-client', '-load', self.package], ['dfx-mgr-client', '-load', DEFAULT]]
        removing = len(argv) == 3 and argv[:2] == ['dfx-mgr-client', '-remove'] and argv[2].isascii() and argv[2].isdigit()
        need((not state_changing and readonly) or (state_changing and (argv in changes or removing)),
             'command outside idle allowlist')
        if state_changing:
            self.guard()
            self.pl_mutation_started = True  # includes an uncertain first command
        return super().command(argv, state_changing)

    def service(self, action):
        need(action in ('stop', 'start'), 'unsupported graphical service action')
        self.guard()
        self.kernel_checkpoint('before_gdm_' + action)
        proc = subprocess.Popen(['systemctl', action, 'gdm.service'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, close_fds=True)
        try:
            out, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            self.park('GDM_ACTION_UNKNOWN_NO_KILL')
        need(proc.returncode == 0, 'graphical service action failed')
        self.emit('GDM_ACTION', action=action, exit_code=proc.returncode,
                  stdout=out.decode(errors='replace'), stderr=err.decode(errors='replace'))
        state = subprocess.run(['systemctl', 'is-active', 'gdm.service'], capture_output=True, timeout=3)
        need(state.stdout.strip() == (b'inactive' if action == 'stop' else b'active'), 'graphical state differs')
        self.gdm_isolated = action == 'stop'
        self.kernel_checkpoint('after_gdm_' + action)

    def observation(self):
        self.kernel_checkpoint('before_process_scan')
        scan = collect(allow_ps_display=True)
        ref = Path('/sys/module/zocl/refcnt')
        refs = int(ref.read_text().strip()) if ref.exists() else None
        self.kernel_checkpoint('after_process_scan')
        self.emit('PROCESS_RELEASE_OBSERVATION', scan=scan, module_refcount=refs,
                  kernel_gate_allowed=not self.kernel_gate.blocked)
        return scan, refs, not self.kernel_gate.blocked

    def no_users(self, *, module_loaded):
        scan, refs, allowed = self.observation()
        if module_loaded:
            require_release(scan, refs, allowed, boot_id=self.boot)
        else:
            need(refs is None and not Path('/sys/module/zocl').exists(), 'module unexpectedly present')
            require_no_users(scan, allowed, boot_id=self.boot)

    def wait_prepl_quiet(self):
        """Bounded readiness reads ONLY before the first PL command.

        Stopping GDM may leave short-lived user processes exiting. Preserve
        incomplete observations; require two complete identical process sets.
        This is NOT a retry of hardware, nor a post-XRT release exception.
        """
        need(not self.pl_mutation_started and self.worker is None and self.gdm_isolated,
             'readiness wait only before PL/native activity with GDM stopped')
        previous = None
        time.sleep(2)
        for attempt in range(4):
            scan, refs, allowed = self.observation()
            need(refs is None and not Path('/sys/module/zocl').exists(), 'module unexpectedly present')
            try:
                require_no_users(scan, allowed, boot_id=self.boot)
            except RuntimeError as exc:
                # No new kernel diagnostics, users, maps, permission errors or
                # wrong identity are converted to an acceptable observation.
                issues = scan.get('scan_issues', [])
                transient = (allowed is True and scan.get('boot_id') == self.boot == scan.get('boot_id_after')
                             and issues and all(row['reason'] in ('PROCESS_SET_CHANGED',
                                 'ValueError: PROCESS_OR_FD_TABLE_CHANGED') or
                                 row['reason'].startswith('FileNotFoundError:') for row in issues))
                need(transient and not scan.get('device_holders') and not scan.get('device_mappings'), str(exc))
                self.emit('PREPL_INCOMPLETE_READ_PRESERVED', readiness_attempt=attempt+1, reason=str(exc))
                previous = None
            else:
                current = scan['inspected_processes']
                if previous == current:
                    self.emit('PREPL_TWO_COMPLETE_QUIET_READS', readiness_attempt=attempt+1)
                    return
                previous = current
            if attempt < 3:
                time.sleep(1)
        raise RuntimeError('PREPL_QUIET_NOT_ESTABLISHED_NO_HARDWARE_ATTEMPT')

    def remove(self, package):
        if package == self.package:
            need(self.release_checked and self.worker is not None and
                 self.worker.state == 'RELEASE_PRECHECK_PASSED', 'worker exit/release gate not passed')
            self.release_checked = False  # one-time consumption, never repeat remove
        else:
            need(package == DEFAULT and self.worker is None, 'unexpected removal order')
        handle = active_handle(self.command(['dfx-mgr-client', '-listPackage']), package)
        self.command(['dfx-mgr-client', '-remove', handle], True)

    def claim(self):
        import fcntl
        trusted_file(CENTRAL)
        need(not os.path.lexists(CENTRAL / 'active'), 'existing lease, no takeover')
        for path in LOCKS:
            fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            stream = os.fdopen(fd, 'r+')
            self.held_locks.append(stream)
            trusted_file(path)
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = CENTRAL / 'active'
        active.mkdir(mode=0o700)
        lease = dict(owner='A', scope=SCOPE, identity=MACHINE + ':' + self.boot,
                     pid=os.getpid(), owner_start_ticks=start_ticks(Path('/proc/self')),
                     window=self.package, compute_authorized=False,
                     expires_monotonic_ns=time.monotonic_ns() + 300_000_000_000)
        with (active / 'lease.json').open('x', encoding='utf-8') as stream:
            json.dump(lease, stream)
            stream.flush()
            os.fsync(stream.fileno())
        self.identity = dict(boot_id=self.boot, window_id=self.package,
                             lease_sha256=digest(active / 'lease.json'), request_sha256=self.review_sha,
                             protocol='a10-isolated-idle-worker-v1', manager_pid=os.getpid())
        self.guard()
        self.emit('LEASE_AND_DUAL_LOCKS_ACQUIRED', lease_sha256=self.identity['lease_sha256'])

    def run(self):
        need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and os.uname().release == KERNEL,
             'wrong root/platform/kernel')
        for p in (self.source, self.source / 'review.json', self.source / 'baseline.raw.txt'):
            trusted_file(p)
        need(digest('/etc/machine-id') == MACHINE, 'wrong board identity')
        need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'wrong boot')
        age = time.monotonic_ns() - self.review['baseline_read_uptime_ns']
        need(0 <= age <= 120_000_000_000, 'fresh baseline older than 120 seconds')
        need(digest(self.source / 'baseline.raw.txt') == self.review['baseline_sha256'], 'baseline changed')
        baseline = (self.source / 'baseline.raw.txt').read_bytes().decode('utf-8')
        need(self.kernel_gate.observe_action(self.boot, baseline, self.review['baseline_sha256'], 'none')['allowed'],
             'baseline rejected')
        signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT})
        os.umask(0o077)
        with (self.source / 'attempt.json').open('x', encoding='utf-8') as stream:
            json.dump(dict(review_sha256=self.review_sha, boot_id=self.boot), stream)
        self.log = (self.source / 'lifecycle.jsonl').open('x', encoding='utf-8')
        self.kernel_checkpoint('initial_baseline_continuity')
        initial = self.snapshot('initial')
        need(initial['overlays'] == {DEFAULT + '_image_1': 'applied'} and initial['module_refcount'] is None
             and not initial['zocl_bound'] and not initial['render_nodes'] and not initial['device_holders'],
             'initial default state differs')
        for path, sha in {**BOOT_FILES, **LIBRARIES}.items():
            need(digest(path) == sha, 'platform file hash differs: ' + path)
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'default PL hash differs')
        need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT, 'default configuration differs')
        need(not os.path.lexists(self.target) and not Path('/state.txt').exists(), 'existing staging/dfx state')
        for name in ('a1-vadd.bit.bin', 'a1-vadd.dtbo'):
            need(not os.path.lexists('/lib/firmware/' + name), 'firmware extraction would overwrite')
        need(load_json(self.source / 'shell.json') == dict(shell_type='XRT_FLAT', num_pl_slots=1, num_aie_slots=0),
             'shell metadata differs')
        self.claim()
        self.execute_lifecycle(initial)

    def execute_lifecycle(self, initial):
        """Hardware steps; only run() may enter this after all preconditions."""
        self.service('stop')
        self.wait_prepl_quiet()
        self.target.mkdir(mode=0o755)
        for name in ('a1-vadd.bit.bin', 'a1-vadd.dtbo', 'shell.json'):
            with (self.source / name).open('rb') as src, (self.target / name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
            need(digest(self.target / name) == digest(self.source / name), 'staged bytes differ')
        self.remove(DEFAULT)
        check_removed(self.snapshot('default_removed'), False)
        self.command(['insmod', str(self.driver)], True)
        check_removed(self.snapshot('module_unbound'), True)
        need(Path('/sys/module/zocl/srcversion').read_text().strip() == '15F2AC2306CB3CB7257CFCB', 'module source differs')
        self.command(['dfx-mgr-client', '-load', self.package], True)
        check_loaded(self.snapshot('test_loaded'), self.package)
        self.no_users(module_loaded=True)
        request = {key: self.identity[key] for key in ('boot_id', 'window_id', 'lease_sha256', 'request_sha256')}
        self.worker = IdleWorkerBoundary(request, self.source / 'worker-result.json',
                                         guard=self.guard, quarantine=self.park, emit=self.emit)
        self.worker.start(['/usr/bin/python3', '-B', '-I', str(self.source / 'isolated_idle_entry.py'),
                           '--execute-isolated-idle', '--source', str(self.source)],
                          stdout_path=self.source / 'worker.stdout.jsonl', stderr_path=self.source / 'worker.stderr.txt')
        result = self.worker.wait_normal(15)
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
        need(final['overlays'] == initial['overlays'] and final['module_refcount'] is None
             and not final['zocl_bound'] and not final['render_nodes'] and not final['device_holders']
             and final['vart_sha256'] == initial['vart_sha256'], 'default restoration differs')
        self.service('start')
        self.snapshot('graphical_restored')
        self.kernel_checkpoint('final')
        for path, sha in {**BOOT_FILES, **LIBRARIES}.items():
            need(digest(path) == sha, 'platform file changed')
        self.guard()
        history = CENTRAL / 'history' / self.package
        need(history.parent.is_dir() and not os.path.lexists(history), 'history target unavailable')
        (CENTRAL / 'active').rename(history)
        receipt = dict(status='PASS_IDLE_XRT_PROCESS_LIFECYCLE_ONLY', boot_id=self.boot, kernel=KERNEL,
                       worker_result=result, final=final, lease_archive=str(history), compute_runs=0,
                       explicit_compute_bo_allocations=0, A10='NOT_PASSED_POSTCOMPUTE_VERIFICATION_OPEN',
                       normal_kernel_restore='NOT_TESTED_IN_THIS_ENTRY')
        with (self.source / 'idle-receipt.json').open('x', encoding='utf-8') as stream:
            json.dump(receipt, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        self.emit('IDLE_LIFECYCLE_COMPLETE_DEFAULT_PL_RESTORED', receipt=receipt)
        for stream in reversed(self.held_locks):
            stream.close()
        self.held_locks.clear()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-idle-once', action='store_true')
    ap.add_argument('--source', type=Path)
    ap.add_argument('--review-sha256')
    args = ap.parse_args(argv)
    if not args.execute_authorized_idle_once:
        print(json.dumps(dict(mode='PLAN_ONLY', scope=SCOPE, new_compute_runs=0,
                              needs_fresh_irq2_boot=True, board_accepted=False)))
        return 0
    need(args.source is not None and args.review_sha256, 'fresh source/review required')
    trial = IsolatedIdleTrial(args.source, args.review_sha256)
    try:
        trial.run()
    except BaseException as exc:
        if trial.held_locks:
            trial.park('MAINTENANCE_FAILURE: ' + type(exc).__name__ + ': ' + str(exc))
        raise
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
