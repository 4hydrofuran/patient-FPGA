"""One new reviewed full-model compute window. No retries, forced exits or scope growth."""
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import sys
import threading
import time
BUNDLE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUNDLE / 'platform/qwen35/a12'))
sys.path.insert(0, str(BUNDLE / 'control/support'))
import cpu01b_observer as ob
from cpu02_support import CACHE
from cpu01_profile import audit_profile
from cpu01_numeric import compare_cases
from cpu01_usage import process_usage
from common import sha, save
from cpu01b_window import Window
from cpu01b_healthrecord import compact_kernel_record
from cpu01b_health import PersistentKmsg, StableTemperatures, HealthSchedule, HealthBlocked
from capacity_policy import admission, review_archive_cache
from cpu01b_supervisor import OwnedWorker as CPUWorker
from mlp_base import IsolatedIdleTrial, check_topology
from cpu01b_kernel_gate import MinimalGate
from isolated_idle_policy import BOOT_FILES, LIBRARIES, MACHINE, DEFAULT, trusted_file
from idle_board_trial import RESTORE, active_handle, check_loaded, check_removed
from accelerator_release_gate_v2 import require_release
from resource_probe_case import execute_case
sys.path.insert(0,str(BUNDLE/'application'))
from tt10_00_app import measure as measure_application
os.environ['SP_TT10_CONFIG']=str(BUNDLE/'control/prefix-config.json')

SPEC = json.loads((BUNDLE / 'control/window-spec.json').read_text())
WINDOW = SPEC['window_id']

class Platform(IsolatedIdleTrial):

    def __init__(self, run, boot):
        self.source = BUNDLE / 'hardware'
        self.boot = boot
        self.package = WINDOW
        self.target = Path('/lib/firmware/xilinx') / WINDOW
        self.driver = self.source / 'zocl.refcount.ko'
        self.driver_sha256 = '388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c'
        self.run = run
        self.log = (run / 'lifecycle.jsonl').open('x')
        self.kernel_gate = MinimalGate()
        self.worker = None
        self.release_checked = False
        self.gdm_isolated = False
        self.pl_mutation_started = False
        self.owner = None
        self.gate_lock = threading.RLock()
        self.health_schedule = HealthSchedule(self.gate_lock)
        self.kmsg_reader = None
        self.stable_temperatures = None
        self.topology_checked_ns = 0
        self.health_parts = dict(kernel_ms=0.0, temperature_memory_ms=0.0, kernel_calls=0)

    def emit(self, event, **data):
        if event == 'KERNEL_LOG_GATE':
            data = compact_kernel_record(self.run, data)
            self.latest_kernel = dict(allowed=data['allowed'], sha256=data['current_sha256'], observation_monotonic_ns=time.monotonic_ns())
        if event == 'LIVE_HEALTH':
            self.latest_health = dict(data, checked_monotonic_ns=time.monotonic_ns())
        if SPEC['compact_health_journal'] and event in ('KERNEL_LOG_GATE', 'LIVE_HEALTH'):
            key = event
            now = time.monotonic_ns()
            last = getattr(self, 'journal_last', {}).get(key)
            fingerprint = self.latest_kernel['sha256'] if event == 'KERNEL_LOG_GATE' else None
            if last and now - last[0] < 1000000000 and (fingerprint == last[1]) and (event != 'KERNEL_LOG_GATE' or data['allowed'] is True):
                return
            if not hasattr(self, 'journal_last'):
                self.journal_last = {}
            self.journal_last[key] = (now, fingerprint)
        return super().emit(event, **data)

    def kernel_checkpoint(self, phase, mutation=None):
        with ob.span('health.kernel_total'):
            if phase != 'a12_serialized_health':
                super().kernel_checkpoint(phase, mutation)
                if self.kmsg_reader is not None:
                    self.kmsg_reader.assert_full_snapshot(self.kernel_gate.previous)
                return
            start = time.monotonic_ns()
            try:
                if self.kmsg_reader is None:
                    self.kmsg_reader = PersistentKmsg()
                    super().kernel_checkpoint(phase, mutation)
                    self.kmsg_reader.assert_full_snapshot(self.kernel_gate.previous)
                else:
                    with ob.span('health.kmsg_drain'):
                        raw = self.kmsg_reader.drain()
                    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                    with ob.span('health.kernel_gate'):
                        result = self.kernel_gate.observe_action(boot, raw, None, 'none', False)
                    with ob.span('health.kernel_emit'):
                        self.emit('KERNEL_LOG_GATE', phase=phase, raw_log=raw, **dict(result, action='none'))
                    if not result['allowed']:
                        raise HealthBlocked('incremental kernel gate rejected')
            except BaseException:
                self.kernel_gate.blocked = True
                raise
            finally:
                self.health_parts['kernel_ms'] += (time.monotonic_ns() - start) / 1000000.0
                self.health_parts['kernel_calls'] += 1

    def live_health(self, boot, full_resident):
        with ob.span('health.live_total'):
            start = time.monotonic_ns()
            assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
            if self.stable_temperatures is None:
                self.stable_temperatures = StableTemperatures()
            now = time.monotonic_ns()
            with ob.span('health.temperature_topology'):
                if now - self.topology_checked_ns >= 1000000000:
                    self.stable_temperatures.verify_topology()
                    self.topology_checked_ns = now
            with ob.span('health.temperatures'):
                temps = self.stable_temperatures.read()
            with ob.span('health.meminfo'):
                mem = {l.split(':')[0]: int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines()}
            if mem['MemAvailable'] < 1114112 or mem['CmaFree'] < 98304:
                raise HealthBlocked('full-model live extra reserve gate')
            with ob.span('health.reserve'):
                result = dict(temperatures_mC=temps, memory_kib={k: mem[k] for k in ('MemAvailable', 'CmaFree', 'CmaTotal')}, full_resident=full_resident, actual_reserve=admission(mem, 140591104, already_charged_bo_bytes=140591104) if full_resident else None)
            self.health_parts['temperature_memory_ms'] += (time.monotonic_ns() - start) / 1000000.0
            return result

    def guard(self, identity=None):
        if self.owner:
            self.owner.owner_check()
        if self.gdm_isolated:
            r = subprocess.run(['systemctl', 'is-active', 'gdm.service'], capture_output=True, timeout=3)
            assert r.stdout.strip() == b'inactive', 'GDM isolation lost'
        self.snapshot('identity_health_guard')
        return True

    def remove(self, package):
        if package == self.package:
            assert self.release_checked and self.worker.closed and (self.worker.process.returncode == 0)
            self.release_checked = False
        else:
            assert package == DEFAULT and self.worker is None
        handle = active_handle(self.command(['dfx-mgr-client', '-listPackage']), package)
        self.command(['dfx-mgr-client', '-remove', handle], True)

