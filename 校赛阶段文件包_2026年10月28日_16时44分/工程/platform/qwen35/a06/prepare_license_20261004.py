"""Install the user-supplied official license without exposing license text."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys

R = Path('/mnt/c/Patientqwen')
E = R / 'evidence/A06_acceptance/final-20261004-v1'
SOURCE = Path('/mnt/d/EdgeDownload/Xilinx (2).lic')
TARGET = Path('/home/member-a/.Xilinx/kv260-a-rehost-20261004.lic')
EXPECTED = 'c334722c1bcf29b3a925427b4e19c40067a9d5a734556abade35b7bf7c27ee83'


def main():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED
    text = raw.decode('utf-8')
    ids = sorted(set(re.findall(r'HOSTID=([0-9a-fA-F]{12})(?:\s|\\|$)', text)))
    actual = Path('/sys/class/net/eth0/address').read_text().strip().replace(':', '')
    assert actual == '00155dbc29e7' and actual in ids, 'Host ID changed; no install'
    assert not TARGET.exists() and not TARGET.is_symlink()
    assert TARGET.parent.is_dir() and not TARGET.parent.is_symlink()
    E.mkdir(parents=True, exist_ok=True)
    before = E / 'before'; before.mkdir(exist_ok=False)
    snapshots = {}
    for name in ['AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md',
                 'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'hw/linear_A/KERNEL_SOURCE.json',
                 'hw/linear_A/A07_KERNEL_INTEGRATION.md']:
        dst = before / name; dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(R / name, dst)
        snapshots[name] = hashlib.sha256(dst.read_bytes()).hexdigest()
    # O_EXCL never overwrites old licenses; only the private license directory
    # receives the raw bytes, never the repository or logs.
    fd = os.open(TARGET, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    assert hashlib.sha256(TARGET.read_bytes()).hexdigest() == EXPECTED
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED
    receipt = {'status': 'INSTALLED_HOST_MATCH_TOOL_CHECKOUT_PENDING', 'host_id': actual,
               'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
               'license_sha256': EXPECTED, 'installed_path': str(TARGET), 'mode': '0600',
               'features': re.findall(r'^INCREMENT\s+(\S+)', text, re.M),
               'original_unchanged': True, 'network_identity_modified': False,
               'persistent_host_id_guarantee': False, 'before_sha256': snapshots}
    with (E / 'license-install.json').open('x') as f:
        json.dump(receipt, f, indent=2)
    print(json.dumps({k: receipt[k] for k in ['status', 'host_id', 'license_sha256', 'mode']}))


if __name__ == '__main__':
    main()
