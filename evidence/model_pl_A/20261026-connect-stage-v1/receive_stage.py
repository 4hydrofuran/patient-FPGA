"""Transfer-only receiver: no imports from candidate, no model or PL execution."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import sys
import zipfile

EXPECTED = 'acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
SIZE = 8325748
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest() == 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert os.getuid() != 0
base = Path.home()/'kv260-staging'
base.mkdir(mode=0o700, exist_ok=True)
assert not base.is_symlink()
final = base/'a12-ordinary-resource-20261026-v1'
partial = base/'.a12-ordinary-resource-20261026-v1-upload'
assert not final.exists() and not partial.exists(), 'Existing upload preserved; use a new directory'
assert shutil.disk_usage(base).free >= 128*1024**2, 'Insufficient space for staged package'
partial.mkdir(mode=0o700)
h = hashlib.sha256()
remaining = SIZE
with (partial/'bundle-v2.zip').open('xb') as f:
    while remaining:
        data = sys.stdin.buffer.read(min(256*1024, remaining))
        if not data:
            raise RuntimeError('Truncated transfer; partial bytes retained')
        f.write(data)
        h.update(data)
        remaining -= len(data)
    f.flush()
    os.fsync(f.fileno())
assert h.hexdigest() == EXPECTED, 'Transfer SHA mismatch; partial retained'
target = partial/'bundle'
target.mkdir(mode=0o700)
with zipfile.ZipFile(partial/'bundle-v2.zip') as z:
    members = z.infolist()
    assert len({i.filename for i in members}) == len(members)
    for info in members:
        name = PurePosixPath(info.filename)
        assert not name.is_absolute() and '..' not in name.parts and '\\' not in info.filename
        mode = info.external_attr >> 16
        assert not stat.S_ISLNK(mode)
        dest = target.joinpath(*name.parts)
        if info.is_dir():
            dest.mkdir(mode=0o700, parents=True, exist_ok=True)
        else:
            dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with z.open(info) as src, dest.open('xb') as dst:
                shutil.copyfileobj(src, dst, 256*1024)
            if mode & 0o111:
                dest.chmod(0o700)
receipt = dict(status='UPLOADED_ONLY_NOT_ACTIVATED_NOT_ACCEPTED', remote_path=str(final),
    package_sha256=h.hexdigest(), package_bytes=SIZE, extracted_files=sum(not i.is_dir() for i in members),
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(), kernel=os.uname().release,
    expected_compute_kernel='6.8.12-a10irq2', kernel_matches_compute=os.uname().release=='6.8.12-a10irq2',
    model_started=False, PL_calls=0, compute_acceptance_performed=False,
    default_boot_modified=False, network_config='runtime_secondary_192.168.2.2/24')
with (partial/'STAGING_STATUS.json').open('x') as f:
    json.dump(receipt, f, indent=2)
    f.write('\n')
    f.flush()
    os.fsync(f.fileno())
partial.rename(final)
print(json.dumps(receipt), flush=True)