class Owner(Window):

    def __init__(self, platform, review, evidence):
        self.platform = platform
        super().__init__(review, evidence=evidence)
        platform.owner = self

    def health(self, *, closing=False):
        return self.platform.health_schedule.fresh(lambda: self._health_observation(closing=closing))

    def _health_observation(self, *, closing=False):
        with ob.span('health.observation_total'):
            with ob.lock_context(self.platform.gate_lock, '_health_observation.lock_wait'):
                assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.boot
                self.platform.kernel_checkpoint('a12_serialized_health')
                if not closing:
                    self.platform.emit('LIVE_HEALTH', **self.platform.live_health(self.boot, getattr(self, 'full_resident', False)))
                return dict(kernel=self.platform.latest_kernel, live_health=None if closing else self.platform.latest_health, closing=closing, checked_monotonic_ns=time.monotonic_ns(), checks_skipped=False, journal_compacted=SPEC['compact_health_journal'])

def receive(worker, owner, run, timeout=None):
    timeout = SPEC['receive_seconds'] if timeout is None else timeout
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with ob.scope('idle'):
            owner.platform.health_schedule.idle(owner._health_observation, owner.owner_check)
        try:
            r = worker.messages.get(timeout=0.25)
        except queue.Empty:
            continue
        assert r is not None, 'unexpected worker EOF'
        return r
    worker.cancel('bounded_model_deadline')
    raise RuntimeError('deadline: delivery cancelled, no kill or resource release')

