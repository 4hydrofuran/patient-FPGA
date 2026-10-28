"""PC-only exact-backup-derived initramfs/FIT candidate; NEVER a deployment tool."""
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tarfile

from inspect_initramfs_layout import inspect, newc
from audit_full_zocl import RELEASE
from audit_module_stage import module_paths

WORK = Path('/home/member-a/a10-kernel-full-20261019-v1')
OLD = 'usr/lib/modules/6.8.0-1015-xilinx'
NEW = 'usr/lib/modules/' + RELEASE


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or '\0' in name:
        raise ValueError('Unsafe archive member')
    return name


def entry(name, data, mode, inode):
    name = safe_name(name).encode() + b'\0'
    fields = [inode, mode, 0, 0, 1, 1792368000, len(data), 0, 0, 0, 0, len(name), 0]
    raw = b'070701' + ''.join(f'{n:08x}' for n in fields).encode() + name
    raw += b'\0' * (-len(raw) % 4)
    raw += data
    return raw + b'\0' * (-len(raw) % 4)


def old_member(name):
    return name == OLD or name.startswith(OLD + '/')


def filter_old_modules(raw):
    entries, end = newc(raw)
    if any(raw[end:]):
        raise ValueError('Unexpected data after main cpio trailer')
    # Preserve every non-module entry byte-for-byte, including hardlink metadata.
    chunks = [raw[e['entry_start']:e['entry_end']] for e in entries if not old_member(e['path'])]
    chunks.append(entry('TRAILER!!!', b'', 0, 0))
    return b''.join(chunks), sum(old_member(e['path']) for e in entries)


def closure(seeds, deps):
    selected = set()
    todo = list(seeds)
    while todo:
        name = safe_name(todo.pop())
        if name in selected:
            continue
        if name not in deps:
            raise ValueError('Missing module dependency record: ' + name)
        selected.add(name)
        todo.extend(deps[name])
    return sorted(selected)


