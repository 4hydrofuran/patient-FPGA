"""Seal this offline review and verify prior immutable evidence; no rollback run."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-offline-signoff-v1'
EXCLUDE = {'SEAL.json', 'seal-command.json', 'seal-verify-command.json'}
GOV = ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
       'AI_ASSISTANCE.md', 'status/A.md', 'handoffs/A_A13_AUDIO_SIGNOFF_20261024.md']


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


def previous():
    baseline = load(E / 'BASELINE.json')
    count = 0
    for folder, old in baseline['previous_seals'].items():
        base = E.parent / folder
        assert sha(base / 'SEAL.json') == old['seal_sha256']
        for name, entry in load(base / 'SEAL.json')['files'].items():
            assert sha(base / name) == entry['sha256'], (folder, name)
            count += 1
    assert count == baseline['previous_sealed_files_unchanged'] == 760
    for name, entry in baseline['files'].items():
        assert sha(E / 'before' / name) == entry['sha256'], name
    # Original old active sources were also untouched, not just their copies.
    for folder in ['audio_pl', 'audio_pl_build']:
        for p in (E / 'before/source' / folder).iterdir():
            assert sha(ROOT / 'platform/qwen35/a13' / folder / p.name) == sha(p), p.name
    return count


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--verify', action='store_true')
    args = p.parse_args()
    count = previous()
    if args.verify:
        seal = load(E / 'SEAL.json')
        for name, entry in seal['files'].items():
            assert sha(E / name) == entry['sha256'], name
        actual = {p.relative_to(E).as_posix() for p in E.rglob('*') if p.is_file() and p.name not in EXCLUDE}
        assert actual == set(seal['files']), ('unexpected/missing evidence', actual ^ set(seal['files']))
        print(json.dumps({'status': 'SEAL_VERIFIED', 'files': len(seal['files']),
                          'previous_unchanged': count, 'BOARD': 'NOT_TESTED'}))
        return
    for receipt in ['contracts-after', 'config-after', 'pc-tests', 'previous-safety-tests',
                    'previous-build-tests', 'collect-review-v3', 'locked-modules-build',
                    'inspect-queue', 'inspect-controller', 'inspect2-queue', 'inspect2-controller']:
        assert load(E / (receipt + '.json'))['exit_code'] == 0, receipt
    review = load(E / 'OFFLINE_REVIEW.json')
    assert not review['deployment_allowed'] and not review['audio_allowed']
    assert review['measured_current_mA'] is None and review['cdc']['warnings_6_remaining'] == 3
    assert load(E / 'collect-review.json')['exit_code'] == 1
    assert load(E / 'collect-review-v2.json')['exit_code'] == 1
    for path in Path(__file__).resolve().parent.iterdir():
        if path.is_file():
            copy(path, E / 'source-final' / path.name)
    for name in GOV:
        copy(ROOT / 'docs' / name, E / 'after/docs' / name)
    files = {p.relative_to(E).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(E.rglob('*')) if p.is_file() and p.name not in EXCLUDE}
    seal = {'status': 'SEALED_OFFLINE_REVIEW_WITH_OPEN_STREAMING_ELECTRICAL_GATES',
            'BOARD': 'NOT_TESTED', 'current_mA': None, 'deployment_allowed': False,
            'previous_sealed_files_unchanged': count, 'files': files}
    with (E / 'SEAL.json').open('x', encoding='utf-8') as stream:
        json.dump(seal, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    assert all(sha(E / name) == entry['sha256'] for name, entry in files.items())
    print(json.dumps({'status': seal['status'], 'files': len(files), 'previous_unchanged': count,
                      'BOARD': 'NOT_TESTED', 'current_mA': None}))


if __name__ == '__main__':
    main()
