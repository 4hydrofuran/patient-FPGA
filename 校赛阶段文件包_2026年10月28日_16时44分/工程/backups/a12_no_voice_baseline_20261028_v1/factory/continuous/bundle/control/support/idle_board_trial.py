"""One authorized idle PL cycle. No XRT device opens, compute or BO API calls.

Default is help, not execution. Any failed readback stops; no automatic repair.
An uncertain management call parks with its locks, never kills its child.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
from kernel_log_gate import KernelLogGate, KernelLogBlocked

BOOT = 'd07af077-84c9-4910-8529-95757a09106d'
MACHINE = 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
PACKAGE = 'a10-vadd-20261019'
DEFAULT = 'k26-starter-kits'
TARGET = Path('/lib/firmware/xilinx') / PACKAGE
CENTRAL = Path('/var/lock/kv260-a1')
DRIVER = Path('/home/ubuntu/a10-driver-check-20261018-v2/zocl.ko')
HASHES = {'a1-vadd.bit.bin': '772b26d0756e43e71cc1cf05b0f0de9e51b6f25507d427eff5c2f82d3c790c23',
          'a1-vadd.dtbo': '14a014624b084f8c9f39fd13e15e156360f9eae367b7da7994328fee432e4646'}
RESTORE = {'k26_starter_kits.bit.bin': 'f9dfe95d14881a2768b2c0e6a36fc363635e8ae7882ecad9725d270490395d3e',
           'k26_starter_kits.dtbo': '1e998ffd5d33a05da3746df3603e65603e1628006bc878209a836cc9bd3c4ae1'}


def need(value, reason):
    if not value:
        raise RuntimeError(reason)


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def active_handle(text, package):
    rows = [line.split() for line in text.splitlines() if line.split() and line.split()[0] == package]
    need(len(rows) == 1, 'missing/ambiguous package row')
    pairs = re.findall(r'(\d+)->(\d+)', ' '.join(rows[0]))
    need(len(pairs) == 1 and pairs[0][0] == '0', 'unknown active handle')
    return pairs[0][1]


def check_removed(s, module_loaded):
    need(s['overlays'] == {} and s['zocl_bound'] == [] and s['render_nodes'] == [] and
         s['device_holders'] == [] and not s.get('accelerator_card_nodes'), 'removal readback not clean')
    need((type(s['module_refcount']) is int and s['module_refcount'] == 0) if module_loaded
         else s['module_refcount'] is None, 'module state/refcount')


def accelerator_fd(target, cards):
    return (target.startswith(('/dev/dri/renderD', '/dev/zocl', '/dev/uio', '/dev/vfio/')) or
            target.removesuffix(' (deleted)') in cards)


def check_loaded(s, package=PACKAGE):
    need(len(s['overlays']) == 1 and all(k.startswith(package + '_image_') and v == 'applied'
         for k, v in s['overlays'].items()), 'test overlay not applied')
    detail = s.get('zocl_binding_details', [])
    main = [d for d in detail if d['driver'] == 'zocl-drm' and d['name'] == 'axi:zyxclmm_drm']
    child = [d for d in detail if d['driver'] == 'zocl_irq_intc' and
             re.fullmatch(r'ZOCL_CU_INTC\.\d+\.auto', d['name'])]
    need(len(detail) == 2 and len(main) == len(child) == 1 and
         Path(child[0]['path']).parent == Path(main[0]['path']) and
         sorted(d['name'] for d in detail) == s['zocl_bound'], 'unexpected ZOCL binding topology')
    need(len(s['render_nodes']) == 1 and s['device_holders'] == [], 'binding/node/holder mismatch')
    need(s['fpga_state'] == 'operating', 'FPGA manager not operating')


class Trial:
    # Defaults retain the historical trial/cleanup identity. A derived candidate
    # entry must supply its own exact identity; no process-global substitutions.
    boot = BOOT
    kernel_release = '6.8.0-1015-xilinx'
    package = PACKAGE
    target = TARGET
    driver = DRIVER
    driver_sha256 = '545df42c8b66396dd847ccd6a280f19d9a0051d36e2e75c1ec84437caca328a9'
    temperature_limit_mC = 60000
    memory_reserve_KiB = 262144
    history_name = 'a10-idle-20261019.json'
    authorization_label = 'USER_ALLOW_SINGLE_IDLE_CONFIGURATION_20261019'
    reviewed_baseline_sha256 = None

    def __init__(self, source):
        self.source = source
        self.log = (source / 'idle-result.jsonl').open('x', encoding='utf-8')

    def emit(self, event, **data):
        row = dict(event=event, monotonic_s=time.monotonic(), **data)
        text = json.dumps(row)
        self.log.write(text + '\n'); self.log.flush(); os.fsync(self.log.fileno())
        print(text, flush=True)

    def command(self, argv, state_changing=False):
        if state_changing:
            self.kernel_checkpoint('before_mutation', argv)
        self.emit('COMMAND_BEGIN', argv=argv, state_changing=state_changing)
        p = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = p.communicate(timeout=8)
        except subprocess.TimeoutExpired:
            self.emit('UNKNOWN_COMMAND_STATE_PARKED_NO_KILL', argv=argv, pid=p.pid)
            while True:
                time.sleep(30)  # no retry/kill/release: operator reconciliation required
        self.emit('COMMAND_END', argv=argv, exit_code=p.returncode, stdout=out, stderr=err)
        if state_changing:
            self.kernel_checkpoint('after_mutation', argv)
        need(p.returncode == 0, 'command failed: ' + repr(argv))
        return out

    def kernel_checkpoint(self, phase, mutation):
        # Separate bounded read-only subprocess. Never consume/clear the ring or
        # invoke the mutation runner recursively. No baseline waiver by default.
        if not hasattr(self, 'kernel_gate'):
            self.kernel_gate = KernelLogGate()
        try:
            # The board's dmesg rejects --raw with any --color argument. Raw mode
            # already bypasses color formatting and retains syslog priorities.
            p = subprocess.run(['dmesg', '--raw'], capture_output=True,
                               timeout=3, check=False)
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            if p.returncode != 0 or p.stderr or boot != self.boot:
                raise KernelLogBlocked('kernel log read failed or boot changed')
            # Firmware messages contain literal CR bytes. text=True silently
            # rewrites CRLF/CR and breaks the independently hashed raw baseline.
            # Decode explicitly: retain every byte, never normalize the review.
            raw = p.stdout.decode('utf-8', errors='strict')
            result = self.kernel_gate.observe(boot, raw, self.reviewed_baseline_sha256)
            self.emit('KERNEL_LOG_GATE', phase=phase, mutation=mutation,
                      log_exit_code=p.returncode, boot_id=boot, raw_log=raw, **result)
            if not result['allowed']:
                raise KernelLogBlocked(result['reason'])
        except Exception as exc:
            self.kernel_gate.blocked = True
            self.emit('KERNEL_LOG_BLOCKED_NO_NEXT_MUTATION', phase=phase,
                      mutation=mutation, error=str(exc))
            raise

    def snapshot(self, phase):
        need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot, 'boot changed')
        need(digest('/etc/machine-id') == MACHINE, 'machine changed')
        temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
        need(temps and all(0 < t < self.temperature_limit_mC for t in temps), 'temperature gate')
        mem = {l.split(':')[0]: int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
        need(mem['MemAvailable'] >= self.memory_reserve_KiB and mem['CmaFree'] >= 32768, 'memory reserve')
        overlays = {p.name: (p / 'status').read_text().strip()
                    for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()}
        bound = [p.name for p in Path('/sys/bus/platform/devices').iterdir()
                 if (p / 'driver/module').exists() and (p / 'driver/module').resolve().name == 'zocl']
        details = [dict(name=name, driver=(Path('/sys/bus/platform/devices') / name / 'driver').resolve().name,
                        path=str((Path('/sys/bus/platform/devices') / name).resolve())) for name in sorted(bound)]
        nodes = sorted(str(p) for p in Path('/dev/dri').glob('renderD*'))
        cards = sorted('/dev/dri/' + p.name for p in Path('/sys/class/drm').glob('card[0-9]*')
                       if p.name[4:].isdigit() and (p / 'device/driver/module').exists() and
                       (p / 'device/driver/module').resolve().name == 'zocl')
        # Read only symlink targets, never open device nodes or alter process state.
        holders = []
        for proc in Path('/proc').iterdir():
            if not proc.name.isdigit():
                continue
            try:
                for fd in (proc / 'fd').iterdir():
                    try:
                        target = os.readlink(fd)
                        if accelerator_fd(target, cards):
                            holders.append(dict(pid=int(proc.name), fd=fd.name, target=target))
                    except FileNotFoundError:
                        pass
            except FileNotFoundError:
                pass
        ref = Path('/sys/module/zocl/refcnt')
        s = dict(phase=phase, boot_id=self.boot, temperatures_mC=temps,
                 memory_kib={k: mem[k] for k in ('MemTotal', 'MemAvailable', 'CmaTotal', 'CmaFree')},
                 overlays=overlays, zocl_bound=sorted(bound), render_nodes=nodes, device_holders=holders,
                 accelerator_card_nodes=cards,
                 zocl_binding_details=details,
                 module_refcount=int(ref.read_text()) if ref.exists() else None,
                 fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
                 vart_sha256=digest('/etc/vart.conf') if Path('/etc/vart.conf').exists() else None)
        self.emit('READBACK', **s)
        return s

    def run(self):
        import fcntl
        need(os.geteuid() == 0 and os.uname().machine == 'aarch64', 'root ARM64 required')
        need(os.uname().release == self.kernel_release, 'kernel changed')
        need(not CENTRAL.is_symlink() and not os.path.lexists(self.target), 'existing target/symlink')
        for name, sha in HASHES.items():
            need(digest(self.source / name) == sha, 'test artifact changed')
            need(not os.path.lexists('/lib/firmware/' + name), 'firmware copy would overwrite')
        need(not self.driver.is_symlink() and digest(self.driver) == self.driver_sha256, 'driver changed')
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore changed')
        need(Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT, 'default changed')
        need(not Path('/state.txt').exists(), 'existing libdfx temporary file')
        shell = json.loads((self.source / 'shell.json').read_text())
        need(shell == dict(shell_type='XRT_FLAT', num_pl_slots=1, num_aie_slots=0), 'shell differs')
        initial = self.snapshot('initial')
        need(initial['overlays'] == {DEFAULT + '_image_1': 'applied'} and initial['module_refcount'] is None
             and not initial['zocl_bound'] and not initial['render_nodes'] and not initial['device_holders'], 'initial state differs')
        self.command(['dmesg', '--color=never'])
        listing = self.command(['dfx-mgr-client', '-listPackage'])
        handle = active_handle(listing, DEFAULT)
        CENTRAL.mkdir(mode=0o755, exist_ok=True)
        need(CENTRAL.stat().st_uid == 0 and not (CENTRAL.stat().st_mode & 0o022), 'untrusted central directory')
        self.deploy_lock = (CENTRAL / 'deployment.lock').open('a+')
        fcntl.flock(self.deploy_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.shared_lock = Path('/run/lock/patient-qwen-linear.lock').open('a+')
        fcntl.flock(self.shared_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        active = CENTRAL / 'active'
        active.mkdir()
        lease = dict(owner='A', scope='A10_IDLE_PL_ONCE', identity=MACHINE + ':' + self.boot,
                     issued_unix=time.time(), expires_unix=time.time() + 600, pid=os.getpid(),
                     compute_authorized=False, authorization=self.authorization_label)
        with (active / 'lease.json').open('x') as f:
            json.dump(lease, f)
        self.emit('LEASE_ACQUIRED', scope=lease['scope'])
        self.target.mkdir(mode=0o755)
        for name in (*HASHES, 'shell.json'):
            with (self.source / name).open('rb') as src, (self.target / name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
            need(digest(self.source / name) == digest(self.target / name), 'staging mismatch')
        self.emit('STAGED_NO_XCLBIN_NO_COMPUTE_PROGRAM', target=str(self.target))
        self.snapshot('before_remove_default')
        self.command(['dfx-mgr-client', '-remove', handle], True)
        check_removed(self.snapshot('default_removed'), False)
        self.command(['insmod', str(self.driver)], True)
        check_removed(self.snapshot('driver_unbound'), True)
        self.command(['dfx-mgr-client', '-load', self.package], True)
        loaded = self.snapshot('test_loaded_idle')
        check_loaded(loaded, self.package)
        need(loaded['vart_sha256'] == initial['vart_sha256'], 'vart changed')
        listing = self.command(['dfx-mgr-client', '-listPackage'])
        handle = active_handle(listing, self.package)
        self.command(['dmesg', '--color=never'])
        self.emit('WAIT_OPERATOR_KERNEL_LOG_REVIEW_NO_COMPUTE')
        need(input('Type CONTINUE_UNLOAD after reviewing the new kernel messages: ').strip() ==
             'CONTINUE_UNLOAD', 'operator did not authorize normal unload continuation')
        self.snapshot('before_test_unload')
        self.command(['dfx-mgr-client', '-remove', handle], True)
        check_removed(self.snapshot('test_removed'), True)
        self.command(['rmmod', 'zocl'], True)
        check_removed(self.snapshot('driver_removed'), False)
        self.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = self.snapshot('default_restored')
        need(final['overlays'] == initial['overlays'] and final['module_refcount'] is None and
             not final['zocl_bound'] and not final['render_nodes'] and not final['device_holders'] and
             final['fpga_state'] == 'operating' and final['vart_sha256'] == initial['vart_sha256'], 'restore readback mismatch')
        active_handle(self.command(['dfx-mgr-client', '-listPackage']), DEFAULT)
        for name, sha in RESTORE.items():
            need(digest(Path('/lib/firmware/xilinx') / DEFAULT / name) == sha, 'restore source changed')
        self.command(['dmesg', '--color=never'])
        history = CENTRAL / 'history'
        history.mkdir(exist_ok=True)
        dest = history / self.history_name
        need(not dest.exists(), 'history exists')
        (active / 'lease.json').rename(dest)
        active.rmdir()
        self.emit('IDLE_CYCLE_COMPLETE', compute_runs=0, compute_BO_allocations=0,
                  A10='NOT_PASSED_COMPUTE_AND_RECOVERY_GATES_REMAIN', package_retained=str(self.target))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-authorized-idle-once', action='store_true')
    a = ap.parse_args()
    need(a.execute_authorized_idle_once, 'explicit once-only switch required')
    trial = Trial(Path(__file__).resolve().parent)
    try:
        trial.run()
    except Exception as exc:
        trial.emit('STOP_NO_AUTOMATIC_RECOVERY', error=str(exc), error_type=type(exc).__name__)
        raise
