"""Stage candidate translation units and exact private header for PC cross-compile."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bundle', type=Path, required=True)
    ap.add_argument('--archives', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    orig = a.archives / 'linux-xilinx_6.8.0.orig.tar.gz'
    diff = a.archives / 'linux-xilinx_6.8.0-1015.16.diff.gz'
    assert sha(orig) == '26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c8'
    assert sha(diff) == '2f73ef45d2ddbb70e540fc657bf3c74a7c45d3b0663c10e0a6e45f723c332954'
    manifest = json.loads((a.bundle / 'manifest.json').read_text(encoding='utf-8'))
    for name, hashes in manifest['files'].items():
        assert sha(a.bundle / 'candidate' / name) == hashes['candidate_sha256']
    patch = gzip.decompress(diff.read_bytes()).decode('utf-8')
    header = 'drivers/of/of_private.h'
    marker = '--- linux-xilinx-6.8.0.orig/' + header + '\n'
    start = patch.index(marker)
    end = patch.find('\n--- linux-xilinx-6.8.0.orig/', start + len(marker))
    section = patch[start:] if end == -1 else patch[start:end + 1]
    a.output.mkdir(parents=True, exist_ok=False)
    for name in manifest['files']:
        target = a.output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as dest:
            dest.write((a.bundle / 'candidate' / name).read_bytes())
    with tarfile.open(orig) as archive:
        member = archive.getmember('linux-6.8/' + header)
        assert member.isfile()
        with (a.output / header).open('xb') as dest:
            dest.write(archive.extractfile(member).read())
    p = subprocess.run(['patch', '--batch', '--forward', '--fuzz=0', '-p1'], input=section,
                       cwd=a.output, text=True, capture_output=True)
    print(json.dumps(dict(private_header_patch_exit=p.returncode, stdout=p.stdout, stderr=p.stderr)))
    if p.returncode:
        raise SystemExit(p.returncode)
    shutil.copyfile(Path(__file__).with_name('Kbuild'), a.output / 'Kbuild')
    # Normalize only newly staged inputs, never host/board clocks or source archives.
    # Windows/WSL timestamp skew otherwise makes make warn about future inputs.
    for name in [*manifest['files'], header, 'Kbuild']:
        os.utime(a.output / name, (1735689600, 1735689600))
    print(json.dumps(dict(source_hashes={name: sha(a.output / name) for name in [*manifest['files'], header]},
                          input_mtime_epoch=1735689600,
                          cross_compile_only=True, install_allowed=False)))
