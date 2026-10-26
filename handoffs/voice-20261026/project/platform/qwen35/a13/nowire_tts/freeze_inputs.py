"""Freeze the no-rewire/24MHz and file-only TTS baseline; offline only."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261024-audio-nowire-tts-v1'


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as src, target.open('xb') as dst:
        shutil.copyfileobj(src, dst)
    assert sha(source) == sha(target)


def main():
    seals = {}
    for name in ['20261024-steps01-02-v3', '20261024-step03-v1', '20261024-audio-pl-v1',
                 '20261024-audio-pl-build-v1', '20261024-audio-pl-build-v2',
                 '20261024-audio-offline-signoff-v1']:
        base = E.parent / name
        seal = json.loads((base / 'SEAL.json').read_text(encoding='utf-8'))
        for relative, entry in seal['files'].items():
            assert sha(base / relative) == entry['sha256'], (name, relative)
        seals[name] = {'files': len(seal['files']), 'sha256': sha(base / 'SEAL.json')}
    names = [f'docs/{name}' for name in ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md',
             'TEST_MATRIX.md', 'AI_ASSISTANCE.md', 'status/A.md', 'A13_TASK_SPEC_20261024.md',
             'handoffs/A_A13_AUDIO_SIGNOFF_20261024.md']]
    names += [f'modules/voice_A/{name}' for name in ['README.md', 'manifest.json',
              'resources.lock.json', 'requirements.pc.lock.txt', 'engine.py', 'worker.py']]
    names += ['contracts/qwen35/voice_v1.json', 'contracts/qwen35/contracts.lock',
              'evidence/a13_A/20261024-step03-v1/BOARD_ENV.json',
              'evidence/a13_A/20261024-step03-v1/ABI_ASSESSMENT.json']
    before = E / 'before'
    before.mkdir(exist_ok=False)
    for name in names:
        copy(ROOT / name, before / name)
    baseline = {'previous_seals': seals, 'previous_files_unchanged': sum(s['files'] for s in seals.values()),
                'files': {p.relative_to(before).as_posix(): sha(p) for p in sorted(before.rglob('*')) if p.is_file()},
                'BOARD': 'NOT_TESTED', 'current_mA': None}
    with (E / 'BASELINE.json').open('x', encoding='utf-8') as stream:
        json.dump(baseline, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'previous_files_unchanged': baseline['previous_files_unchanged'],
                      'frozen_inputs': len(baseline['files']), 'BOARD': 'NOT_TESTED'}))


if __name__ == '__main__':
    main()
