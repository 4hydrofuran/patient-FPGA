"""Seal no-board results, old evidence and the independently verified private package."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-nowire-tts-v1'
PAYLOAD = 'package-arm64-file-only'
EXCLUDE = {'SEAL.json', 'seal-command.json', 'seal-verify-command.json'}
GOV = ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
       'AI_ASSISTANCE.md', 'status/A.md', 'handoffs/A_A13_NOWIRE_TTS_20261024.md']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    assert sha(source) == sha(target)


def evidence_files():
    for path in sorted(E.iterdir()):
        if path.name == PAYLOAD or path.name in EXCLUDE:
            continue
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (p for p in sorted(path.rglob('*')) if p.is_file())


def verify_prior():
    baseline = load(E / 'BASELINE.json')
    count = 0
    for folder, entry in baseline['previous_seals'].items():
        base = E.parent / folder
        assert sha(base / 'SEAL.json') == entry['sha256'], folder
        for name, data in load(base / 'SEAL.json')['files'].items():
            assert sha(base / name) == data['sha256'], (folder, name)
            count += 1
    assert count == baseline['previous_files_unchanged'] == 918
    for name, digest in baseline['files'].items():
        assert sha(E / 'before' / name) == digest
        if not name.startswith('docs/'):
            assert sha(ROOT / name) == digest, name
    return count


def verify_payload():
    package = E / PAYLOAD
    assert sha(package / 'MANIFEST.json') == sha(E / 'TTS_PACKAGE_MANIFEST.json')
    manifest = load(package / 'MANIFEST.json')
    for name, entry in manifest['files'].items():
        assert sha(package / name) == entry['sha256'], name
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'}
    assert actual == set(manifest['files'])
    for path in (ROOT / 'modules/voice_A/file_tts').glob('*.py'):
        assert sha(path) == sha(package / 'code/modules/voice_A/file_tts' / path.name)
    return len(manifest['files'])


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    prior = verify_prior()
    package_files = verify_payload()
    if args.verify:
        seal = load(E / 'SEAL.json')
        for name, entry in seal['files'].items():
            assert sha(E / name) == entry['sha256'], name
        assert {p.relative_to(E).as_posix() for p in evidence_files()} == set(seal['files'])
        print(json.dumps({'status': 'VERIFIED', 'sealed_evidence_files': len(seal['files']),
                          'private_package_files_verified': package_files, 'old_files_unchanged': prior,
                          'BOARD': 'NOT_TESTED', 'audio_attempts': 0}))
        return
    for name in ['contracts-before', 'config-before', 'contracts-after', 'config-after',
                 'freeze-before', 'tests-offline', 'prepare-arm64-package', 'review-results',
                 'tts-pc-files', 'tts-pc-files-v2', 'regression-prior19', 'regression-prior8', 'regression-prior17']:
        assert load(E / (name + '.json'))['exit_code'] == 0, name
    assert load(E / 'tts-arm-launch-refusal.json')['exit_code'] == 2
    review = load(E / 'REVIEW.json')
    assert review['BOARD'] == 'NOT_TESTED' and not review['playback'] and review['current_mA'] is None
    for path in Path(__file__).resolve().parent.iterdir():
        if path.is_file():
            copy(path, E / 'source-final/platform' / path.name)
    for path in (ROOT / 'modules/voice_A/file_tts').glob('*.py'):
        copy(path, E / 'source-final/file_tts' / path.name)
    for name in GOV:
        copy(ROOT / 'docs' / name, E / 'after/docs' / name)
    files = {path.relative_to(E).as_posix(): {'bytes': path.stat().st_size, 'sha256': sha(path)}
             for path in evidence_files()}
    value = {'status': 'SEALED_OFFLINE_CLOCK_FEASIBILITY_AND_FILE_TTS_PREPARATION_NOT_DEPLOYED',
             'previous_sealed_files_unchanged': prior, 'BOARD': 'NOT_TESTED', 'audio_attempts': 0,
             'current_mA': None, 'private_package': {'files': package_files,
                  'manifest_sha256': sha(E / 'TTS_PACKAGE_MANIFEST.json'),
                  'redistribution_allowed': False, 'verified_separately_not_duplicated_in_evidence_file_map': True},
             'files': files}
    with (E / 'SEAL.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    assert all(sha(E / name) == entry['sha256'] for name, entry in files.items())
    print(json.dumps({'status': value['status'], 'sealed_evidence_files': len(files),
                      'private_package_files_verified': package_files, 'old_files_unchanged': prior,
                      'BOARD': 'NOT_TESTED', 'audio_attempts': 0}))


if __name__ == '__main__':
    main()
