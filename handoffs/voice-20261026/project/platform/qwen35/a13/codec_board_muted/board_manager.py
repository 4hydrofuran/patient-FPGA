"""One explicitly requested, zero-only and physically muted maintenance window.

No reboot, signal, forced unload, recording, audible test, global module install
or boot changes. Any unknown hardware/child state retains actual ownership.
ARTIFACTS, REQUEST and the strict scanner are hash-bound by the local preparer.
"""
import base64
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time

from accelerator_release_gate_v2 import collect, require_no_users
from kernel_log_gate import KernelLogGate, diagnostics

MACHINE = 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
BOOT = '415c0647-4061-40c2-bf13-36d5c55ba80c'
BASELINE = '07bdb3b2a7e49a59f848b9c78b728956a06d21989eedd9f2c54c200c3741542f'
OUT = Path('/var/lib/kv260-a13/audio-muted-20261025-v1')
FW = Path('/lib/firmware/xilinx/a13-muted-20261025-v1')
CENTRAL = Path('/var/lock/kv260-a1')
OVERLAYS = Path('/sys/kernel/config/device-tree/overlays')
DEFAULT = OVERLAYS / 'k26-starter-kits_image_1'
MUTED = OVERLAYS / 'a13-muted-20261025-v1'
DEFAULT_FILES = {
 '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.bit.bin': 'f9dfe95d14881a2768b2c0e6a36fc363635e8ae7882ecad9725d270490395d3e',
 '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.dtbo': '1e998ffd5d33a05da3746df3603e65603e1628006bc878209a836cc9bd3c4ae1',
 '/boot/firmware/image.fit': '23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
 '/boot/firmware/boot.scr.uimg': 'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
 '/boot/firmware/a10-candidate-irq2-20261021.fit': 'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'}
CHILDREN = []
FDS = []
LEASE_SHA = None


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1048576), b''): h.update(chunk)
    return h.hexdigest()


def trusted(path, directory=False):
    info = Path(path).lstat()
    assert info.st_uid == 0 and not info.st_mode & 0o022 and not stat.S_ISLNK(info.st_mode), str(path)
    assert stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    return info


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def event(kind, **fields):
    row = dict(event=kind, monotonic_ns=time.monotonic_ns(), **fields)
    with (OUT / 'events.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(row) + '\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(row), flush=True)


def identity():
    assert os.geteuid() == 0 and os.uname().machine == 'aarch64'
    assert os.uname().release == '6.8.12-a10irq2'
    assert sha('/etc/machine-id') == MACHINE
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT


def lease():
    identity()
    assert sha(CENTRAL / 'active/lease.json') == LEASE_SHA
    for fd in FDS:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def command(label, argv, deadline=15):
    lease()
    save(label + '-reserved.json', {'argv': argv, 'no_signal_or_retry': True})
    with (OUT / (label + '.stdout')).open('xb') as stdout, (OUT / (label + '.stderr')).open('xb') as stderr:
        p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        CHILDREN.append(p)
        try:
            code = p.wait(timeout=deadline)
        except subprocess.TimeoutExpired:
            event('CHILD_STILL_RUNNING_RETAIN_OWNER', label=label, pid=p.pid)
            raise RuntimeError('Deadline without automatic child termination')
    save(label + '-result.json', {'exit_code': code, 'pid': p.pid, 'argv': argv})
    assert code == 0, label + ' failed; no retry'


def kernel_raw():
    # Read-only bounded dmesg is not a hardware worker or power command.
    p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=5)
    assert p.returncode == 0
    return p.stdout


