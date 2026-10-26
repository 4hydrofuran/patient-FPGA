"""封存本轮无板候选及失败证据；验收边界不因封存而扩大。"""
import argparse
import json
from pathlib import Path
import shutil

from freeze_inputs import verify_old, sha

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'
EXCLUDE = {'SEAL.json', 'seal-command.json', 'seal-verify-command.json'}
GOV = ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md',
       'AI_ASSISTANCE.md', 'status/A.md', 'handoffs/A_A13_CODEC_MASTER_OFFLINE_20261025.md']


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def copy(source, target):
    assert not source.is_symlink()
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as incoming, target.open('xb') as outgoing:
        shutil.copyfileobj(incoming, outgoing)
    assert sha(source) == sha(target)


def files():
    return [p for p in sorted(E.rglob('*')) if p.is_file() and p.relative_to(E).as_posix() not in EXCLUDE]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    old = verify_old()
    assert sum(v['files'] for v in old.values()) == 982
    baseline = load(E / 'BASELINE.json')
    for name, digest in baseline['files'].items():
        assert sha(E / 'before' / name) == digest
        if not name.startswith('docs/'):
            assert sha(ROOT / name) == digest, name
    review = load(E / 'OFFLINE_REVIEW.json')
    assert review['BOARD'] == 'NOT_TESTED' and not review['deployment_allowed']
    assert review['audio_attempts'] == 0 and review['raw_strict_gate']['ready'] is False
    assert len(review['targeted_operation_exceptions']) == 13
    if args.verify:
        seal = load(E / 'SEAL.json')
        assert {p.relative_to(E).as_posix() for p in files()} == set(seal['files'])
        for name, entry in seal['files'].items():
            assert sha(E / name) == entry['sha256'], name
        for name, digest in seal['source_files'].items():
            assert sha(SRC / name) == digest, name
        print(json.dumps({'status': 'VERIFIED', 'files': len(seal['files']),
                          'prior_sealed_files_unchanged': 982, 'BOARD': 'NOT_TESTED', 'audio_attempts': 0}))
        return
    for name in ['contracts-after', 'config-after', 'collect-native-tools', 'review-results-v3',
                 'protected-old-verify']:
        assert load(E / (name + '.json'))['exit_code'] == 0, name
    source_files = {}
    for path in sorted(SRC.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            copy(path, E / 'source-final' / path.relative_to(SRC))
            source_files[path.relative_to(SRC).as_posix()] = sha(path)
    for name in GOV:
        copy(ROOT / 'docs' / name, E / 'after/docs' / name)
    value = {'status': 'SEALED_OFFLINE_FUNCTIONAL_PHYSICAL_REVIEW_NOT_DEPLOYMENT',
             'prior_sealed_files_unchanged': 982, 'raw_strict_gate_ready': False,
             'targeted_operation_exceptions': 13, 'BOARD': 'NOT_TESTED',
             'audio_attempts': 0, 'actual_current_mA': None, 'deployment_allowed': False,
             'source_files': source_files,
             'private_TTS_payload': '2266_FILES_VERIFIED_SEPARATELY_NO_NEW_COPY_OR_DISTRIBUTION',
             'files': {p.relative_to(E).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files()}}
    with (E / 'SEAL.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    assert all(sha(E / name) == item['sha256'] for name, item in value['files'].items())
    print(json.dumps({'status': value['status'], 'files': len(value['files']), 'BOARD': 'NOT_TESTED'}))


if __name__ == '__main__':
    main()