def validate_bo(route):
    assert route['owned_bo_charged_bytes'] == 140591104 and route['weight_load_count'] == 72
    assert route['a11_explicit_bo_allocations_host_counter'] == 148 and route['a11_argument_groups'] == [3] * 6
    spans = list(zip(route['a11_io_bo_addresses'], route['a11_io_bo_charged_sizes']))
    assert len(route['a11_live_weights']) == 72
    for w in route['a11_live_weights']:
        spans.extend(zip(w['addresses'], w['charged_sizes']))
    assert len(spans) == 148 and sum((n for a, n in spans)) == 140591104
    for i, (a, n) in enumerate(spans):
        assert 0 <= a and a + n <= 2147483648 and (n % 8192 == 0)
        assert all((a + n <= b or b + m <= a for b, m in spans[:i]))
    return spans
'Inserted into reviewed manager: bounded state/cancel cases, never force-close.'
'Inserted into reviewed manager: bounded state/cancel cases, never force-close.'
'Bounded normal/profile measurements; client clocks include ordinary IPC and completion.'

def run_case(worker, owner, path, *, real):
    return execute_case(worker, owner, path, real=real, api=globals())

def main():
    raise PermissionError('UNBOUND probe: future recovery, safe release, fresh binding and separate authorized driver required')
    assert os.geteuid() == 0 and os.uname().machine == 'aarch64' and (os.uname().release == '6.8.12-a10irq2')
    assert sha('/etc/machine-id') == MACHINE
    os.umask(63)
    run = BUNDLE / 'run-v1'
    run.mkdir(mode=448)
    pins = json.loads((BUNDLE / 'manifest.json').read_text())
    for row in pins['files']:
        p = BUNDLE / row['path']
        trusted_file(p)
        assert p.stat().st_size == row['bytes'] and sha(p) == row['sha256']
    assets = json.loads((BUNDLE / 'control/asset-pins.json').read_text())
    for name, pin in assets.items():
        assert sha('/opt/patient-qwen/' + name) == pin
    for name, pin in {**BOOT_FILES, **LIBRARIES}.items():
        assert sha(name) == pin
    for name, pin in RESTORE.items():
        assert sha(Path('/lib/firmware/xilinx') / DEFAULT / name) == pin
    assert Path('/etc/dfx-mgrd/default_firmware').read_text().strip() == DEFAULT
    assert not Path('/state.txt').exists() and (not Path('/sys/module/zocl').exists())
    assert not Path('/var/lock/kv260-a1/active').exists()
    assert not os.path.lexists(Path('/lib/firmware/xilinx') / WINDOW)
    for name in ('a11-mlp.bit.bin', 'a11-mlp.dtbo'):
        assert not os.path.lexists('/lib/firmware/' + name)
    for k in list(os.environ):
        if k.startswith(('SP_A12', 'LD_', 'GGML_', 'OMP_')):
            os.environ.pop(k)
    os.environ.update(LD_LIBRARY_PATH=str(BUNDLE / 'bin'), OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='1')
    os.chmod(BUNDLE / 'bin/qwen35-a12', 448)
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    prior = json.loads((BUNDLE / 'control/preflight.json').read_text())
    assert boot == prior['boot_id']
    p = Platform(run, boot)
    raw = subprocess.check_output(['dmesg', '--raw'])
    stamp = time.monotonic_ns()
    assert raw.decode() == prior['kernel_raw'], 'kernel changed after reviewed preflight'
    (run / 'baseline.raw.txt').write_bytes(raw)
    assert p.kernel_gate.observe_action(boot, raw.decode(), sha(run / 'baseline.raw.txt'), 'none')['allowed']
    initial = p.snapshot('initial')
    assert initial['overlays'] == {DEFAULT + '_image_1': 'applied'} and initial['module_refcount'] is None
    assert not initial['zocl_bound'] and (not initial['render_nodes']) and (not initial['device_holders'])
    assert initial['memory_kib']['CmaFree'] >= 32768
    assert initial['memory_kib']['MemAvailable'] >= 1048576
    review = dict(schema='A12_FRESH_WINDOW_V1', authorized_compute=True, machine_sha256=MACHINE, boot_id=boot, window_id=WINDOW, scope='all', max_runs=SPEC['max_runs'], max_loads=72, explicit_bo_budget_bytes=140591104, compact_completion=SPEC['compact_completion'], compact_health_journal=SPEC['compact_health_journal'], operation='BOUNDED_FULL_MODEL_' + SPEC['variant'], max_session_seconds=SPEC['max_session_seconds'], bundle_sha256=sha(BUNDLE / 'manifest.json'), kernel_baseline_file=str(run / 'baseline.raw.txt'), kernel_baseline_sha256=sha(run / 'baseline.raw.txt'), baseline_read_monotonic_ns=stamp)
    save(run / 'review.json', review)
    s2 = run / 's2'
    s2.mkdir()
    owner = None
    try:
        owner = Owner(p, review, s2)
        p.service('stop')
        p.no_users(module_loaded=False)
        pending = p.snapshot('before_full_BO_allocation')
        capacity = admission(pending['memory_kib'], 140591104)
        save(run / 'pre-allocation-admission.json', capacity)
        if not capacity['allowed']:
            raise RuntimeError('unchanged full BO capacity admission failed; owner retained')
        p.wait_prepl_quiet()
        p.target.mkdir(mode=493)
        for name in ('a11-mlp.bit.bin', 'a11-mlp.dtbo', 'shell.json'):
            with (p.source / name).open('rb') as src, (p.target / name).open('xb') as dst:
                shutil.copyfileobj(src, dst)
            assert sha(p.target / name) == sha(p.source / name)
        p.remove(DEFAULT)
        check_removed(p.snapshot('default_removed'), False)
        p.command(['insmod', str(p.driver)], True)
        check_removed(p.snapshot('driver_unbound'), True)
        assert Path('/sys/module/zocl/srcversion').read_text().strip() == '15F2AC2306CB3CB7257CFCB'
        p.command(['dfx-mgr-client', '-load', WINDOW], True)
        check_loaded(p.snapshot('test_loaded'), WINDOW)
        p.no_users(module_loaded=True)
        launch = time.monotonic_ns()
        pl = owner.start_worker(BUNDLE)
        pl.task10_launch_ns = launch
        p.worker = pl
        save(s2 / 'identity.json', dict(pid=pl.process.pid, argv=pl.process.args, binary_sha256=sha(BUNDLE / 'bin/qwen35-a12'), physical_domain='BOARD'))
        result = run_case(pl, owner, s2, real=True)
        check_topology(p.snapshot('worker_exited'), WINDOW)
        scan, refs, allowed = p.observation()
        require_release(scan, refs, allowed, boot_id=boot)
        save(run / 'release-precheck.json', dict(scan=scan, refcount=refs, kernel_allowed=allowed))
        p.release_checked = True
        p.remove(WINDOW)
        check_removed(p.snapshot('test_removed'), True)
        p.no_users(module_loaded=True)
        p.command(['rmmod', 'zocl'], True)
        check_removed(p.snapshot('driver_removed'), False)
        p.command(['dfx-mgr-client', '-load', DEFAULT], True)
        final = p.snapshot('default_restored')
        assert final['overlays'] == initial['overlays'] and final['vart_sha256'] == initial['vart_sha256']
        p.service('start')
        p.snapshot('gdm_restored')
        owner.finish(pl)
        p.stable_temperatures.verify_topology()
        p.kmsg_reader.close()
        save(run / 'result.json', dict(status='FULL_MODEL_' + SPEC['variant'] + '_NORMAL_RESTORE_PENDING_AUDIT', physical_domain='BOARD', worker_exit_code=0, permission_submissions=pl.runs, backend_host_verified_completions=result['bridge']['a12_route']['host_verified_completions'], hardware_global_count=None, scope='all', lease_archived=True, variant=SPEC['variant'], request_count=SPEC['request_limit'], step10='IN_PROGRESS_' + SPEC['variant'] + '_PENDING_AUDIT', board_speedup=None))
    except BaseException as exc:
        reason = type(exc).__name__ + ': ' + str(exc)
        if owner:
            owner.retain_until_finished(reason)
        raise
    print(json.dumps(dict(status='FULL_MODEL_WINDOW_NORMAL_EXIT', scope='all', variant=SPEC['variant'])), flush=True)
if __name__ == '__main__':
    raise SystemExit('UNBOUND_RESOURCE_PROBE_NO_COMPUTE_AUTHORIZATION')
