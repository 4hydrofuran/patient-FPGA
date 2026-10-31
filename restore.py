"""Verify and restore the split public KV260 project backup to an empty directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile

BASE = Path(__file__).resolve().parent


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def restore_set(manifest_path, schema, dest):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema') != schema:
        raise RuntimeError('Unknown manifest schema')
    rows = manifest['files']
    expected = {r['path']: r for r in rows}
    if len(rows) != len(expected):
        raise RuntimeError('Duplicate file paths in manifest')
    for name in expected:
        path = PurePosixPath(name)
        if path.is_absolute() or not path.parts or '..' in path.parts or '\\' in name or ':' in name:
            raise RuntimeError('Unsafe archive path: ' + name)
    with tempfile.TemporaryDirectory(prefix='kv260-backup-') as tmp:
        archive_path = Path(tmp) / 'backup.zip'
        with archive_path.open('xb') as out:
            for part in manifest['archive']['parts']:
                name = part['path']
                if Path(name).name != name:
                    raise RuntimeError('Unsafe part name')
                src = BASE / name
                if not src.is_file() or src.stat().st_size != part['bytes'] or sha256(src) != part['sha256']:
                    raise RuntimeError('Missing or corrupt archive part: ' + name)
                with src.open('rb') as handle:
                    shutil.copyfileobj(handle, out, 1024 * 1024)
        if archive_path.stat().st_size != manifest['archive']['bytes'] or sha256(archive_path) != manifest['archive']['sha256']:
            raise RuntimeError('Reassembled archive does not match manifest')
        with zipfile.ZipFile(archive_path) as archive:
            names = [i.filename for i in archive.infolist() if not i.is_dir()]
            if len(names) != len(expected) or set(names) != set(expected):
                raise RuntimeError('Archive member list differs from manifest')
            dest.mkdir(parents=True, exist_ok=True)
            for n, name in enumerate(names, 1):
                row = expected[name]
                target = dest.joinpath(*PurePosixPath(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                count = 0
                with archive.open(name) as src, target.open('xb') as out:
                    for chunk in iter(lambda: src.read(1024 * 1024), b''):
                        count += len(chunk)
                        digest.update(chunk)
                        out.write(chunk)
                if count != row['bytes'] or digest.hexdigest() != row['sha256']:
                    raise RuntimeError('Restored file failed verification: ' + name)
                if n % 1000 == 0:
                    print('Restored and verified', n, 'files', flush=True)
    print('Restored and verified', len(expected), 'files to', dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path,
                        help='New or empty directory where the verified files will be written')
    args = parser.parse_args()
    dest = args.destination.resolve()
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise RuntimeError('Destination must be new or empty; refusing to overwrite')
    if os.name == 'nt':
        name = str(dest)
        if name.startswith('\\\\'):
            dest = Path('\\\\?\\UNC\\' + name[2:])
        else:
            dest = Path('\\\\?\\' + name)
    restore_set(BASE / 'MANIFEST.json', 'KV260_PUBLIC_PROJECT_BACKUP_V1', dest)
    board_manifest = BASE / 'BOARD_MANIFEST.json'
    if board_manifest.exists():
        restore_set(board_manifest, 'KV260_PUBLIC_BOARD_BACKUP_V1', dest / 'board-snapshot')


if __name__ == '__main__':
    main()
