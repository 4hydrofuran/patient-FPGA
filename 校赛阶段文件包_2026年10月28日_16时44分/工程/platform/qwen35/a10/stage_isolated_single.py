"""Authorized additive root-owned copy only; never imports the candidate code."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import uuid

SOURCE = Path('/home/ubuntu/a10-isolated-single-20261023-v1')
TARGET = Path('/var/lib/kv260-a10/a10-isolated-single-20261023-v1')
MANIFEST_SHA = 'ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7'
MACHINE = 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stage(boot):
    need(str(uuid.UUID(boot)) == boot, 'invalid boot')
    need(os.geteuid() == 0 and os.uname().machine == 'aarch64' and
         os.uname().release == '6.8.12-a10irq2', 'root exact candidate ARM64 system required')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot, 'boot changed')
    need(sha(Path('/etc/machine-id')) == MACHINE, 'wrong board')
    need(not Path('/sys/module/zocl').exists() and not os.path.lexists('/var/lock/kv260-a1/active'),
         'maintenance active; no takeover')
    need(Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()
         == 'applied', 'default overlay missing')
    need(not os.path.lexists(TARGET) and not SOURCE.is_symlink(), 'target exists or source symlink')
    need(TARGET.parent.is_dir() and not TARGET.parent.is_symlink() and
         TARGET.parent.stat().st_uid == 0 and not TARGET.parent.stat().st_mode & 0o022,
         'trusted root parent required')
    need(sha(SOURCE / 'manifest.json') == MANIFEST_SHA, 'manifest differs')
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    need(manifest['schema'] == 'A10_ISOLATED_SINGLE_BUNDLE_V1' and
         manifest['authorization_included'] is False and type(manifest['max_submissions']) is int and
         manifest['max_submissions'] == 1 and manifest['board_accepted'] is False and len(manifest['files']) == 20, 'wrong bundle')
    files = dict(manifest['files'])
    files['manifest.json'] = dict(bytes=(SOURCE / 'manifest.json').stat().st_size, sha256=MANIFEST_SHA)
    need(set(p.name for p in SOURCE.iterdir()) == set(files), 'extra/missing source payload')
    for name, meta in files.items():
        need(Path(name).name == name and '/' not in name and '\\' not in name, 'unsafe file name')
        path = SOURCE / name
        info = path.lstat()
        need(stat.S_ISREG(info.st_mode) and info.st_uid == 1000 and
             info.st_size == meta['bytes'] and sha(path) == meta['sha256'], 'source differs: ' + name)
    temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    need(temps and all(0 < t < 55000 for t in temps), 'temperature gate')
    need(shutil.disk_usage(TARGET.parent).free > 128 * 1024 * 1024, 'storage reserve')
    os.umask(0o077)
    TARGET.mkdir(mode=0o700)
    for name, meta in files.items():
        with (SOURCE / name).open('rb') as src, (TARGET / name).open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 * 1024)
            dst.flush()
            os.fsync(dst.fileno())
        need(sha(TARGET / name) == meta['sha256'], 'root copy readback differs')
    return dict(status='ROOT_BUNDLE_STAGED_HASH_VERIFIED_NOT_EXECUTED', boot_id=boot,
                target=str(TARGET), files=len(files), manifest_sha256=MANIFEST_SHA,
                temperatures_mC=temps, pl_loads=0, compute_runs=0)


if __name__ == '__main__':
    need(len(sys.argv) == 2, 'fresh boot argument required')
    print(json.dumps(stage(sys.argv[1])))
