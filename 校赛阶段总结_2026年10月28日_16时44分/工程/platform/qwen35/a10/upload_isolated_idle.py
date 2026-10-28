"""Fixed, additive PC-to-board idle bundle upload; no execution or installation."""
import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid

from isolated_idle_policy import MACHINE, digest, need, verify_bundle

ROOT = Path(__file__).resolve().parents[3]
BUNDLE = ROOT / 'platform/local/a10-isolated-idle-20261023-v4'
MANIFEST_SHA = '726723f471aa6bb3f6902b5a65a543402be0cf94202c25e169f89b9703867b06'
REMOTE = '/home/ubuntu/a10-isolated-idle-20261023-v4'
HOST_KEY = '192.168.2.2 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJzl9EZaYhasiRc6si0HnT5tdzIcCGjVrFXMN8g57GGe'


def plan(boot):
    need(str(uuid.UUID(boot)) == boot, 'exact fresh boot required')
    m = verify_bundle(BUNDLE, MANIFEST_SHA)
    known = ROOT / 'platform/qwen35/a10/board_ssh_known_hosts'
    need(known.read_text().strip() == HOST_KEY, 'SSH key pin changed')
    options = ['-o', 'BindAddress=192.168.2.1', '-o', f'UserKnownHostsFile={known.as_posix()}',
               '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
               '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
               '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no']
    guard = (f'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = {boot}; '
             'test "$(uname -r)" = 6.8.12-a10irq2; test "$(id -u)" = 1000; '
             f'test "$(sha256sum /etc/machine-id | cut -d \' \' -f1)" = {MACHINE}; '
             'test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; '
             'test "$(cat /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status)" = applied; ')
    ssh = ['C:/Windows/System32/OpenSSH/ssh.exe', '-T', *options, 'ubuntu@192.168.2.2']
    paths = [BUNDLE / n for n in sorted(m['files'])] + [BUNDLE / 'manifest.json']
    hashes = {p.name: digest(p) for p in paths}
    commands = [ssh + [guard + 'umask 077; mkdir ' + REMOTE],
                ['C:/Windows/System32/OpenSSH/scp.exe', '-l', '16384', *options,
                 *[str(p) for p in paths], 'ubuntu@192.168.2.2:' + REMOTE + '/'],
                ssh + [guard + 'cd ' + REMOTE + '; sha256sum ' + ' '.join(sorted(hashes))]]
    return commands, hashes


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--boot-id', required=True)
    ap.add_argument('--execute-authorized-upload', action='store_true')
    ap.add_argument('--receipt', type=Path)
    args = ap.parse_args(argv)
    commands, hashes = plan(args.boot_id)
    if not args.execute_authorized_upload:
        print(json.dumps(dict(board_contact=False, commands=commands, hashes=hashes), indent=2))
        return 0
    need(args.receipt is not None, 'exclusive receipt required')
    report = dict(status='RESERVED', boot_id=args.boot_id, manifest_sha256=MANIFEST_SHA,
                  remote=REMOTE, commands=[], hashes=hashes, board_execution=False, pl_loads=0, compute_runs=0)
    with args.receipt.open('x', encoding='utf-8') as receipt:
        json.dump(report, receipt); receipt.flush()
        started = time.monotonic()
        try:
            for command in commands:
                # Password is handled only by OpenSSH's real terminal prompt.
                proc = subprocess.run(command, stdout=subprocess.PIPE)
                output = proc.stdout.decode('utf-8', errors='replace')
                report['commands'].append(dict(argv=command, exit_code=proc.returncode, stdout=output))
                need(proc.returncode == 0, 'upload failed: no retry/overwrite/execution')
            found = {row.split()[1]: row.split()[0] for row in output.splitlines() if len(row.split()) == 2}
            need(found == hashes, 'board readback hash mismatch')
            report['status'] = 'USER_BUNDLE_UPLOADED_HASH_VERIFIED_NOT_EXECUTED'
        except Exception as exc:
            report['status'], report['error'] = 'STOPPED', str(exc)
        finally:
            report['elapsed_s'] = time.monotonic() - started
            receipt.seek(0); json.dump(report, receipt, indent=2); receipt.truncate(); receipt.flush()
    print(json.dumps(dict(status=report['status'], receipt=str(args.receipt))))
    return 0 if report['status'] == 'USER_BUNDLE_UPLOADED_HASH_VERIFIED_NOT_EXECUTED' else 2


if __name__ == '__main__':
    raise SystemExit(main())