def kernel_transition(label, previous):
    raw = kernel_raw()
    with (OUT / (label + '.kernel.raw')).open('xb') as stream: stream.write(raw)
    assert raw.startswith(previous), 'Kernel continuity lost'
    new = raw[len(previous):].decode('utf-8')
    found = diagnostics(new)
    symbols = {'a13muted_mclk', 'a13muted_sound', 'a13muted_afi', 'a13muted_bus',
               'a13muted_serial', 'a13muted_dma', 'a13muted_iic', 'a13muted_codec'}
    permitted = {'/fpga-region/firmware-name', '/fpga-region/resets'} | {'/__symbols__/' + s for s in symbols}
    unexpected = []
    for row in found:
        message = re.sub(r'^<\d+>\[\s*[0-9.]+\]\s*', '', row['text'])
        prefix = 'OF: overlay: WARNING: memory leak will occur if overlay removed, property: '
        expected_overlay = message.startswith(prefix) and message[len(prefix):] in permitted
        expected_module = message == 'a13_muted_dma: loading out-of-tree module taints kernel.' or message in {
            name + ': module verification failed: signature and/or required key missing - tainting kernel'
            for name in ('a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card')}
        if not (expected_overlay or expected_module): unexpected.append(row)
    generic = KernelLogGate()
    assert generic.observe(BOOT, previous.decode('utf-8'), hashlib.sha256(previous).hexdigest())['allowed']
    strict_result = generic.observe(BOOT, raw.decode('utf-8'))
    save(label + '-kernel-review.json', {'strict_unmodified_gate': strict_result,
        'all_new_diagnostics': found, 'unexpected': unexpected,
        'scope': 'EXACT_KNOWN_MODULE_AND_OVERLAY_TRANSITION_ONLY_NO_FAULT_EXEMPTIONS',
        'raw_sha256': hashlib.sha256(raw).hexdigest()})
    assert not unexpected, 'Unexpected kernel diagnostic: preserve/stop'
    return raw


def platform_state():
    return {p.name: (p / 'status').read_text().strip() for p in OVERLAYS.iterdir() if p.is_dir()}


def read_kv(path):
    text = Path(path).read_text().strip()
    result = {}
    for key, value in re.findall(r'(\w+)=([^ ]+)', text):
        radix = 16 if key in {'status', 'control', 'last_fault', 'mm2s_cr', 'mm2s_sr',
            's2mm_cr', 's2mm_sr', 'dacctl1', 'power1', 'power2', 'power3', 'classd1',
            'iface1', 'clock1', 'clock2', 'pll1', 'pll2', 'pll3', 'pll4'} else 10
        result[key] = int(value, radix)
    return {'raw': text, 'values': result}


def locate(driver, leaf):
    root = Path('/sys/bus/platform/drivers') / driver
    matches = [p.resolve() / leaf for p in root.iterdir() if p.is_symlink()
               and p.name not in {'module', 'subsystem'} and (p.resolve() / leaf).exists()]
    assert len(matches) == 1, (driver, [str(p) for p in matches])
    return matches[0]


def codec_path():
    root = Path('/sys/bus/i2c/drivers/a13-muted-wm8960')
    matches = [p.resolve() / 'muted_state' for p in root.iterdir()
               if re.fullmatch(r'\d+-001a', p.name) and p.is_symlink()]
    assert len(matches) == 1
    return matches[0]


def states(paths, running=False):
    data = {name: read_kv(path) for name, path in paths.items()}
    s, d, c = (data[name]['values'] for name in ('serial', 'dma', 'codec'))
    assert s['status'] >> 16 == 0xa13c and not s['status'] & 31
    assert not s['fatal'] and s['faults'] == 0
    assert c['fault'] == 0 and c['dacctl1'] & 8
    assert c['power1'] & ~0x1c0 == 0 and c['power2'] & ~0x181 == 0
    assert c['power3'] == c['classd1'] == 0
    assert not d['mm2s_sr'] & 0x770 and not d['s2mm_sr'] & 0x770
    if running:
        assert s['running'] == 1 and s['control'] == 1 and s['status'] & 64
        assert c['configured'] == 1 and c['iface1'] == 0x42
        assert c['clock1'] == 5 and c['clock2'] == 0x1c7
        assert d['mm2s_cr'] & 1 and not d['mm2s_sr'] & 1
    else:
        assert not s['running'] and not s['open'] and s['control'] == 0
        assert not c['configured'] and c['iface1'] == 2 and c['power2'] == 0
        assert d['mm2s_sr'] & 1 and d['s2mm_sr'] & 1, 'DMA halt not proven'
    return data


