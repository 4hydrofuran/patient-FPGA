"""Pinned-root candidate inventory and exact kernel bytes; no hardware mutation."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zlib

ROOT = Path('/var/lib/kv260-a10/a10-isolated-single-20261023-v1')
MANIFEST_SHA = 'ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7'


def main():
    assert len(sys.argv) == 2 and os.geteuid() == 0
    assert not ROOT.is_symlink() and ROOT.stat().st_uid == 0 and not ROOT.stat().st_mode & 0o022
    assert hashlib.sha256((ROOT / 'manifest.json').read_bytes()).hexdigest() == MANIFEST_SHA
    # Root-staged/pinned, pure-Python read-only modules only. Never import XRT.
    sys.path.insert(0, str(ROOT))
    from single_compute_policy import BOOT_FILES, LIBRARIES, KERNEL, MACHINE, digest, verify_bundle
    from accelerator_release_gate_v2 import collect
    assert os.uname().release == KERNEL and digest('/etc/machine-id') == MACHINE
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    assert boot == sys.argv[1]
    verify_bundle(ROOT, MANIFEST_SHA)
    assert not os.path.lexists('/var/lock/kv260-a1/active')
    assert not Path('/sys/module/zocl').exists()
    attempt = None
    assert not (ROOT / 'attempt.json').exists()
    hashes = {p: digest(p) for p in {**BOOT_FILES, **LIBRARIES}}
    assert hashes == {**BOOT_FILES, **LIBRARIES}
    scan = collect(allow_ps_display=True)
    p = subprocess.run(['dmesg', '--raw'], capture_output=True, timeout=3)
    assert p.returncode == 0 and not p.stderr and 0 < len(p.stdout) < 1048576
    assert p.stdout.endswith(b'\n')
    p.stdout.decode('utf-8')
    read_ns = time.monotonic_ns()
    temps = [int(path.read_text()) for path in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    mem = {r.split(':')[0]: int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines()}
    overlays = {q.name: (q / 'status').read_text().strip()
                for q in Path('/sys/kernel/config/device-tree/overlays').iterdir() if q.is_dir()}
    drm = [dict(name=q.name, device=str((q / 'device').resolve()), driver=str((q / 'device/driver').resolve()),
                dev=(q / 'dev').read_text().strip(), inode=(Path('/dev/dri') / q.name).stat().st_ino)
           for q in Path('/sys/class/drm').iterdir() if (q / 'dev').is_file()]
    meta = [dict(path=str(q), exists=q.exists(), uid=q.stat().st_uid if q.exists() else None,
                 mode=oct(q.stat().st_mode & 0o7777) if q.exists() else None, symlink=q.is_symlink())
            for q in (Path('/var/lock/kv260-a1'), Path('/var/lock/kv260-a1/history'),
                      Path('/var/lock/kv260-a1/deployment.lock'), Path('/run/lock/patient-qwen-linear.lock'))]
    result = dict(status='READONLY_CANDIDATE_REVIEW_REQUIRED', boot_id=boot, kernel=KERNEL,
                  temperatures_mC=temps, memory_kib={k: mem[k] for k in ('MemTotal','MemAvailable','CmaTotal','CmaFree')},
                  overlays=overlays, drm_bindings=drm, lock_path_metadata=meta, source=str(ROOT), manifest_sha256=MANIFEST_SHA,
                  platform_hashes=hashes, process_scan=scan,
                  baseline_read_uptime_ns=read_ns, baseline_bytes=len(p.stdout),
                  baseline_sha256=hashlib.sha256(p.stdout).hexdigest(),
                  baseline_zlib_base64=base64.b64encode(zlib.compress(p.stdout)).decode(),
                  preserved_prelock_attempt=attempt, lifecycle_bytes=(ROOT / 'lifecycle.jsonl').stat().st_size if attempt else None,
                  board_mutations=0, compute_runs=0)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
