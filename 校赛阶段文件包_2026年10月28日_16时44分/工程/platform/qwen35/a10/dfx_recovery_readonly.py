"""Bounded source/provenance inventory; no dfx client, driver or FPGA operation."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
import time

start = time.monotonic()
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot == 'd07af077-84c9-4910-8529-95757a09106d', 'boot changed'
temps = [int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
assert temps and all(0 < t < 60000 for t in temps), 'health gate'
cmd = ['dpkg-query', '-W', '-f=${Package}\t${Version}\t${source:Package}\t${source:Version}\n',
       'dfx-mgr', 'libdfx-mgr2', 'libdfx1.0', 'xlnx-default-bitstreams']
p = subprocess.run(cmd, timeout=2, capture_output=True, text=True)
assert p.returncode == 0, 'package query failed'
out = dict(boot_id=boot, temperatures_mC=temps, argv=cmd, exit_code=p.returncode, packages=p.stdout, files={})
paths = [
    '/usr/share/doc/dfx-mgr/changelog.Debian.gz',
    '/usr/share/doc/libdfx1.0/changelog.Debian.gz',
    '/etc/dfx-mgrd/default_firmware',
    '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.dtbo',
    '/lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.bit.bin',
    '/usr/lib/aarch64-linux-gnu/libdfx.so.1.0',
    '/usr/lib/aarch64-linux-gnu/libdfx-mgr.so.2.0',
    '/var/lib/dpkg/info/libdfx1.0:arm64.md5sums',
    '/var/lib/dpkg/info/libdfx-mgr2:arm64.md5sums',
]
for name in paths:
    path = Path(name)
    if not path.is_file():
        out['files'][name] = None
        continue
    with path.open('rb') as f:
        data = f.read(2097153)
    assert len(data) <= 2097152, 'file cap'
    item = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    if name.endswith('.dtbo'):
        item['base64'] = base64.b64encode(data).decode()
    elif name.endswith('.gz'):
        with gzip.open(path, 'rt') as f:
            item['changelog_first_8192'] = f.read(8192)
    elif 'md5sums' in name or name.endswith('default_firmware'):
        item['text'] = data.decode()
    out['files'][name] = item
out['fpga_device_node_exists'] = Path('/dev/fpga0').exists()
out['elapsed_s'] = time.monotonic() - start
print(json.dumps(out))
