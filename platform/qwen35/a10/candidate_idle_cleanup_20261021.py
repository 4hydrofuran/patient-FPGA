"""Cleanup ONLY the exact pre-bitstream stop from the authorized idle window.

No retry, test load, insmod, reboot, device open, BO or compute. Default is a plan.
This is not a continuation/reset of the latched trial gate. The exact observed
out-of-tree flag is reviewed solely to permit ordinary unbound-module removal.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
SOURCE = Path('/home/ubuntu/a10-candidate-idle-20261021-v3')
BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'
STOP_SHA = 'd5d19d7a5b16870e0e9c1ea32f4d6744783a877b8ec322f645dc9b23770dff80'
RAW_SHA = 'c44e83966105ce3f31fb75668a971474d1c9412479180dcb05098a892c9171ca'
IMPORT_HASHES = {
    'idle_board_trial.py': 'c59f91ab17a1a984115599441aa55dd1e56a190a1f4680b6a9518dc275ae7089',
    'kernel_log_gate.py': '2a9e5bb2a0cae4454277df1118103754ac043298cf729f98a1c9e4fd8a1ef396',
}


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def commands_allowed(argv, changing):
    require((changing and argv in [['rmmod', 'zocl'],
                                  ['dfx-mgr-client', '-load', 'k26-starter-kits']])
            or (not changing and argv == ['dfx-mgr-client', '-listPackage']),
            'outside unbound-cleanup-only scope')


def validate_stop(rows):
    require(rows[-1]['event'] == 'STOP_NO_AUTOMATIC_RECOVERY', 'no completed stop')
    writes = [r['argv'] for r in rows if r['event'] == 'COMMAND_BEGIN'
              and r['state_changing']]
    require(writes == [['dfx-mgr-client', '-remove', '0'],
                      ['insmod', '/usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko']],
            'not the unbound pre-bitstream stop')
    gates = [r for r in rows if r['event'] == 'KERNEL_LOG_GATE']
    last = gates[-1]
    require(last['reason'] == 'NEW_KERNEL_DIAGNOSTIC'
            and last['current_sha256'] == RAW_SHA
            and last['new_text'] ==
            '<4>[ 1224.225715] zocl: loading out-of-tree module taints kernel.\n',
            'different diagnostic; not reviewed')
    return next(r for r in rows if r['event'] == 'READBACK' and r['phase'] == 'initial')


def restored(final, initial):
    require(final['overlays'] == initial['overlays']
            and final['module_refcount'] is None
            and not final['zocl_bound'] and not final['render_nodes']
            and not final['device_holders'] and not final['accelerator_card_nodes']
            and final['fpga_state'] == 'operating'
            and final['vart_sha256'] == initial['vart_sha256'], 'restore readback mismatch')


def execute():
    for name, expected in IMPORT_HASHES.items():
        require(not (SOURCE / name).is_symlink() and sha(SOURCE / name) == expected,
                'stopped helper changed')
    sys.path.insert(0, str(SOURCE))
    from idle_board_trial import Trial, CENTRAL, MACHINE, DEFAULT, RESTORE, digest, check_removed, active_handle
    from kernel_log_gate import KernelLogBlocked
    import fcntl

    class Cleanup(Trial):
        boot = BOOT
        kernel_release = '6.8.12-a10irq1'
        temperature_limit_mC = 55000
        memory_reserve_KiB = 1048576
        reviewed_baseline_sha256 = RAW_SHA

        def __init__(self):
            self.log = Path('/home/ubuntu/a10-candidate-idle-cleanup-20261021-v2.jsonl').open('x')
            self.events = []

        def emit(self, event, **data):
            # Authoritative full bytes on board; do not flood the interactive TTY.
            import time
            row = dict(event=event, monotonic_s=time.monotonic(), **data)
            self.events.append(row)
            self.log.write(json.dumps(row) + '\n')
            self.log.flush()
            os.fsync(self.log.fileno())
            print(json.dumps({k: v for k, v in row.items()
                              if k not in ('raw_log', 'baseline_diagnostics', 'stdout')}),
                  flush=True)

        def command(self, argv, state_changing=False):
            commands_allowed(argv, state_changing)
            return super().command(argv, state_changing)

        def cleanup(self):
            require(os.geteuid() == 0 and os.uname().machine == 'aarch64'
                    and os.uname().release == self.kernel_release, 'root/kernel/architecture')
            require(sha(SOURCE / 'idle-result.jsonl') == STOP_SHA, 'stopped evidence changed')
            initial = validate_stop([json.loads(l) for l in
                                     (SOURCE / 'idle-result.jsonl').read_text().splitlines()])
            active = CENTRAL / 'active'
            for p in (CENTRAL, active, active / 'lease.json', CENTRAL / 'deployment.lock',
                      Path('/run/lock/patient-qwen-linear.lock')):
                require(p.exists() and not p.is_symlink() and p.stat().st_uid == 0
                        and not p.stat().st_mode & 0o022, 'untrusted lock: ' + str(p))
            self.deploy_lock = (CENTRAL / 'deployment.lock').open('r+')
            self.shared_lock = Path('/run/lock/patient-qwen-linear.lock').open('r+')
            for lock in (self.deploy_lock, self.shared_lock):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            lease_sha = digest(active / 'lease.json')
            lease = json.loads((active / 'lease.json').read_text())
            require(lease.get('owner') == 'A' and lease.get('scope') == 'A10_IDLE_PL_ONCE'
                    and lease.get('identity') == MACHINE + ':' + BOOT
                    and lease.get('compute_authorized') is False
                    and type(lease.get('pid')) is int and lease['pid'] > 1
                    and not Path('/proc', str(lease['pid'])).exists(), 'lease/old process changed')
            require(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT
                    and not Path('/state.txt').exists(), 'default/dfx temporary state differs')
            for name, expected in RESTORE.items():
                require(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == expected,
                        'restore source changed')
            check_removed(self.snapshot('cleanup_unbound_preflight'), True)
            self.kernel_checkpoint('exact_stop_review_cleanup_only', None)
            self.command(['rmmod', 'zocl'], True)
            check_removed(self.snapshot('driver_removed'), False)
            try:
                self.command(['dfx-mgr-client', '-load', DEFAULT], True)
            except KernelLogBlocked:
                # Capture independent final state even when the final load
                # emits warnings. Never resume hardware mutations or clear gate.
                self.emit('RESTORE_DIAGNOSTIC_STOP_READBACK_ONLY')
            ends = [r for r in self.events if r['event'] == 'COMMAND_END']
            require(ends[-1]['argv'] == ['dfx-mgr-client', '-load', DEFAULT]
                    and ends[-1]['exit_code'] == 0, 'restore call not known complete')
            final = self.snapshot('default_restored')
            restored(final, initial)
            active_handle(self.command(['dfx-mgr-client', '-listPackage']), DEFAULT)
            for name, expected in RESTORE.items():
                require(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == expected,
                        'restore source changed')
            # Evidence bookkeeping only. Normal recovery state is independently
            # proved; diagnostic gate remains latched and compute stays forbidden.
            require(digest(active / 'lease.json') == lease_sha, 'lease changed')
            history = CENTRAL / 'history'
            require(not history.is_symlink(), 'history symlink')
            history.mkdir(exist_ok=True)
            archived = history / 'a10-idle-candidate-20261021-cleanup.json'
            with archived.open('x') as output:
                json.dump(dict(lease=lease, source_sha256=lease_sha,
                               status='DEFAULT_RESTORED_NOT_CLEAN_ACCEPTANCE'), output)
                output.flush()
                os.fsync(output.fileno())
            (active / 'lease.json').unlink()
            active.rmdir()
            blocked = self.kernel_gate.blocked
            self.emit('DEFAULT_RESTORED_NO_COMPUTE', diagnostic_gate_blocked=blocked,
                      A10='NOT_PASSED', test_bitstream_loaded=False, compute_runs=0,
                      compute_BO_allocations=0, active_lease_archived=True)
            return 2 if blocked else 0

    trial = Cleanup()
    try:
        return trial.cleanup()
    except Exception as exc:
        trial.emit('CLEANUP_STOP_NO_RETRY', error=str(exc))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-authorized-cleanup-only', action='store_true')
    args = parser.parse_args()
    if args.execute_authorized_cleanup_only:
        raise SystemExit(execute())
    print(json.dumps(dict(status='PLAN_ONLY', board_contact=False,
                          commands=[['rmmod', 'zocl'],
                                    ['dfx-mgr-client', '-load', 'k26-starter-kits']],
                          compute=False, test_load=False)))
