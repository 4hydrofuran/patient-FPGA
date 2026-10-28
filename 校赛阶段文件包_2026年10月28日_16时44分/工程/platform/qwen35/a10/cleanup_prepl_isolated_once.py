"""One explicitly authorized cleanup of the proven PRE-PL Python waiter only.

NOT a generic kill/unload/recovery tool. Does not invoke any PL or XRT API.
An exact pidfd prevents PID reuse; SIGUSR1 terminates this known signal-default
waiter (not a graceful manager exit). Never SIGKILL, kernel reset or reboot.
"""
import hashlib
import json
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

ROOT = Path('/var/lib/kv260-a10/a10-isolated-idle-20261023-v3')
BOOT = 'c5baeabe-273d-447e-b323-ff07dd7af201'
PID, TICKS = 3887, 144649
LOG_SHA = 'e3314a4b53936ecc4b041edb3e4a286c4efbd8f44d661ab7fcb27aa1beb0e6ea'
LEASE_SHA = '51cc97732d7d4d0645e015e70c757a55009242760cb2668eeebc3580d12c19f1'
KLOG_SHA = 'bb70a7d9357dd63e49b010cc9059d6a9459b6d755eaf9ef2eed97d36b522e71d'


def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def validate_log(raw):
    need(hashlib.sha256(raw).hexdigest() == LOG_SHA, 'reviewed pre-PL log changed')
    rows = [json.loads(r) for r in raw.splitlines()]
    permitted = {'KERNEL_LOG_GATE', 'READBACK', 'LEASE_AND_DUAL_LOCKS_ACQUIRED',
                 'GDM_ACTION', 'PROCESS_RELEASE_OBSERVATION', 'QUARANTINED_MANAGER_AND_LOCKS_RETAINED'}
    need(all(row['event'] in permitted for row in rows), 'hardware/unknown event in log')
    need(all(row.get('allowed') is True for row in rows if row['event'] == 'KERNEL_LOG_GATE'), 'latched kernel fault')
    service = [row for row in rows if row['event'] == 'GDM_ACTION']
    need(len(service) == 1 and service[0]['action'] == 'stop' and service[0]['exit_code'] == 0, 'unexpected service history')
    need(rows[-1]['event'] == 'QUARANTINED_MANAGER_AND_LOCKS_RETAINED' and
         rows[-1]['reason'] == 'MAINTENANCE_FAILURE: RuntimeError: PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT',
         'wrong quarantine cause')


