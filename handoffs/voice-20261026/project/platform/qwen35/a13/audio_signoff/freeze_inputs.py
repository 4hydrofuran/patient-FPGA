"""Freeze read-only baseline for the offline CDC/IIC/clock review; no board API."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'evidence/a13_A/20261024-audio-offline-signoff-v1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dest:
        shutil.copyfileobj(src, dest)
    assert sha(source) == sha(target)


def main():
    results = {}
    for name in ['20261024-steps01-02-v3', '20261024-step03-v1', '20261024-audio-pl-v1',
                 '20261024-audio-pl-build-v1', '20261024-audio-pl-build-v2']:
        base = ROOT / 'evidence/a13_A' / name
        seal = json.loads((base / 'SEAL.json').read_text(encoding='utf-8'))
        for relative, record in seal['files'].items():
            assert sha(base / relative) == record['sha256'], (name, relative)
        results[name] = {'files': len(seal['files']), 'seal_sha256': sha(base / 'SEAL.json')}
    before = OUT / 'before'
    before.mkdir(exist_ok=False)
    for name in ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
                 'AI_ASSISTANCE.md', 'status/A.md', 'handoffs/A_A13_AUDIO_BUILD_20261024.md']:
        copy(ROOT / 'docs' / name, before / 'docs' / name)
    for folder in ['audio_pl', 'audio_pl_build']:
        for path in sorted((ROOT / 'platform/qwen35/a13' / folder).iterdir()):
            if path.is_file():
                copy(path, before / 'source' / folder / path.name)
    old = ROOT / 'evidence/a13_A/20261024-step03-v1'
    for name in ['DOCUMENT_INPUT.json', 'DOCUMENT_TEXT.txt', 'REFERENCES.json', 'USER_CONNECTION_CONFIRMATION.json']:
        copy(old / name, before / 'module' / name)
    document = json.loads((old / 'DOCUMENT_INPUT.json').read_text(encoding='utf-8'))
    assert sha(Path(document['source'])) == document['sha256'], 'connection document changed'
    result = {'status': 'BASELINE_HASHED_NO_BOARD_ACTION', 'previous_seals': results,
              'previous_sealed_files_unchanged': sum(item['files'] for item in results.values()),
              'connection_document_sha256': document['sha256'], 'BOARD': 'NOT_TESTED',
              'supply_V': 3.3, 'total_limit_mA': 100, 'measured_current_mA': None,
              'files': {p.relative_to(before).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)}
                        for p in sorted(before.rglob('*')) if p.is_file()}}
    with (OUT / 'BASELINE.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write('\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'files'}))


if __name__ == '__main__':
    main()
