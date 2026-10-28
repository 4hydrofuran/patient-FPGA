"""Publish a NEW source-only package after actual PC component checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile
sys.dont_write_bytecode = True
from build_package import write_manifest
from verify_package import verify

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--staging', type=Path, required=True)
    ap.add_argument('--validation', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--failures', type=Path, required=True)
    ap.add_argument('--receipt', type=Path, required=True)
    a = ap.parse_args()
    stage, result_dir, out = a.staging.resolve(), a.validation.resolve(), a.output.resolve()
    verify(stage)
    result = json.loads((result_dir / 'RESULT.json').read_text(encoding='utf-8'))
    assert result['status'] == 'PASS_PC_SYNTHETIC_COMPONENTS'
    projection = [json.loads(x) for x in (result_dir / 'projection.stdout.txt').read_text().splitlines() if x.startswith('{')]
    assert projection[-1]['cases'] == 126
    # The published compile/test sources must equal those actually checked in staging.
    if out.exists() or out.with_suffix('.zip').exists(): raise ValueError('Output already exists')
    shutil.copytree(stage, out)
    valid = out / 'validation'; valid.mkdir()
    for p in sorted(result_dir.iterdir()):
        if p.is_file() and p.name in {'COMMANDS.json', 'RESULT.json', 'configure.stdout.txt', 'configure.stderr.txt',
                                      'build.stdout.txt', 'build.stderr.txt', 'projection.stdout.txt',
                                      'projection.stderr.txt', 'profile.stdout.txt', 'profile.stderr.txt'}:
            shutil.copyfile(p, valid / p.name)
    shutil.copyfile(a.failures, valid / 'PACKAGING_FAILURES.json')
    metadata = {'status': 'PASS_PC_BASELINE_COMPONENTS_ONLY', 'synthetic_projection_cases': 126,
                'profile_baseline_checks': 6, 'full_model': 'NOT_TESTED', 'CROSS_BUILD': 'NOT_TESTED',
                'BOARD': 'NOT_TESTED', 'optimization_implemented': False, 'board_speedup': None,
                'tested_staging_manifest_sha256': sha(stage / 'MANIFEST.json'),
                'publication_changes': 'Only validation records/manifest added after the tested staging.',
                'tested_source_files': {p.relative_to(stage).as_posix(): sha(p)
                                       for folder in ['source', 'tests', 'tools']
                                       for p in (stage / folder).rglob('*') if p.is_file()}}
    for name, digest in metadata['tested_source_files'].items(): assert sha(out / name) == digest
    (valid / 'SCOPE.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    write_manifest(out)
    check = verify(out)
    archive = out.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(out.rglob('*')):
            if p.is_file(): z.write(p, out.name + '/' + p.relative_to(out).as_posix())
    manifest = json.loads((out / 'MANIFEST.json').read_text(encoding='utf-8'))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        names = set(z.namelist()); prefix = out.name + '/'
        assert names == {prefix + n for n in manifest['files']} | {prefix + 'MANIFEST.json'}
        for name, meta in manifest['files'].items():
            data = z.read(prefix + name)
            assert len(data) == meta['bytes'] and hashlib.sha256(data).hexdigest() == meta['sha256']
    receipt = {'status': 'PASS_PUBLISHED_SOURCE_HANDOFF', 'archive': str(archive),
               'archive_bytes': archive.stat().st_size, 'archive_sha256': sha(archive),
               'manifest_sha256': sha(out / 'MANIFEST.json'), 'package_check': check,
               'ZIP_CRC_and_all_payload_hashes': 'PASS', 'PC_cases': 126, 'profile_checks': 6,
               'BOARD': 'NOT_TESTED', 'model_runs': 0, 'device_accesses': 0,
               'CROSS_BUILD': 'NOT_TESTED', 'credentials_or_weight_payloads_included': False}
    a.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    archive.with_suffix('.zip.sha256').write_text(receipt['archive_sha256'] + '  ' + archive.name + '\n', encoding='ascii')
    print(json.dumps(receipt, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
