"""One read-only post-cleanup snapshot. OpenSSH handles its hidden credential."""
import argparse
import json
from pathlib import Path
import subprocess
import time


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--execute-readonly', action='store_true')
    ap.add_argument('--receipt', type=Path)
    args = ap.parse_args()
    command = (
        'set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = '
        '751e617d-c003-4b99-be03-bb5c78235d24; '
        'test "$(uname -r)" = 6.8.12-a10irq1; '
        'test ! -e /var/lock/kv260-a1/active; test ! -d /sys/module/zocl; '
        'test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1; '
        'cat /proc/sys/kernel/random/boot_id; uname -r; '
        'cat /sys/class/fpga_manager/fpga0/state; '
        'cat /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status; '
        'grep -E "MemTotal|MemAvailable|CmaTotal|CmaFree" /proc/meminfo; '
        'for f in /sys/class/hwmon/hwmon*/temp*_input; do printf "%s " "$f"; cat "$f"; done; '
        'sha256sum /boot/firmware/image.fit /boot/firmware/boot.scr.uimg '
        '/home/ubuntu/a10-idle-candidate-20261021-v2/idle-result.jsonl '
        '/home/ubuntu/a10-candidate-idle-20261021-v3/idle-result.jsonl '
        '/home/ubuntu/a10-candidate-idle-cleanup-20261021.jsonl '
        '/home/ubuntu/a10-candidate-idle-cleanup-20261021-v2.jsonl; '
        'printf "READONLY_FINAL_DEFAULT_NO_ZOCL_NO_ACTIVE_LEASE\\n"')
    argv = ['C:/Windows/System32/OpenSSH/ssh.exe', '-T', '-o', 'BindAddress=192.168.2.1',
            '-o', 'UserKnownHostsFile=C:/Patientqwen/platform/qwen35/a10/board_ssh_known_hosts',
            '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5',
            '-o', 'ServerAliveInterval=5', '-o', 'ServerAliveCountMax=2',
            '-o', 'NumberOfPasswordPrompts=1', '-o', 'PubkeyAuthentication=no',
            'ubuntu@192.168.2.2', command]
    if not args.execute_readonly:
        print(json.dumps(dict(board_contact=False, argv=argv), indent=2))
        return 0
    if args.receipt is None:
        raise ValueError('exclusive evidence file required')
    with args.receipt.open('x', encoding='utf-8') as output:
        begin = time.monotonic()
        # stdout only; OpenSSH's actual password prompt stays on the terminal.
        result = subprocess.run(argv, stdout=subprocess.PIPE, timeout=60)
        record = dict(argv=argv, exit_code=result.returncode,
                      elapsed_s=time.monotonic() - begin, stdout=result.stdout.decode('utf-8'))
        json.dump(record, output, indent=2)
        print(json.dumps(record, indent=2))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
