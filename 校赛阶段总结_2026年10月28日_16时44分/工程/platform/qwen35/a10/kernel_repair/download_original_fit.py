"""Read one pinned board FIT via SCP into a NEW local directory; no remote writes.

Authentication is handled interactively by OpenSSH, never by this program.
"""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = ROOT / 'platform/local/a10-boot-backup-20261019/fit-v2'
EXPECTED = 'b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9'


if __name__ == '__main__':
    OUTPUT.mkdir(parents=True, exist_ok=False)
    known = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
    if known.read_text(encoding='utf-8').strip() != '192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe':
        raise SystemExit('Host key pin changed')
    argv = ['C:/Windows/System32/OpenSSH/scp.exe', '-l', '65536',
            '-o', 'BindAddress=192.168.2.1',
            '-o', f'UserKnownHostsFile={known.as_posix()}', '-o', 'StrictHostKeyChecking=yes',
            '-o', 'ConnectTimeout=5', '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no',
            'ubuntu@192.168.2.2:/boot/firmware/image.fit', str(OUTPUT / 'image.fit')]
    t = time.monotonic()
    result = subprocess.run(argv)
    path = OUTPUT / 'image.fit'
    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    good = result.returncode == 0 and actual == EXPECTED and path.stat().st_size == 64453664
    report = dict(argv=argv, scp_exit_code=result.returncode, elapsed_s=time.monotonic()-t,
                  bytes=path.stat().st_size if path.is_file() else None, sha256=actual,
                  expected_sha256=EXPECTED, status='FIT_BACKUP_HASH_MATCH' if good else 'FAILED_NOT_VERIFIED',
                  credential_logged=False, remote_write=False, board_compute=False)
    with (OUTPUT / 'download.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    print(json.dumps(report))
    raise SystemExit(0 if good else 2)
