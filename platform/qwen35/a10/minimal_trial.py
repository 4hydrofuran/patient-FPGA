"""A10 single small compute, preceded by verified IRQ teardown. No default run.

Only the independently pinned bundle and same reviewed boot are accepted.
Unknown hardware state retains process/locks; no timeout kill or forced cleanup.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid
sys.dont_write_bytecode = True
from idle_board_trial import (Trial, MACHINE, DEFAULT, CENTRAL, HASHES, RESTORE,
                              need, digest, active_handle, check_loaded, check_removed)
from minimal_gate import MinimalGate

BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'
KERNEL = '6.8.12-a10irq1'
PACKAGE = 'a10-vadd-minimal-20261021'
DRIVER = Path('/usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko')
DRIVER_SHA = '2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc'
BOOT_FILES = {
    '/boot/firmware/image.fit': 'b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9',
    '/boot/firmware/boot.scr.uimg': '690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc'}


class MinimalTrial(Trial):
    boot, kernel_release, package = BOOT, KERNEL, PACKAGE
    target = Path('/lib/firmware/xilinx') / PACKAGE
    driver, driver_sha256 = DRIVER, DRIVER_SHA
    temperature_limit_mC, memory_reserve_KiB = 55000, 1048576

    def __init__(self, source, sha):
        manifest = source / 'manifest.json'
        need(digest(manifest) == sha, 'bundle manifest differs')
        m = json.loads(manifest.read_text())
        need(set(p.name for p in source.iterdir()) == set(m['files']) | {'manifest.json'},
             'bundle inventory differs; no automatic rerun')
        for name, entry in m['files'].items():
            p = source / name
            need(p.is_file() and not p.is_symlink() and p.stat().st_size == entry['bytes']
                 and digest(p) == entry['sha256'], 'payload changed: ' + name)
        self.kernel_gate = MinimalGate()
        baseline = (source / 'baseline.raw.txt').read_bytes().decode('utf-8')
        need(hashlib.sha256(baseline.encode()).hexdigest() ==
             '9e568d2b6fcbb04548e13f2a4d263e8894bc89d22c4996b28a531b8936e79e3f',
             'reviewed baseline differs')
        need(self.kernel_gate.observe_action(BOOT, baseline, digest(source / 'baseline.raw.txt'),
                                            'none')['allowed'], 'baseline rejected')
        super().__init__(source)
        self.emit('MINIMAL_WINDOW', bundle_sha256=sha, boot=BOOT, kernel=KERNEL,
                  regression='CANCELLED_BY_USER', compute_n=32, compute_count=1,
                  source_review='kernel/module/main.c external provenance; drivers/of/overlay.c property lifetime retained; IRQ refcount never waived')

    def emit(self, event, **data):
        row = dict(event=event, monotonic_s=time.monotonic(), **data)
        self.log.write(json.dumps(row) + '\n')
        self.log.flush()
        os.fsync(self.log.fileno())
        print(json.dumps({k: v for k, v in row.items() if k not in
                          ('raw_log', 'new_text', 'stdout', 'stderr')})[:3500], flush=True)

    def kernel_checkpoint(self, phase, mutation):
        p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
        need(p.returncode == 0 and not p.stderr, 'kernel log unavailable')
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        raw = p.stdout.decode('utf-8')
        action = 'none'
        if phase == 'after_mutation':
            if mutation == ['insmod', str(DRIVER)]:
                action = 'insmod'
            elif mutation == ['dfx-mgr-client', '-load', PACKAGE]:
                action = 'load_test'
            elif mutation == ['dfx-mgr-client', '-load', DEFAULT]:
                action = 'load_default'
        result = self.kernel_gate.observe_action(boot, raw, None, action)
        self.emit('KERNEL_LOG_GATE', phase=phase, mutation=mutation, raw_log=raw, **result)
        need(result['allowed'], 'kernel gate stopped: ' + result['reason'])

    def command(self, argv, state_changing=False):
        read = [['dfx-mgr-client', '-listPackage']]
        write = [['dfx-mgr-client', '-load', PACKAGE], ['dfx-mgr-client', '-load', DEFAULT],
                 ['insmod', str(DRIVER)], ['rmmod', 'zocl']]
        remove = len(argv) == 3 and argv[:2] == ['dfx-mgr-client', '-remove'] and argv[2].isascii() and argv[2].isdigit()
        need((not state_changing and argv in read) or (state_changing and (argv in write or remove)),
             'outside minimal command allowlist')
        return super().command(argv, state_changing)

    def remove(self, package):
        self.snapshot('before_remove_' + package)
        handle = active_handle(self.command(['dfx-mgr-client', '-listPackage']), package)
        self.command(['dfx-mgr-client', '-remove', handle], True)

    def compute(self, lease, active):
        self.kernel_checkpoint('before_compute', None)
        need(not self.kernel_gate.blocked, 'kernel gate latched')
        check_loaded(self.snapshot('before_single_compute'), PACKAGE)
        approval = dict(schema='A10_VADD_SHORT_APPROVAL_V1', authorized=True,
                        platform_review_complete=True, recovery_review_complete=True,
                        review_scope='ONE_N32_ONLY_AFTER_THIS_BOOT_IDLE_TEARDOWN',
                        kernel_release=KERNEL, board_machine_id_sha256=MACHINE,
                        approved_boot_id=BOOT,
                        xclbin_sha256='9d1243508f887dfe7db76ad1f37984907fe39567bab1cb118403f7691ed98394',
                        xclbin_uuid='87b3bf55-dfd2-2b35-0a6a-55028f87deec')
        for kind in ('xrt_coreutil', 'xrt_core'):
            path = '/usr/lib/lib' + kind + '.so.2.18.0'
            approval[kind + '_path'], approval[kind + '_sha256'] = path, digest(path)
        with (self.source / 'approval.actual.json').open('x') as f:
            json.dump(approval, f, indent=2)
        lease.update(scope='A10_VADD_SHORT', token=uuid.uuid4().hex, expires_unix=time.time() + 300,
                     compute_authorized=True)
        with (active / 'lease.json').open('w') as f:
            json.dump(lease, f)
        self.emit('SINGLE_COMPUTE_AUTHORIZED_AFTER_IDLE_TEARDOWN', approval=approval)
        host = self.source / 'a10-vadd-short'
        host.chmod(0o755)
        argv = [str(host), '--execute-authorized-short', str(self.source / 'approval.actual.json'),
                str(self.source / 'vadd.xclbin'), str(self.source / 'compute.jsonl'), '7', '1']
        env = os.environ.copy()
        for key in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'XCL_EMULATION_MODE'):
            need(key not in env, 'loader/emulation override')
        env['A1_BOARD_LEASE'] = lease['token']
        # Host takes the SAME compute lock. Deployment lock and active lease stay.
        fcntl.flock(self.shared_lock, fcntl.LOCK_UN)
        self.emit('COMPUTE_COMMAND_BEGIN', argv=argv)
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            out, err = p.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            self.emit('UNKNOWN_COMPUTE_STATE_PARKED_NO_KILL', pid=p.pid)
            while True:
                time.sleep(30)
        self.emit('COMPUTE_COMMAND_END', exit_code=p.returncode,
                  stdout=out.decode(errors='replace'), stderr=err.decode(errors='replace'))
        need(p.returncode == 0, 'compute failed; no automatic cleanup')
        fcntl.flock(self.shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rows = [json.loads(l) for l in (self.source / 'compute.jsonl').read_text().splitlines()]
        verified = [r for r in rows if r['event'] == 'VERIFIED']
        need(len(verified) == 1 and verified[0]['n'] == 32 and verified[0]['pass'] is True
             and rows[-1]['event'] == 'BATCH_COMPLETE' and rows[-1]['verified'] == 1,
             'compute evidence incomplete')
        self.kernel_checkpoint('after_compute', None)
        check_loaded(self.snapshot('single_compute_finished_no_holders'), PACKAGE)

    def run(self):
        need(os.geteuid() == 0 and os.uname().machine == 'aarch64'
             and os.uname().release == KERNEL, 'wrong execution platform')
        self.kernel_checkpoint('preflight', None)
        initial = self.snapshot('initial')
        need(initial['overlays'] == {DEFAULT + '_image_1': 'applied'} and
             initial['module_refcount'] is None and not initial['zocl_bound'] and
             not initial['render_nodes'] and not initial['device_holders'], 'initial state differs')
        for p, sha in BOOT_FILES.items():
            need(digest(p) == sha, 'original boot file differs')
        need(digest(DRIVER) == DRIVER_SHA, 'driver differs')
        need(not self.target.exists() and not CENTRAL.is_symlink() and
             CENTRAL.stat().st_uid == 0 and not CENTRAL.stat().st_mode & 0o022,
             'untrusted or existing target/lease directory')
        need(not Path('/state.txt').exists(), 'existing libdfx state file')
        need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT, 'default differs')
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore hash differs')
        for name, sha in HASHES.items():
            need(digest(self.source / name) == sha and not os.path.lexists('/lib/firmware/' + name),
                 'test hash or existing firmware name')
        self.deploy_lock = (CENTRAL / 'deployment.lock').open('a+')
        fcntl.flock(self.deploy_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.shared_lock = Path('/run/lock/patient-qwen-linear.lock').open('a+')
        fcntl.flock(self.shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = CENTRAL / 'active'
        active.mkdir()
        lease = dict(owner='A', scope='A10_MINIMAL_IDLE_THEN_ONE', identity=MACHINE + ':' + BOOT,
                     pid=os.getpid(), issued_unix=time.time(), expires_unix=time.time() + 600,
                     compute_authorized=False, authorization='USER_MAXIMALLY_SIMPLIFY_AND_COMPLETE_20261021')
        with (active / 'lease.json').open('x') as f:
            json.dump(lease, f)
        self.target.mkdir()
        for name in (*HASHES, 'shell.json'):
            with (self.source / name).open('rb') as src, (self.target / name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
            need(digest(self.source / name) == digest(self.target / name), 'staging mismatch')
        self.remove(DEFAULT)
        check_removed(self.snapshot('default_removed'), False)
        self.command(['insmod', str(DRIVER)], True)
        check_removed(self.snapshot('driver_unbound'), True)
        self.command(['dfx-mgr-client', '-load', PACKAGE], True)
        check_loaded(self.snapshot('test_idle_loaded'), PACKAGE)
        self.remove(PACKAGE)
        check_removed(self.snapshot('test_idle_removed'), True)
        self.emit('IRQ_TEARDOWN_VERIFIED_THIS_BOOT_NO_COMPUTE')
        self.command(['dfx-mgr-client', '-load', PACKAGE], True)
        self.compute(lease, active)
        self.remove(PACKAGE)
        check_removed(self.snapshot('computed_test_removed'), True)
        self.command(['rmmod', 'zocl'], True)
        check_removed(self.snapshot('driver_removed'), False)
        self.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = self.snapshot('default_restored')
        need(final['overlays'] == initial['overlays'] and final['module_refcount'] is None and
             not final['device_holders'] and not final['zocl_bound'] and not final['render_nodes']
             and final['fpga_state'] == 'operating' and final['vart_sha256'] == initial['vart_sha256'],
             'restore differs')
        active_handle(self.command(['dfx-mgr-client', '-listPackage']), DEFAULT)
        for p, sha in BOOT_FILES.items():
            need(digest(p) == sha, 'original boot file changed')
        self.kernel_checkpoint('final_readback', None)
        history = CENTRAL / 'history' / 'a10-minimal-20261021.json'
        need(not history.exists(), 'history exists')
        (active / 'lease.json').rename(history)
        active.rmdir()
        self.emit('MINIMAL_WINDOW_COMPLETE', compute_runs=1, n=32,
                  regression='CANCELLED_BY_USER', default_restored=True,
                  acceptance='PENDING_PC_EVIDENCE_AUDIT', limitations=[
                      'bounded overlay property lifetime; no repeated swapping qualification',
                      'candidate boot only; default boot remains original',
                      'one small vector-add is not model/MLP acceptance',
                      'no pressure, bandwidth benchmark, maximum BO, or injected fault'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-minimal', action='store_true')
    ap.add_argument('--bundle-sha256')
    a = ap.parse_args()
    need(a.execute_authorized_minimal and a.bundle_sha256, 'explicit authorized switch and hash required')
    t = MinimalTrial(Path(__file__).resolve().parent, a.bundle_sha256)
    try:
        t.run()
    except Exception as exc:
        t.emit('STOP_NO_AUTOMATIC_RECOVERY', error=str(exc), error_type=type(exc).__name__)
        raise


if __name__ == '__main__':
    main()