def build(work=WORK, release=RELEASE, image_sha='dd261f19374ada85873b8b7165b82d36f49515866f9e3cfbe39a88933e083ba2'):
    # Parameters are local to this build; historical callers keep pinned defaults.
    WORK, RELEASE = Path(work), release
    NEW = 'usr/lib/modules/' + RELEASE
    if os.uname().machine != 'x86_64':
        raise ValueError('PC only')
    audit = json.loads((WORK/'module-stage-audit-v2.json').read_text())
    if audit['status'] != 'PASS_PC_STAGED_MODULES_NOT_BOARD':
        raise ValueError('Module audit must pass first')
    stage = WORK/'module-stage-v2/lib/modules'/RELEASE
    modules, _ = module_paths(stage)
    pinned = {r['path']:r['sha256'] for r in audit['files']}
    if set(pinned) != {p.relative_to(stage).as_posix() for p in modules}:
        raise ValueError('Module set changed')
    for p in modules:
        if sha(p.read_bytes()) != pinned[p.relative_to(stage).as_posix()]:
            raise ValueError('Staged module changed')
    original = (WORK/'original-boot-v2/ramdisk').read_bytes()
    layout = inspect(original)
    if len(layout['archives']) != 1 or layout['tail_magic_hex'][:8] != '28b52ffd':
        raise ValueError('Unexpected original initramfs layout')
    seeds = []
    for e in layout['archives'][0]['entries']:
        if stat.S_ISREG(e['mode']):
            if not e['path'].startswith(OLD + '/') or not e['path'].endswith('.ko.zst'):
                raise ValueError('Unexpected leading-archive regular member: '+e['path'])
            seeds.append(e['path'][len(OLD)+1:-4])
        elif not stat.S_ISDIR(e['mode']):
            raise ValueError('Unexpected leading-archive special entry')
    deps = {}
    for line in (stage/'modules.dep').read_text().splitlines():
        name, rest = line.split(':', 1)
        deps[name] = rest.split()
    selected = closure(seeds, deps)
    # v1 preserved: mkimage failed because dtc was absent from its subprocess PATH.
    out = WORK/'boot-candidate-v2'
    out.mkdir(mode=0o700)  # exclusive; never overwrite originals or failed attempts
    root = out/'initramfs-stage'
    dest = root/'lib/modules'/RELEASE
    dest.mkdir(parents=True)
    for name in selected:
        target = dest/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stage/name, target)
    for name in ('modules.builtin', 'modules.builtin.modinfo'):
        shutil.copyfile(stage/name, dest/name)
    (dest/'modules.order').write_text(''.join(n+'\n' for n in selected))
    result = subprocess.run(['/usr/sbin/depmod', '-b', str(root), '-F', str(WORK/'build/System.map'), RELEASE],
                            capture_output=True, text=True)
    (out/'depmod.log').write_text(result.stdout+result.stderr)
    if result.returncode or result.stderr.strip():
        raise ValueError('Initramfs depmod warning/error; inspect preserved log')
    zstd = WORK/'deps/root/usr/bin/zstd'
    base = subprocess.run([str(zstd), '-q', '-d', '-c'], input=original[layout['tail_offset']:],
                          capture_output=True, check=True).stdout
    userland, removed = filter_old_modules(base)
    prefix = bytearray()
    inode = 1
    for directory in ('usr', 'usr/lib', 'usr/lib/modules', NEW):
        prefix += entry(directory, b'', stat.S_IFDIR | 0o755, inode)
        inode += 1
    # No extraction of the original archive, no executing its hooks or binaries.
    for p in sorted(dest.rglob('*')):
        rel = NEW + '/' + p.relative_to(dest).as_posix()
        if p.is_symlink():
            raise ValueError('Unexpected initramfs link')
        if p.is_dir():
            prefix += entry(rel, b'', stat.S_IFDIR | 0o755, inode)
        elif p.is_file():
            prefix += entry(rel, p.read_bytes(), stat.S_IFREG | 0o644, inode)
        else:
            raise ValueError('Unexpected initramfs special file')
        inode += 1
    prefix += entry('TRAILER!!!', b'', 0, 0)
    combined = bytes(prefix) + userland
    packed = gzip.compress(combined, compresslevel=6, mtime=0)
    if gzip.decompress(packed) != combined:
        raise ValueError('Candidate initramfs compression verification failed')
    (out/'initramfs.cpio.gz').write_bytes(packed)
    image = (WORK/'build/arch/arm64/boot/Image').read_bytes()
    if sha(image) != image_sha:
        raise ValueError('Kernel Image hash changed')
    (out/'Image.gz').write_bytes(gzip.compress(image, compresslevel=6, mtime=0))
    dt = (WORK/'original-boot-v2/kv260-revB.dtb').read_bytes()
    if sha(dt) != '32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3':
        raise ValueError('Original DT changed')
    (out/'kv260-revB.dtb').write_bytes(dt)
    its = Path(__file__).with_name('candidate.its').read_text()
    (out/'candidate.its').write_text(its.replace('6.8.12-a10irq1', RELEASE))
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = str(WORK/'deps/root/usr/lib/x86_64-linux-gnu')
    env['SOURCE_DATE_EPOCH'] = '1792368000'
    tools = WORK/'deps/root/usr/bin'
    dtc = WORK/'build/scripts/dtc/dtc'
    if not dtc.is_file() or not os.access(dtc, os.X_OK):
        raise ValueError('Private built dtc unavailable')
    env['PATH'] = str(dtc.parent) + ':' + str(tools) + ':' + env.get('PATH', '')
    result = subprocess.run([str(tools/'mkimage'), '-f', 'candidate.its', 'candidate.fit'],
                            cwd=out, env=env, capture_output=True, text=True)
    (out/'mkimage.log').write_text(result.stdout+result.stderr)
    result.check_returncode()
    for index, name in enumerate(('Image.gz', 'initramfs.cpio.gz', 'kv260-revB.dtb')):
        path = out/('verify-'+name)
        subprocess.run([str(tools/'dumpimage'), '-T', 'flat_dt', '-p', str(index), '-o', str(path),
                        str(out/'candidate.fit')], env=env, check=True, capture_output=True)
        if sha(path.read_bytes()) != sha((out/name).read_bytes()):
            raise ValueError('FIT component mismatch')
    # Full module package: explicit files only, never follow build/source links.
    with (out/'modules.tar.gz').open('xb') as stream:
        with gzip.GzipFile(filename='', mode='wb', fileobj=stream, mtime=0) as gz:
            with tarfile.open(fileobj=gz, mode='w|') as tar:
                members = modules + sorted(stage.glob('modules.*'))
                for p in sorted(members):
                    if p.is_symlink() or not p.is_file():
                        raise ValueError('Refuse non-regular module archive entry')
                    name = 'lib/modules/' + RELEASE + '/' + p.relative_to(stage).as_posix()
                    info = tar.gettarinfo(str(p), arcname=name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ''
                    info.mtime = 1792368000
                    with p.open('rb') as file:
                        tar.addfile(info, file)
    result = {'status': 'PC_BOOT_CANDIDATE_NOT_BOOT_TESTED_NOT_DEPLOYABLE',
        'kernel_release': RELEASE, 'original_initramfs_module_count':len(seeds),
        'candidate_initramfs_module_count':len(selected), 'old_main_archive_entries_removed':removed,
        'nonmodule_userland_preserved': True, 'original_DTB_preserved':True,
        'QSPI_or_SD_written':False, 'board_access':False, 'board_authorization':False,
        'unresolved':['actual U-Boot one-shot boot/return path', 'board kernel boot compatibility',
                      'normal PL teardown without new kernel errors', 'one minimal PL I/O and small BO accounting'],
        'local_only_not_for_publication':True, 'artifacts':{}}
    for name in ('candidate.fit', 'modules.tar.gz', 'Image.gz', 'initramfs.cpio.gz', 'kv260-revB.dtb'):
        p = out/name
        result['artifacts'][name] = {'bytes':p.stat().st_size, 'sha256':sha(p.read_bytes())}
    (out/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    build()
