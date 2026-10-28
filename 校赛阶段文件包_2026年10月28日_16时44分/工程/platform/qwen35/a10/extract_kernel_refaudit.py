"""Extract a hash-pinned, allowlisted source subset on the PC; no board access."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile

ORIG_SHA = '26512115972bdf017a4ac826cc7d3e9b0ba397d4f85cd330e4e4ff54c78061c8'
DIFF_SHA = '2f73ef45d2ddbb70e540fc657bf3c74a7c45d3b0663c10e0a6e45f723c332954'
FILES = ('drivers/of/irq.c', 'drivers/of/platform.c', 'drivers/of/device.c',
         'drivers/of/dynamic.c', 'drivers/of/overlay.c', 'drivers/base/platform.c',
         'drivers/irqchip/irq-xilinx-intc.c', 'kernel/irq/irqdomain.c',
         'include/linux/of_irq.h', 'drivers/of/property.c',
         'drivers/irqchip/irqchip.c', 'drivers/base/core.c', 'include/linux/irqchip.h')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archives', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    orig = a.archives / 'linux-xilinx_6.8.0.orig.tar.gz'
    diff = a.archives / 'linux-xilinx_6.8.0-1015.16.diff.gz'
    if sha(orig.read_bytes()) != ORIG_SHA or sha(diff.read_bytes()) != DIFF_SHA:
        raise ValueError('archive SHA256 mismatch')
    patch = gzip.decompress(diff.read_bytes()).decode('utf-8')
    # Debian diff is file-delimited. Keep complete hunks, only for the chosen files.
    sections = []
    current = []
    for line in patch.splitlines(keepends=True):
        if line.startswith('--- linux-xilinx-6.8.0.orig/') and current:
            sections.append(''.join(current))
            current = []
        current.append(line)
    if current:
        sections.append(''.join(current))
    chosen = []
    for section in sections:
        header = section.splitlines()[0]
        if any(header == f'--- linux-xilinx-6.8.0.orig/{name}' for name in FILES):
            chosen.append(section)
    if not chosen:
        raise ValueError('unrecognized source diff format; no files created')
    a.output.mkdir(parents=True, exist_ok=False)
    manifest = dict(source_package='linux-xilinx 6.8.0-1015.16',
                    orig_sha256=ORIG_SHA, diff_sha256=DIFF_SHA,
                    verification='SHA256 matches Ubuntu published source; not a binary or signature attestation',
                    extracted_originals={})
    with tarfile.open(orig) as archive:
        for name in FILES:
            member = archive.getmember('linux-6.8/' + name)
            if not member.isfile():
                raise ValueError('not a regular source member')
            data = archive.extractfile(member).read()
            target = a.output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as stream:
                stream.write(data)
            manifest['extracted_originals'][name] = sha(data)
    patch_bytes = ''.join(chosen).encode('utf-8')
    with (a.output / 'selected-package.patch').open('xb') as stream:
        stream.write(patch_bytes)
    manifest['selected_patch_sha256'] = sha(patch_bytes)
    with (a.output / 'extraction.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
