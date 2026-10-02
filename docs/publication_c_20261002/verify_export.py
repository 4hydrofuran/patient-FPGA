"""Read-only verification of imported publication files and the final candidate ZIP."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def main():
    manifest = json.loads((HERE/'export_manifest.json').read_text('utf-8'))
    failures = []
    for row in manifest['files']:
        path = (ROOT/row['path']).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            failures.append(dict(path=row['path'], error='MISSING_OR_OUTSIDE_ROOT'))
        elif path.stat().st_size != row['bytes'] or digest(path) != row['exported_sha256']:
            failures.append(dict(path=row['path'], error='BYTES_OR_SHA256_MISMATCH'))
    archive = ROOT/'workspaces/C/releases/c04/C_pc_candidate_v1.zip'
    checksum = archive.with_suffix('.zip.sha256').read_text('ascii').split()[0]
    if digest(archive) != checksum:
        failures.append(dict(path=archive.relative_to(ROOT).as_posix(), error='ZIP_CHECKSUM_MISMATCH'))
    print(json.dumps(dict(status='FAIL' if failures else 'PASS', imported_files=len(manifest['files']),
        failures=failures, scope='Imported files; newly authored publication docs and inherited B files are outside this manifest'), ensure_ascii=False))
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
