"""最终只读连续性复核：不动其他任务状态或任何板端对象。"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SRC = Path(__file__).resolve().parent
E = ROOT / 'evidence/a13_A/20261025-audio-codec-master-v1'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old = load(E / 'governance-before-closeout/PROJECT_STATUS.json')
    current = load(ROOT / 'docs/PROJECT_STATUS.json')
    own = current.pop('a13_codec_master_offline_20261025')
    assert current == old, 'Other task status changed during closeout; inspect, do not overwrite'
    assert own['BOARD'] == 'NOT_TESTED' and own['audio_attempts'] == 0 and not own['deployment_allowed']
    for name in ['DESIGN_GAP.md', 'DECISIONS.md', 'TEST_MATRIX.md', 'AI_ASSISTANCE.md', 'status/A.md']:
        before = (E / 'governance-before-closeout' / name).read_text(encoding='utf-8')
        after = (ROOT / 'docs' / name).read_text(encoding='utf-8')
        assert after.startswith(before) or after.endswith(before), name
    assert sha(SRC / 'model.py') == sha(ROOT / 'local/a13c_s01/inputs/model.py') == sha(ROOT / 'local/a13c_s05/inputs/model.py')
    static = load(E / 'static-audit-final/RESULT.json')
    for name, digest in static['rtl_sha256'].items():
        assert sha(SRC / 'rtl' / name) == digest
    guard = load(E / 'dma-guard-pc/RESULT.json')
    assert sha(E / 'module-candidates-v5/modules/a13_period_dma.c') == guard['fixed_source_sha256']
    for path in (E / 'module-candidates-v5/modules').glob('*.ko'):
        header = path.read_bytes()[:20]
        assert header[:6] == b'\x7fELF\x02\x01' and int.from_bytes(header[18:20], 'little') == 183
    dt = load(E / 'dt-verified/RESULT.json')
    assert sha(SRC / 'wm8960-master-disabled.dtso') == dt['source_sha256']
    review = load(E / 'OFFLINE_REVIEW.json')
    assert load(E / 'hwh-b05-v2/RESULT.json')['xsa_sha256'] == review['implementation']['xsa_sha256']
    artifacts = E / 'native-tools/b05/artifacts'
    assert sha(artifacts / 'codec_master.xsa') == review['implementation']['xsa_sha256']
    assert sha(artifacts / 'codec_master_routed.dcp') == review['implementation']['DCP_sha256']
    assert load(SRC / 'POWER_STATUS.json')['board_operations_currently_allowed'] is False
    result = {'status': 'PASS_FINAL_SOURCE_ARTIFACT_GOVERNANCE_CONTINUITY',
              'other_task_JSON_values_unchanged': True, 'prior_Markdown_body_text_preserved': True,
              'DMA_C_guard_equals_actual_AArch64_build_source': True, 'BOARD': 'NOT_TESTED',
              'audio_attempts': 0, 'deployment_allowed': False}
    with (E / 'FINAL_INTEGRITY.json').open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