def main():
    import fcntl
    need(os.geteuid() == 0 and os.uname().release == '6.8.12-a10irq2', 'exact root kernel required')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT, 'boot changed')
    need(hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest() ==
         'b8d9c8761602422661104492c317a456507684dfc04b65cb2a116173fefa8b9a', 'source pin changed')
    sys.path.insert(0, str(ROOT))
    from isolated_idle_policy import MACHINE, LOCKS, digest, lock_owned, trusted_file
    need(digest('/etc/machine-id') == MACHINE, 'board changed')
    validate_log((ROOT / 'lifecycle.jsonl').read_bytes())
    active = Path('/var/lock/kv260-a1/active')
    need(digest(active / 'lease.json') == LEASE_SHA, 'lease changed')
    for path in (ROOT, active, active / 'lease.json', *LOCKS):
        trusted_file(path)
    archive = Path('/var/lock/kv260-a1/history/a10-isolated-idle-20261023-v3-prepl-aborted')
    need(not os.path.lexists(archive), 'cleanup already consumed')

    def hardware_absent():
        need(not Path('/sys/module/zocl').exists() and
             not Path('/lib/firmware/xilinx/a10-isolated-idle-20261023-v3').exists(), 'hardware touched')
        need(not list(Path('/dev/dri').glob('render*')), 'render device present')
        overlay = Path('/sys/kernel/config/device-tree/overlays')
        need({q.name: (q/'status').read_text().strip() for q in overlay.iterdir() if q.is_dir()} ==
             {'k26-starter-kits_image_1': 'applied'}, 'default overlay differs')
        need(not (ROOT/'worker.stdout.jsonl').exists() and not (ROOT/'worker-result.json').exists(), 'worker touched')
        temps = [int(q.read_text()) for q in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        need(temps and all(0 < t < 55000 for t in temps), 'temperature limit')
        return temps

    def log_bytes():
        p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
        need(p.returncode == 0 and not p.stderr, 'cannot read kernel')
        return p.stdout

    hardware_absent()
    before = log_bytes()
    need(hashlib.sha256(before).hexdigest() == KLOG_SHA, 'kernel changed: review required')
    proc = Path('/proc') / str(PID)
    pidfd = os.pidfd_open(PID, 0)
    need(int((proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]) == TICKS, 'PID reused')
    need(not (proc / 'task' / str(PID) / 'children').read_text().strip(), 'manager has child')
    need('libxrt' not in (proc / 'maps').read_text().lower() and '/dev/' not in (proc / 'maps').read_text(), 'native/device mapping')
    expected = [str(ROOT/'lifecycle.jsonl'), '/var/lock/kv260-a1/deployment.lock', '/run/lock/patient-qwen-linear.lock']
    actual = {q.name: os.readlink(q) for q in (proc / 'fd').iterdir()}
    need(actual == {**{str(n): '/dev/pts/0' for n in range(3)}, **{str(n+3): p for n,p in enumerate(expected)}}, 'unexpected manager fd')
    need(all(lock_owned(path, PID) for path in LOCKS), 'lock owner changed')
    status = dict(line.split(':', 1) for line in (proc / 'status').read_text().splitlines())
    bit = 1 << (signal.SIGUSR1 - 1)
    need(all(not (int(status[key].strip(), 16) & bit) for key in ('SigBlk','SigIgn','SigCgt')), 'termination signal not default')
    need(status['State'].strip().startswith('S') and status['Threads'].strip() == '1', 'not sleeping single-thread waiter')
    receipt_path = ROOT / 'prepl-cleanup.json'
    with receipt_path.open('x', encoding='utf-8') as stream:
        result = dict(status='RESERVED_USER_AUTHORIZED_PREPL_CLEANUP', boot_id=BOOT, pid=PID,
                      pid_start_ticks=TICKS, pl_loads=0, compute_runs=0, signal='SIGUSR1', signal_sent=False)
        json.dump(result, stream); stream.flush(); os.fsync(stream.fileno())
        held = []
        try:
            signal.pidfd_send_signal(pidfd, signal.SIGUSR1, None, 0)
            result['signal_sent'] = True
            need(bool(select.select([pidfd], [], [], 3)[0]), 'waiter exit unconfirmed: no second signal')
            result['pidfd_exit_confirmed'] = True
            for path in LOCKS:
                fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
                held.append(fd)
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            hardware_absent()
            need(log_bytes() == before, 'new kernel message before graphical restore')
            service = subprocess.Popen(['systemctl','start','gdm.service'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                out, err = service.communicate(timeout=15)
            except subprocess.TimeoutExpired:
                raise RuntimeError('graphical restore pending; no kill or retry')
            result['gdm_start'] = dict(exit_code=service.returncode, stdout=out.decode(), stderr=err.decode())
            need(service.returncode == 0, 'graphical restore failed')
            p = subprocess.run(['systemctl','is-active','gdm.service'], capture_output=True, timeout=3)
            need(p.returncode == 0 and p.stdout.strip() == b'active', 'graphical restore unproven')
            after = log_bytes()
            from kernel_log_gate import diagnostics
            need(after.startswith(before) and not diagnostics(after[len(before):].decode()), 'new kernel diagnostics after restore')
            result['temperatures_mC'] = hardware_absent()
            need(digest(active/'lease.json') == LEASE_SHA, 'lease changed before archival')
            active.rename(archive)
            result.update(status='PREPL_ABORT_CLEANUP_COMPLETE_DEFAULT_PL_UNTOUCHED', lease_archive=str(archive),
                          gdm_state='active', kernel_sha256=hashlib.sha256(after).hexdigest(),
                          normal_kernel_restore=False, A10='NOT_PASSED_IDLE_NOT_REACHED')
        except BaseException as exc:
            result.update(status='CLEANUP_STOPPED_NO_AUTOMATIC_RETRY', error=type(exc).__name__+': '+str(exc))
        finally:
            stream.seek(0); json.dump(result, stream, indent=2); stream.truncate(); stream.flush(); os.fsync(stream.fileno())
            for fd in reversed(held):
                os.close(fd)
            os.close(pidfd)
    print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'PREPL_ABORT_CLEANUP_COMPLETE_DEFAULT_PL_UNTOUCHED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
