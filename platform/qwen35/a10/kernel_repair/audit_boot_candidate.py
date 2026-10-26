"""Independent PC readback: archives and original non-module boot data, no deployment."""
import gzip
import json
from pathlib import Path
import stat
import subprocess
import tarfile

from inspect_initramfs_layout import inspect, newc
from prepare_boot_candidate import WORK, OLD, NEW, RELEASE, sha, safe_name, filter_old_modules


def archive_name(name, release=RELEASE):
    safe_name(name)
    prefix = 'lib/modules/' + release + '/'
    if not name.startswith(prefix):
        raise ValueError('Outside candidate module tree')
    return name[len(prefix):]


def audit(work=WORK, release=RELEASE, image_sha='dd261f19374ada85873b8b7165b82d36f49515866f9e3cfbe39a88933e083ba2'):
    WORK, RELEASE = Path(work), release
    NEW = 'usr/lib/modules/' + RELEASE
    out = WORK/'boot-candidate-v2'
    manifest = json.loads((out/'manifest.json').read_text())
    if manifest['board_access'] or manifest['board_authorization']:
        raise ValueError('Unexpected board authority')
    for name, row in manifest['artifacts'].items():
        if name not in ('candidate.fit', 'modules.tar.gz', 'Image.gz', 'initramfs.cpio.gz', 'kv260-revB.dtb'):
            raise ValueError('Unexpected artifact')
        data = (out/name).read_bytes()
        if len(data) != row['bytes'] or sha(data) != row['sha256']:
            raise ValueError('Artifact mismatch: '+name)
    checked = json.loads((WORK/'module-stage-audit-v2.json').read_text())
    pinned = {row['path']:row['sha256'] for row in checked['files']}
    seen = set()
    with tarfile.open(out/'modules.tar.gz', 'r:gz') as tar:
        for member in tar:
            name = archive_name(member.name, RELEASE)
            if name in seen or not member.isfile():
                raise ValueError('Duplicate or nonregular module archive entry')
            seen.add(name)
            data = tar.extractfile(member).read()  # stream only; never extract paths
            if name.endswith('.ko'):
                if name not in pinned or sha(data) != pinned[name]:
                    raise ValueError('Module archive hash mismatch: '+name)
            elif '/' in name or not name.startswith('modules.'):
                raise ValueError('Unexpected archive metadata')
    if {name for name in seen if name.endswith('.ko')} != set(pinned):
        raise ValueError('Incomplete full module archive')
    original = (WORK/'original-boot-v2/ramdisk').read_bytes()
    layout = inspect(original)
    base = subprocess.run([str(WORK/'deps/root/usr/bin/zstd'), '-q', '-d', '-c'],
                          input=original[layout['tail_offset']:], capture_output=True, check=True).stdout
    expected_userland, _ = filter_old_modules(base)
    combined = gzip.decompress((out/'initramfs.cpio.gz').read_bytes())
    prefix, end = newc(combined)
    if combined[end:] != expected_userland:
        raise ValueError('Original nonmodule initramfs content changed')
    paths = set()
    module_count = 0
    for row in prefix:
        name = row['path']
        if name in paths or OLD in name:
            raise ValueError('Duplicate or old-version initramfs member')
        paths.add(name)
        if stat.S_ISREG(row['mode']):
            if not name.startswith(NEW+'/'):
                raise ValueError('Unexpected prefix file')
            name = name[len(NEW)+1:]
            if name.endswith('.ko'):
                data = combined[row['data_start']:row['data_end']]
                if name not in pinned or sha(data) != pinned[name]:
                    raise ValueError('Initramfs module mismatch')
                module_count += 1
            elif '/' in name or not name.startswith('modules.'):
                raise ValueError('Unexpected prefix metadata')
        elif not stat.S_ISDIR(row['mode']):
            raise ValueError('Unexpected prefix special member')
    original_modules = {row['path'][len(OLD)+1:-4] for row in layout['archives'][0]['entries']
                        if row['path'].endswith('.ko.zst')}
    if not {NEW+'/'+name for name in original_modules} <= paths:
        raise ValueError('Original initramfs module coverage lost')
    if sha(gzip.decompress((out/'Image.gz').read_bytes())) != image_sha:
        raise ValueError('Wrong decompressed kernel')
    if sha((out/'kv260-revB.dtb').read_bytes()) != '32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3':
        raise ValueError('Original DT altered')
    return {'status':'PASS_PC_ARCHIVE_READBACK_NOT_BOARD', 'kernel_release':RELEASE,
            'full_module_files_verified':len(pinned), 'initramfs_module_files_verified':module_count,
            'original_module_coverage_preserved':True, 'original_nonmodule_cpio_entries_byte_identical':True,
            'original_DTB_identical':True, 'private_keys_or_source_symlinks_in_module_tar':False,
            'original_backups_modified':False, 'board_access':False,
            'board_boot_and_recovery':'NOT_TESTED', 'actual_initramfs_RAM_placement':None}


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit()
    with args.output.open('x') as f:
        json.dump(result, f, indent=2)
    print(json.dumps(result))