def irq_rows():
    raw = Path('/proc/interrupts').read_text()
    rows = []
    for line in raw.splitlines():
        if 'a1020000' not in line: continue
        left, right = line.split(':', 1); parts = right.split(); count = 0
        while parts and parts[0].isdecimal(): count += int(parts.pop(0))
        rows.append({'linux_irq': int(left), 'count': count, 'description': ' '.join(parts), 'raw': line})
    assert len(rows) == 2
    return rows


def pcm_cycle(index, mode, device, paths):
    lease()
    before = irq_rows()
    label = 'pcm-%02d-%s' % (index, mode)
    save(label + '-before.json', {'states': states(paths), 'interrupts': before})
    with (OUT / (label + '.stdout')).open('xb') as stdout, (OUT / (label + '.stderr')).open('xb') as stderr:
        p = subprocess.Popen([str(OUT / 'pcm_zero_test'), device, mode],
                             stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr)
        CHILDREN.append(p)
        start = time.monotonic(); observed = None
        while time.monotonic() - start < 8:
            if p.poll() is not None: break
            s = read_kv(paths['serial'])['values']
            if s.get('running') and s.get('status', 0) & 64:
                observed = states(paths, running=True)
                break
            time.sleep(.005)
        assert observed is not None, 'Running muted stream not observed; no retry'
        save(label + '-running.json', {'states': observed, 'child_pid': p.pid,
                                      'interrupts': irq_rows()})
        event('MUTED_ZERO_DMA_RUNNING', mode=mode, child_pid=p.pid)
        try: code = p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            raise RuntimeError('PCM child deadline; retained, no signal')
    after = states(paths)
    irq_after = irq_rows()
    assert code == 0, 'PCM test failed; no automatic XRUN recovery'
    delta = {row['linux_irq']: row['count'] for row in irq_after}
    for row in before: delta[row['linux_irq']] -= row['count']
    assert any(value > 0 for value in delta.values()), 'No actual DMA IRQ increment'
    text = (OUT / (label + '.stdout')).read_text()
    assert 'MUTED_PCM_CLOSED' in text and '"constraint_rejections":4' in text
    save(label + '-result.json', {'exit_code': code, 'states': after,
        'hardware_IRQ_delta': delta, 'interrupts': irq_after, 'zero_data_only': True,
        'audible_test': False, 'recording': False})
    event('MUTED_PCM_NORMAL_CLOSE_AND_DMA_HALT_VERIFIED', mode=mode, hardware_IRQ_delta=delta)


def archive_noreplace(source, dest):
    libc = ctypes.CDLL(None, use_errno=True)
    fun = libc.renameat2
    fun.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    fun.restype = ctypes.c_int
    if fun(-100, os.fsencode(source), -100, os.fsencode(dest), 1):
        raise OSError(ctypes.get_errno(), 'renameat2 refused; no overwrite/retry')


