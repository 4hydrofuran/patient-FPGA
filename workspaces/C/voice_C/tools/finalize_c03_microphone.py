"""Seal this microphone extension once, without regenerating historical stages."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
ROLE = ROOT.parent
EVIDENCE = ROOT / 'evidence/c03_mic'


def write(name, value):
    (EVIDENCE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    seal = EVIDENCE / 'artifact_manifest.json'
    if seal.exists():
        raise RuntimeError('This extension is already sealed; use a new evidence directory for later work')
    baseline = json.loads((EVIDENCE / 'c03_before_changes.json').read_text(encoding='utf-8'))
    expected_changes = {'AGENTS.md', 'PROJECT_STATUS.json', 'docs/status/C.md', 'voice_C/README.md'}
    changes, same = [], []
    for row in baseline['files']:
        path = ROLE / row['path']
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual == row['sha256']:
            same.append(row['path'])
        else:
            changes.append(dict(path=row['path'], before_sha256=row['sha256'], after_sha256=actual))
    if {r['path'] for r in changes} != expected_changes:
        raise AssertionError('Unexpected historical changes: ' + repr(changes))
    write('history_integrity.json', dict(baseline_files=len(baseline['files']), unchanged=len(same),
        changes=changes, explanation='Four live status/document files updated; historical source/assets/evidence unchanged'))
    checks = []
    for filename in ('unittest.log', 'unittest_mic_runtime.log'):
        text = (EVIDENCE / filename).read_text(encoding='utf-8')
        match = re.search(r'Ran (\d+) tests', text)
        assert match and int(match.group(1)) == 99 and text.rstrip().endswith('OK'), filename
        checks.append(dict(log=filename, tests=99, passed=99, skipped=0, exit_code=0))
    reports = [json.loads((EVIDENCE / f'real_run_{i:02}/report.json').read_text(encoding='utf-8')) for i in (1, 2, 3)]
    assert reports[0]['status'] == reports[1]['status'] == 'FAILED'
    report = reports[2]
    assert report['status'] == 'PASS_CAPTURE_AND_PROTOCOL'
    capture, audio, final = report['capture'], report['audio_stats'], report['final']
    assert capture['frames'] == audio['frames'] == final['frames'] == 160000
    assert capture['pcm_sha256'] == audio['pcm_sha256'] == final['pcm_sha256']
    assert capture['chunks'] == len(report['chunks']) == 50
    assert capture['opened'] and capture['started'] and capture['released']
    assert not capture['queue_overrun'] and not capture['native_buffer_starvation'] and not capture['cleanup_errors']
    assert report['worker_exit_code'] == 0 and report['raw_audio_retained'] is False
    assert final['text'] == '' and report['human_cer'] is None
    assert json.loads((EVIDENCE / 'user_followup.json').read_text(encoding='utf-8'))['answer'] == '没有朗读，稍后自行测试'
    assert [r['seq'] for r in report['chunks']] == list(range(50))
    for row in report['chunks']:
        assert row['response']['consumed'] and row['sha256'] == row['response']['chunk_sha256']
    trace = [json.loads(line) for line in (EVIDENCE / 'real_run_03/trace.jsonl').read_text(encoding='utf-8').splitlines()]
    responses = [x['message'] for x in trace if x['direction'] == 'response']
    finals = [x for x in responses if x.get('final') is True]
    assert len(finals) == 1 and finals[0]['op'] == 'asr_finish' and finals[0]['type'] == 'result'
    assert all(x.get('commit_allowed') is False for x in responses if x.get('event') == 'partial')
    assert not list(EVIDENCE.rglob('*.pcm')) and not list(EVIDENCE.rglob('*.wav'))
    write('verification.json', dict(status='PASS_PC_MIC_CAPTURE_AND_PROTOCOL', date='2026-10-02',
        tests=checks, failed_attempts_retained=2, successful_captures=1, frames=160000, chunks=50,
        device_released=True, raw_audio_retained=False, human_speech=False, human_quality='NOT_ASSESSED',
        board='NOT_TESTED', default_replacement=False, source_commit=None,
        baseline_files_unchanged=len(same), intentional_live_changes=changes))
    paths = {row['path'] for row in baseline['files']}
    paths.update([
        'voice_C/voicec/microphone.py', 'voice_C/tests/test_microphone.py',
        'voice_C/tools/stream_c03_microphone.py', 'voice_C/tools/run_microphone.ps1',
        'voice_C/tools/prepare_microphone_runtime.py', 'voice_C/tools/finalize_c03_microphone.py',
        'voice_C/MICROPHONE_README.md', 'docs/handoffs/C03_麦克风补充.md',
    ])
    paths.update(p.relative_to(ROLE).as_posix() for p in EVIDENCE.rglob('*')
                 if p.is_file() and p.name not in ('artifact_manifest.json', 'finalize.log'))
    files = []
    for name in sorted(paths):
        path = ROLE / name
        files.append(dict(path=name, bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    write('artifact_manifest.json', dict(stage='C03_MICROPHONE_EXTENSION', scope='LOCAL_ONLY_NOT_DISTRIBUTED',
        date='2026-10-02', raw_audio_retained=False, source_commit=None,
        omitted=['.venv', '.venv_mic', 'temporary audio spool', 'future manual recordings', 'finalize.log', 'self manifest'],
        human_quality='NOT_ASSESSED_USER_DID_NOT_SPEAK', files=files))
    print(json.dumps(dict(status='PASS', sealed_files=len(files), baseline_unchanged=len(same),
                         intentional_live_changes=len(changes)), ensure_ascii=False))


if __name__ == '__main__':
    main()
