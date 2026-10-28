"""Prepared cleanup for the stopped idle trial. No default execution permission.

Never reruns the trial, loads a test bitstream, force-unloads or resets anything.
The separate user cleanup confirmation is required before invoking this entry.
"""
import argparse
import json
import os
from pathlib import Path

from idle_board_trial import (Trial, BOOT, MACHINE, PACKAGE, DEFAULT, CENTRAL,
                              TARGET, HASHES, RESTORE, active_handle, check_loaded,
                              check_removed, digest, need)

OLD = Path('/home/ubuntu/a10-idle-once-20261019-v1')
OLD_LOG_SHA = '278f3efc3e45e1772b3720c09ae27e4eb4e3f4bf7ff9c2238ab59ab740fd337a'
OLD_SCRIPT_SHA = '9ecb264866d8f7bd7d2a0345e0b88bce82dcbdf4b5855a403b56370be7849b84'


def cleanup_lease_gate(lease):
    need(lease.get('owner') == 'A' and lease.get('scope') == 'A10_IDLE_PL_ONCE' and
         lease.get('identity') == MACHINE + ':' + BOOT and lease.get('compute_authorized') is False,
         'not the stopped idle lease')
    need(type(lease.get('pid')) is int and lease['pid'] > 1, 'lease PID missing')


def cleanup_command_gate(argv, changing):
    readonly = [['dfx-mgr-client', '-listPackage'], ['dmesg', '--color=never']]
    normal = [['rmmod', 'zocl'], ['dfx-mgr-client', '-load', DEFAULT]]
    remove = (len(argv) == 3 and argv[:2] == ['dfx-mgr-client', '-remove'] and
              argv[2].isascii() and argv[2].isdigit())
    need((not changing and argv in readonly) or (changing and (argv in normal or remove)),
         'outside cleanup-only command allowlist')


def restored_gate(final, initial):
    need(final['overlays'] == initial['overlays'] and final['module_refcount'] is None and
         not final['zocl_bound'] and not final['render_nodes'] and not final['device_holders'] and
         not final.get('accelerator_card_nodes') and final['fpga_state'] == 'operating' and
         final['vart_sha256'] == initial['vart_sha256'], 'default restore readback mismatch')


class Cleanup(Trial):
    def __init__(self, source):
        self.source = source
        self.log = (source / 'cleanup-result.jsonl').open('x', encoding='utf-8')

    def command(self, argv, state_changing=False):
        cleanup_command_gate(argv, state_changing)
        return super().command(argv, state_changing)

    def run(self):
        import fcntl
        need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and
             os.uname().release == '6.8.0-1015-xilinx', 'wrong root/kernel/architecture')
        need(digest(OLD / 'idle-result.jsonl') == OLD_LOG_SHA and
             digest(OLD / 'idle_board_trial.py') == OLD_SCRIPT_SHA, 'stopped evidence changed')
        rows = [json.loads(line) for line in (OLD / 'idle-result.jsonl').read_text().splitlines()]
        initial = rows[0]
        need(initial['event'] == 'READBACK' and initial['phase'] == 'initial' and
             rows[-1]['event'] == 'STOP_NO_AUTOMATIC_RECOVERY', 'unexpected prior execution')
        active = CENTRAL / 'active'
        for p in (CENTRAL, active, active / 'lease.json', CENTRAL / 'deployment.lock',
                  Path('/run/lock/patient-qwen-linear.lock')):
            need(p.exists() and not p.is_symlink() and p.stat().st_uid == 0 and
                 not (p.stat().st_mode & 0o022), 'untrusted/missing lock path: ' + str(p))
        self.deploy_lock = (CENTRAL / 'deployment.lock').open('r+')
        fcntl.flock(self.deploy_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.shared_lock = Path('/run/lock/patient-qwen-linear.lock').open('r+')
        fcntl.flock(self.shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lease_sha = digest(active / 'lease.json')
        lease = json.loads((active / 'lease.json').read_text())
        cleanup_lease_gate(lease)
        need(not Path('/proc', str(lease['pid'])).exists(), 'prior PID exists; cannot reconcile automatically')
        need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT, 'default selection changed')
        need(not Path('/state.txt').exists(), 'unexpected libdfx temporary state')
        for name, sha in HASHES.items():
            need(digest(TARGET / name) == sha, 'test package changed')
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore material changed')
        before = self.snapshot('cleanup_preflight')
        check_loaded(before)
        need(type(before['module_refcount']) is int and before['module_refcount'] == 0 and
             before['vart_sha256'] == initial['vart_sha256'], 'reference/vart mismatch')
        self.command(['dmesg', '--color=never'])
        handle = active_handle(self.command(['dfx-mgr-client', '-listPackage']), PACKAGE)
        self.emit('CLEANUP_ONLY_BEGIN', source_lease_sha256=lease_sha, compute_authorized=False)
        self.command(['dfx-mgr-client', '-remove', handle], True)
        check_removed(self.snapshot('test_removed'), True)
        self.command(['rmmod', 'zocl'], True)
        check_removed(self.snapshot('driver_removed'), False)
        self.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = self.snapshot('default_restored')
        restored_gate(final, initial)
        active_handle(self.command(['dfx-mgr-client', '-listPackage']), DEFAULT)
        self.command(['dmesg', '--color=never'])
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore source changed')
        need(digest(active / 'lease.json') == lease_sha, 'lease changed during cleanup')
        history = CENTRAL / 'history'
        need(not history.is_symlink(), 'history symlink')
        history.mkdir(exist_ok=True)
        destination = history / 'a10-idle-20261019-cleanup.json'
        # O_EXCL snapshot, then unlink only the exact validated tiny active lease.
        with destination.open('x', encoding='utf-8') as stream:
            stream.write((active / 'lease.json').read_text())
            stream.flush(); os.fsync(stream.fileno())
        (active / 'lease.json').unlink()
        active.rmdir()
        self.emit('DEFAULT_RESTORED_CLEANUP_COMPLETE', original_trial_exit=1,
                  compute_runs=0, A10='NOT_PASSED', staged_artifacts_retained=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-user-confirmed-cleanup-only', action='store_true')
    a = ap.parse_args()
    need(a.execute_user_confirmed_cleanup_only, 'separate user confirmation required')
    trial = Cleanup(Path(__file__).resolve().parent)
    try:
        trial.run()
    except Exception as exc:
        trial.emit('CLEANUP_STOP_NO_RETRY', error=str(exc), error_type=type(exc).__name__)
        raise