def main():
    global LEASE_SHA
    identity()
    assert REQUEST['audible_output'] is False and REQUEST['recording'] is False
    assert not os.path.lexists(OUT) and not os.path.lexists(FW)
    for path in ('/var/lib/kv260-a13', '/lib/firmware/xilinx', CENTRAL, CENTRAL / 'history'):
        trusted(path, True)
    assert all(sha(name) == pin for name, pin in DEFAULT_FILES.items())
    assert not Path('/sys/module/zocl').exists()
    assert not any(Path('/sys/module', n).exists() for n in
                   ('a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card'))
    assert platform_state() == {'k26-starter-kits_image_1': 'applied'}
    raw = kernel_raw(); assert hashlib.sha256(raw).hexdigest() == BASELINE
    before = collect(allow_ps_display=True); require_no_users(before, True, boot_id=BOOT)
    mem = {k: int(v.split()[0]) for k, v in (line.split(':', 1)
            for line in Path('/proc/meminfo').read_text().splitlines())}
    assert (mem['MemTotal'] - mem['MemAvailable']) * 100 < mem['MemTotal'] * 70
    assert mem['CmaFree'] >= 98304, 'Conservative existing resource reserve remains unchanged'
    temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    assert temps and all(0 < x < 55000 for x in temps)
    for path in (CENTRAL / 'a12-finalize-coordinator.lock', CENTRAL / 'deployment.lock',
                 Path('/run/lock/patient-qwen-linear.lock')):
        info = trusted(path)
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW); FDS.append(fd)
        held = os.fstat(fd)
        assert held.st_ino == info.st_ino and held.st_dev == info.st_dev and held.st_nlink == 1
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert not os.path.lexists(CENTRAL / 'active')
    OUT.mkdir(mode=0o700)
    save('request.json', REQUEST)
    save('before.json', {'scan': before, 'memory_kib': mem, 'temperatures_mC': temps,
                         'kernel_raw_sha256': BASELINE, 'default_originals': DEFAULT_FILES})
    with (OUT / 'baseline.kernel.raw').open('xb') as stream: stream.write(raw)
    for name, item in ARTIFACTS.items():
        assert name in {'a13_muted_dma.ko', 'a13_muted_serial.ko', 'a13_muted_codec.ko',
                        'a13_muted_card.ko', 'pcm_zero_test', 'audio-muted.dtbo', 'codec_master.bit.bin'}
        data = base64.b64decode(item['base64'], validate=True)
        assert len(data) == item['bytes'] and hashlib.sha256(data).hexdigest() == item['sha256']
        with (OUT / name).open('xb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
    os.chmod(OUT / 'pcm_zero_test', 0o700)
    start_ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
    active = CENTRAL / 'active'; active.mkdir(mode=0o700)
    lease_obj = {'schema': 'A13_MUTED_MAINTENANCE_LEASE_V1', 'owner': 'A', 'scope': 'all-PL-exclusive-muted',
        'window': 'a13-muted-20261025-v1', 'identity': MACHINE + ':' + BOOT,
        'pid': os.getpid(), 'owner_start_ticks': start_ticks, 'compute_authorized': False,
        'audible_output_authorized': False, 'recording_authorized': False,
        'expires_monotonic_ns': time.monotonic_ns() + 600_000_000_000}
    with (active / 'lease.json').open('x') as stream:
        json.dump(lease_obj, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    LEASE_SHA = sha(active / 'lease.json')
    event('EXCLUSIVE_MUTED_MAINTENANCE_LEASE_ACQUIRED', lease_sha256=LEASE_SHA)
    try:
        FW.mkdir(mode=0o755)
        with (FW / 'codec_master.bit.bin').open('xb') as stream:
            stream.write((OUT / 'codec_master.bit.bin').read_bytes()); stream.flush(); os.fsync(stream.fileno())
        assert sha(FW / 'codec_master.bit.bin') == ARTIFACTS['codec_master.bit.bin']['sha256']
        for name in ('a13_muted_dma', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_card'):
            command('insmod-' + name, ['/usr/sbin/insmod', str(OUT / (name + '.ko'))])
        raw = kernel_transition('after-module-load', raw)
        lease(); save('remove-default-reserved.json', {'target': str(DEFAULT), 'force': False})
        DEFAULT.rmdir(); assert platform_state() == {}
        event('DEFAULT_OVERLAY_NORMALLY_REMOVED')
        MUTED.mkdir(); save('load-muted-reserved.json', {'overlay': str(MUTED), 'bit_sha256': ARTIFACTS['codec_master.bit.bin']['sha256']})
        with (MUTED / 'dtbo').open('wb') as stream: stream.write((OUT / 'audio-muted.dtbo').read_bytes())
        assert platform_state() == {MUTED.name: 'applied'}
        assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() == 'operating'
        raw = kernel_transition('after-muted-overlay', raw)
        # Deferred ASoC probe publication is asynchronous; this waits for device
        # binding only, never reloads a failed overlay/module or retries a run.
        deadline = time.monotonic() + 10
        while True:
            try:
                paths = {'serial': locate('a13-muted-serial', 'muted_status'),
                         'dma': locate('a13-muted-period-dma', 'muted_dma_state'), 'codec': codec_path()}
                card_root = locate('a13-muted-card', 'sound')
                cards = list(card_root.glob('card[0-9]*')); assert len(cards) == 1
                break
            except (OSError, AssertionError):
                if time.monotonic() >= deadline: raise
                time.sleep(.02)
        index = int(cards[0].name[4:]); assert index != 0, 'Do not target existing DP card'
        device = 'hw:%d,0' % index
        save('bound-muted-card.json', {'paths': {k: str(v) for k, v in paths.items()},
            'card': index, 'device': device, 'states': states(paths),
            'cards_raw': Path('/proc/asound/cards').read_text()})
        event('MUTED_CARD_BOUND_ANALOGUE_OUTPUTS_DISABLED', card=index)
        pcm_cycle(1, 'drain', device, paths)
        raw = kernel_transition('after-drain', raw)
        pcm_cycle(2, 'drop', device, paths)
        raw = kernel_transition('after-drop', raw)
        save('before-normal-cleanup.json', {'states': states(paths), 'no_running_children': all(p.poll() is not None for p in CHILDREN)})
        assert all(p.poll() is not None for p in CHILDREN)
        # Accepted IIC writes prove the codec was put in slave/PLL-off state.
        # Only then may the audio overlay disappear and default PL be restored.
        lease(); MUTED.rmdir(); assert platform_state() == {}
        raw = kernel_transition('after-muted-removal', raw)
        for name in ('a13_muted_card', 'a13_muted_serial', 'a13_muted_codec', 'a13_muted_dma'):
            command('rmmod-' + name, ['/usr/sbin/rmmod', name])
        raw = kernel_transition('after-module-removal', raw)
        lease(); DEFAULT.mkdir()
        with (DEFAULT / 'dtbo').open('wb') as stream:
            stream.write(Path('/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.dtbo').read_bytes())
        assert platform_state() == {'k26-starter-kits_image_1': 'applied'}
        assert Path('/sys/class/fpga_manager/fpga0/state').read_text().strip() == 'operating'
        raw = kernel_transition('after-default-restored', raw)
        assert all(sha(name) == pin for name, pin in DEFAULT_FILES.items())
        after = collect(allow_ps_display=True); require_no_users(after, True, boot_id=BOOT)
        assert not Path('/sys/module/zocl').exists()
        archive = CENTRAL / 'history/a13-muted-20261025-v1-completed'
        assert not os.path.lexists(archive)
        save('result.json', {'status': 'BOARD_MUTED_PLAYBACK_DRAIN_DROP_AND_DEFAULT_RESTORE_PASSED',
            'boot_id': BOOT, 'scan': after, 'lease_sha256': LEASE_SHA, 'archive': str(archive),
            'audio_audible_test': 'NOT_TESTED', 'capture': 'NOT_ENABLED_NO_RECORDING',
            'voltage_V': None, 'current_mA': None, 'physical_IIC_edges_or_MTBF': 'NOT_TESTED',
            'kernel_raw_sha256': hashlib.sha256(raw).hexdigest(), 'default_originals_unchanged': True,
            'maintenance_package_retained': str(OUT), 'firmware_package_retained': str(FW)})
        lease(); archive_noreplace(active, archive)
        for directory in (CENTRAL, CENTRAL / 'history'):
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        event('MUTED_WINDOW_COMPLETED_NORMAL_RESTORE', archive=str(archive))
    except Exception as exc:
        event('MUTED_WINDOW_BLOCKED_OWNER_RETAINED', error=type(exc).__name__ + ': ' + str(exc),
              children=[{'pid': p.pid, 'exit_code': p.poll()} for p in CHILDREN],
              no_force_no_reboot_no_automatic_retry=True)
        # Do not release locks or remove a lease while device/child state is
        # unknown. A separate read-only inspector may collect the failure.
        while True: time.sleep(5)
    for fd in reversed(FDS): os.close(fd)
    print(json.dumps({'status': 'MUTED_WINDOW_DONE_INDEPENDENT_POSTCHECK_REQUIRED'}), flush=True)


if __name__ == '__main__':
    main()
