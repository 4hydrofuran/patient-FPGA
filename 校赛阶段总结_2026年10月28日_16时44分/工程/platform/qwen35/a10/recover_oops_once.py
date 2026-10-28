"""One explicitly authorized normal reboot, with pinned identity and receipt.

No force, reset, driver/overlay action, or retry. Passive UART must be ready.
SSH disconnect alone is not successful recovery; independent original-boot
readback is required.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
sys.dont_write_bytecode = True
from minimal_evidence_io import SSH, OPTIONS

BOOT = '751e617d-c003-4b99-be03-bb5c78235d24'
COMMAND = r'''set -e
test "$(cat /proc/sys/kernel/random/boot_id)" = 751e617d-c003-4b99-be03-bb5c78235d24
test "$(uname -r)" = 6.8.12-a10irq1
test "$(sha256sum /etc/machine-id | cut -d ' ' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec
test "$(sha256sum /boot/firmware/image.fit | cut -d ' ' -f1)" = b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9
test "$(sha256sum /boot/firmware/boot.scr.uimg | cut -d ' ' -f1)" = 690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc
test ! -e /home/ubuntu/a10-minimal-20261021-v1/compute.jsonl
test ! -e /home/ubuntu/a10-minimal-20261021-v1/approval.actual.json
printf 'EXACT_OOPS_BOOT_ORIGINAL_BOOT_FILES_VERIFIED_NO_COMPUTE\n'
cat /proc/sys/kernel/random/boot_id
cat /proc/sys/kernel/tainted
cat /sys/class/hwmon/hwmon*/temp*_input
sudo -p '__A10_NORMAL_RECOVERY_SUDO__:' /usr/bin/systemctl reboot
'''


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--authorized-once', action='store_true')
    ap.add_argument('--receipt', type=Path, required=True)
    args = ap.parse_args()
    if not args.authorized_once:
        raise SystemExit('Explicit user confirmation required')
    cmd = [SSH, '-tt', *OPTIONS, 'ubuntu@192.168.2.2', COMMAND]
    with args.receipt.open('x', encoding='utf-8') as f:
        f.write(json.dumps(dict(status='RESERVED_NOT_COMPLETE', argv=cmd)))
        f.flush()
        # SSH/sudo credentials use the actual terminal challenge, never captured
        # in argv/env or Python. stderr stays on the terminal.
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        chunks = []
        while True:
            chunk = os.read(p.stdout.fileno(), 4096)
            if not chunk:
                break
            chunks.append(chunk)
            sys.stdout.write(chunk.decode('utf-8', errors='replace'))
            sys.stdout.flush()
        p.wait()
        captured = b''.join(chunks).decode('utf-8', errors='replace')
        result = dict(status='REBOOT_ATTEMPT_READBACK_REQUIRED', argv=cmd,
                      ssh_exit=p.returncode, stdout=captured,
                      reboot_verified=False, retry_permitted=False)
        f.seek(0)
        json.dump(result, f, indent=2)
        f.truncate()
    print(json.dumps({k: v for k, v in result.items() if k not in ('argv', 'stdout')}))
