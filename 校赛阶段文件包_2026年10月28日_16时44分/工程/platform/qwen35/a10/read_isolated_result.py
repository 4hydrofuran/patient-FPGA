"""Fixed current-window read-only evidence capture, including a parked manager.

No signals, device opens, locks, service changes, or unloads. May run while the
manager retains its locks; never interprets a stopped scan as permission.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import zlib


def pack(raw):
    if len(raw) > 4 * 1024 * 1024:
        raise RuntimeError('bounded evidence cap exceeded')
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(),
                zlib_base64=base64.b64encode(zlib.compress(raw)).decode())


def main():
    root = Path('/var/lib/kv260-a10/a10-isolated-idle-20261023-v4')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert os.geteuid() == 0 and boot == 'c5baeabe-273d-447e-b323-ff07dd7af201'
    assert os.uname().release == '6.8.12-a10irq2'
    assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest() == 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
    assert hashlib.sha256((root / 'manifest.json').read_bytes()).hexdigest() == '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06'
    files = {}
    for name in ('manifest.json', 'attempt.json', 'review.json', 'lifecycle.jsonl',
                 'worker.stdout.jsonl', 'worker.stderr.txt', 'worker-result.json', 'idle-receipt.json', 'prepl-cleanup.json'):
        path = root / name
        files[name] = pack(path.read_bytes()) if path.is_file() else None
    lifecycle = root / 'lifecycle.jsonl'
    manager_pid = None
    if lifecycle.exists():
        with lifecycle.open() as stream:
            first = json.loads(stream.readline(1024 * 1024))
        assert first['boot_id'] == boot and first['window_id'] == root.name
        manager_pid = first['manager_pid']
        assert type(manager_pid) is int and manager_pid > 1
    manager = Path('/proc') / str(manager_pid)
    proc = None
    if manager.exists():
        proc = dict(stat=(manager / 'stat').read_text(), maps=(manager / 'maps').read_text(),
                    status=(manager / 'status').read_text(), cmdline=(manager / 'cmdline').read_bytes().replace(b'\0', b' ').decode(),
                    children=(manager / 'task' / str(manager_pid) / 'children').read_text(),
                    fds={q.name: dict(target=os.readlink(q), fdinfo=(manager / 'fdinfo' / q.name).read_text())
                         for q in (manager / 'fd').iterdir()})
    active = Path('/var/lock/kv260-a1/active/lease.json')
    klog = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
    assert klog.returncode == 0 and not klog.stderr
    gdm = subprocess.run(['systemctl', 'is-active', 'gdm.service'], capture_output=True, timeout=3)
    result = dict(schema='A10_ISOLATED_RESULT_READONLY_V1', boot_id=boot, monotonic_ns=time.monotonic_ns(),
                  files=files, manager_pid=manager_pid, manager_proc=proc, kernel_log=pack(klog.stdout),
                  active_lease=pack(active.read_bytes()) if active.exists() else None,
                  module_present=Path('/sys/module/zocl').exists(),
                  test_package_present=Path('/lib/firmware/xilinx/a10-isolated-idle-20261023-v4').exists(),
                  render_nodes=[str(q) for q in Path('/dev/dri').glob('render*')],
                  overlays={q.name: (q / 'status').read_text().strip()
                            for q in Path('/sys/kernel/config/device-tree/overlays').iterdir() if q.is_dir()},
                  gdm_state=gdm.stdout.decode().strip(), gdm_read_exit=gdm.returncode,
                  temperatures_mC=[int(q.read_text()) for q in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
                  memory_raw=Path('/proc/meminfo').read_text(), hardware_mutations=0)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
