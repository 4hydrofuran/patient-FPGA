"""冻结新主时钟方案输入，只读核对旧封存；不连接板卡。"""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[4]
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'
SEALS = ['20261024-steps01-02-v3', '20261024-step03-v1', '20261024-audio-pl-v1',
         '20261024-audio-pl-build-v1', '20261024-audio-pl-build-v2',
         '20261024-audio-offline-signoff-v1', '20261024-audio-nowire-tts-v1']


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4194304), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_old():
    result = {}
    for name in SEALS:
        base = E.parent / name
        seal = json.loads((base / 'SEAL.json').read_text(encoding='utf-8'))
        for item, entry in seal['files'].items():
            assert sha(base / item) == entry['sha256'], (name, item)
        result[name] = {'files': len(seal['files']), 'seal_sha256': sha(base / 'SEAL.json')}
    return result


def main():
    previous = verify_old()
    before = E / 'before'
    before.mkdir(exist_ok=False)
    names = ['docs/' + n for n in ['PROJECT_STATUS.json', 'DESIGN_GAP.md', 'DECISIONS.md',
             'TEST_MATRIX.md', 'AI_ASSISTANCE.md', 'status/A.md', 'A13_TASK_SPEC_20261024.md',
             'handoffs/A_A13_NOWIRE_TTS_20261024.md']]
    names += ['contracts/qwen35/contracts.lock', 'contracts/qwen35/voice_v1.json',
              'platform/toolchain.lock.json', 'modules/voice_A/engine.py', 'modules/voice_A/worker.py',
              'modules/voice_A/manifest.json', 'modules/voice_A/resources.lock.json']
    files = {}
    for name in names:
        target = before / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with (ROOT / name).open('rb') as source, target.open('xb') as out:
            shutil.copyfileobj(source, out)
        files[name] = sha(target)
        assert files[name] == sha(ROOT / name)
    value = {'previous': previous, 'files': files, 'BOARD': 'NOT_TESTED',
             'supply_V': 3.3, 'total_limit_mA': 100, 'current_mA': None, 'audio_allowed': False}
    with (E / 'BASELINE.json').open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'previous_files': sum(v['files'] for v in previous.values()),
                      'frozen_inputs': len(files), 'BOARD': 'NOT_TESTED'}))


if __name__ == '__main__':
    main()
