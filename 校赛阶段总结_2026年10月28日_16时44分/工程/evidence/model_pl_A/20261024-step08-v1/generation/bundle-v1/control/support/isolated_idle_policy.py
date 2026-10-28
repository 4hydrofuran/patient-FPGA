"""Pinned A10 idle-only policy. Importing this module performs no I/O."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import uuid

from accelerator_release_gate_v2 import start_ticks

KERNEL = '6.8.12-a10irq2'
MACHINE = 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
DEFAULT = 'k26-starter-kits'
XCLBIN_UUID = '87b3bf55-dfd2-2b35-0a6a-55028f87deec'
SCOPE = 'A10_XRT_IDLE_ISOLATED_ONCE'
CENTRAL = Path('/var/lock/kv260-a1')
LOCKS = (CENTRAL / 'deployment.lock', Path('/run/lock/patient-qwen-linear.lock'))
LIBRARIES = {
    '/usr/lib/libxrt_core.so.2.18.0': '88ad9c1c0c4aba93573436a81b09bbb06ace1d6f1b1dc5285ff987143c1d32d4',
    '/usr/lib/libxrt_coreutil.so.2.18.0': '398f44b57956d19876fc2b547689898b8be51f809822c576ca26f7813c841563',
}
BOOT_FILES = {
    '/boot/firmware/image.fit': '23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e',
    '/boot/firmware/boot.scr.uimg': 'f1eb9e841e100a64f59eed77bccd73396297ce93bbcb6ce4916a7b516793c685',
    '/boot/firmware/a10-candidate-irq2-20261021.fit': 'e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b',
}
ASSETS = {
    'a1-vadd.bit.bin': '772b26d0756e43e71cc1cf05b0f0de9e51b6f25507d427eff5c2f82d3c790c23',
    'a1-vadd.dtbo': '14a014624b084f8c9f39fd13e15e156360f9eae367b7da7994328fee432e4646',
    'vadd.xclbin': '9d1243508f887dfe7db76ad1f37984907fe39567bab1cb118403f7691ed98394',
    'zocl.refcount.ko': '388c45a0edefe221615d71ea948de00d0ef68190bdd8497b053dddf788f72b2c',
}
SOURCES = ('isolated_idle_policy.py', 'isolated_idle_worker.py', 'isolated_idle_trial.py',
           'isolated_idle_entry.py', 'isolated_idle_manager_entry.py',
           'xrt_worker_boundary.py', 'accelerator_release_gate_v2.py',
           'idle_board_trial.py', 'minimal_gate.py', 'kernel_log_gate.py')
CONSUMED_BOOTS = {'0e2f466a-87a3-4f5e-9cf4-50d6b7756832',
                  '30f5664b-4d24-430e-831b-5f5d139d0157',
                  '751e617d-c003-4b99-be03-bb5c78235d24'}


def need(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    def unique(pairs):
        data = {}
        for key, value in pairs:
            need(key not in data, 'duplicate JSON key')
            data[key] = value
        return data
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique)


def validate_review(review):
    need(review.get('schema') == 'A10_ISOLATED_IDLE_REVIEW_V1', 'wrong review schema')
    need(review.get('scope') == SCOPE and review.get('compute_authorized') is False,
         'idle-only scope required')
    need(review.get('authorized') is True and review.get('allow_gdm_stop_restore') is True,
         'explicit scoped authorization missing')
    boot = review.get('boot_id')
    need(type(boot) is str and str(uuid.UUID(boot)) == boot and boot not in CONSUMED_BOOTS,
         'fresh reviewed boot required')
    need(review.get('kernel') == KERNEL and review.get('machine_sha256') == MACHINE,
         'platform identity differs')
    need(re.fullmatch(r'a10-isolated-idle-20261023-v[1-9][0-9]*', review.get('window_id', '')),
         'new isolated window name required')
    for key in ('baseline_sha256', 'bundle_sha256'):
        need(re.fullmatch(r'[0-9a-f]{64}', review.get(key, '')), 'missing digest: ' + key)
    need(type(review.get('baseline_read_uptime_ns')) is int and review['baseline_read_uptime_ns'] > 0,
         'baseline read monotonic timestamp required')
    return review


def verify_bundle(source, expected_sha):
    source = Path(source)
    need(digest(source / 'manifest.json') == expected_sha, 'bundle manifest changed')
    manifest = load_json(source / 'manifest.json')
    need(manifest.get('schema') == 'A10_ISOLATED_IDLE_BUNDLE_V1' and
         manifest.get('scope') == SCOPE and manifest.get('compute_authorized') is False,
         'bundle is not idle only')
    need(set(manifest.get('files', {})) == set(ASSETS) | set(SOURCES) | {'shell.json'},
         'bundle source inventory differs')
    for name, entry in manifest['files'].items():
        need(Path(name).name == name and '/' not in name and '\\' not in name, 'unsafe manifest path')
        path = source / name
        need(not path.is_symlink() and path.is_file() and path.stat().st_size == entry['bytes']
             and digest(path) == entry['sha256'], 'payload differs: ' + name)
    for name, sha in ASSETS.items():
        need(manifest['files'][name]['sha256'] == sha, 'wrong hardware asset: ' + name)
    return manifest


def trusted_file(path):
    path = Path(path)
    info = path.stat()
    need(not path.is_symlink() and info.st_uid == 0 and not info.st_mode & 0o022,
         'root-owned non-writable file/directory required: ' + str(path))


def lock_owned(path, pid):
    """Read exact inode and FLOCK ownership from this process's fdinfo."""
    info = Path(path).stat()
    for entry in (Path('/proc') / str(pid) / 'fd').iterdir():
        try:
            fd_stat = entry.stat()
            if (fd_stat.st_dev, fd_stat.st_ino) != (info.st_dev, info.st_ino):
                continue
            text = (entry.parent.parent / 'fdinfo' / entry.name).read_text()
            if re.search(r'(?m)^lock:\s+\d+:\s+FLOCK\s+ADVISORY\s+WRITE\s+' + str(pid) + r'\s', text):
                return True
        except FileNotFoundError:
            continue
    return False


def verify_owner(identity, review, *, parent=False):
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and os.uname().release == KERNEL,
         'root and exact ARM64 kernel required')
    need(boot == identity['boot_id'] == review['boot_id'], 'boot changed')
    need(identity['window_id'] == review['window_id'], 'window mismatch')
    pid = identity['manager_pid']
    need(type(pid) is int and pid == (os.getppid() if parent else os.getpid()), 'manager PID mismatch')
    lease_path = CENTRAL / 'active/lease.json'
    for path in (CENTRAL, CENTRAL / 'active', lease_path, *LOCKS):
        trusted_file(path)
    need(digest(lease_path) == identity['lease_sha256'], 'lease changed')
    lease = load_json(lease_path)
    need(lease.get('scope') == SCOPE and lease.get('compute_authorized') is False
         and lease.get('window') == review['window_id'] and lease.get('pid') == pid
         and lease.get('identity') == MACHINE + ':' + boot, 'wrong lease owner/scope')
    need(lease.get('owner_start_ticks') == start_ticks(Path('/proc') / str(pid)), 'manager PID reused')
    need(type(lease.get('expires_monotonic_ns')) is int and time.monotonic_ns() < lease['expires_monotonic_ns'],
         'maintenance lease expired')
    need(all(lock_owned(path, pid) for path in LOCKS), 'manager does not hold both exact locks')
    need('libxrt_' not in (Path('/proc') / str(pid) / 'maps').read_text(), 'manager imported XRT')
    return True

