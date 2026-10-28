"""Confirm A06 freeze and seal current/prior evidence without any license body."""
import hashlib
import json
from pathlib import Path
R = Path(__file__).resolve().parents[3]
E = R / 'evidence/A06_acceptance/final-20261004-v1'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    audit = read(E / 'AUDIT.json')
    kernel = read(R / 'hw/linear_A/KERNEL_SOURCE.json')
    status = read(R / 'docs/PROJECT_STATUS.json')
    assert audit['status'] == status['stage_status'] == 'PASS_A06_OFFLINE_KERNEL_ACCEPTANCE'
    assert kernel['accepted'] and kernel['frozen'] and not kernel['deployment_allowed']
    assert kernel['A07_offline_link_allowed']
    assert audit['xo_sha256'] == kernel['xo_sha256']
    assert read(E / 'commands/final-audit.json')['exit_code'] == 0
    assert read(E / 'commands/queue-run.json')['exit_code'] == 0
    report = dict(audit, accepted=True, frozen=True, freeze_scope='A07_OFFLINE_ONLY',
                  kernel_source_sha256=sha(R / 'hw/linear_A/KERNEL_SOURCE.json'),
                  acceptance_audit_sha256=sha(E / 'AUDIT.json'))
    for row in report['matrix']:
        if row['status'] == 'READY_TO_FREEZE':
            row['status'] = 'PASS_FROZEN'
    with (E / 'REPORT.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    files = {}
    paths = list(E.rglob('*')) + [R / n for n in [
        'AGENTS.md', 'docs/PROJECT_STATUS.json', 'docs/status/A.md', 'docs/DESIGN_GAP.md',
        'docs/TEST_MATRIX.md', 'docs/handoffs/A_A06_ACCEPTED_20261004.md',
        'hw/linear_A/KERNEL_SOURCE.json', 'hw/linear_A/A07_KERNEL_INTEGRATION.md']]
    paths += list((R / 'platform/qwen35/a06').glob('*20261004*'))
    paths += [R / 'platform/qwen35/a06/closeout_csim.py']
    # These snapshots already bind all received B originals and reviewed traces.
    for folder in ['supplement-v1', 'a-owned-closeout-v1']:
        p = R / 'evidence/A06_acceptance' / folder / 'files.sha256.json'
        files[p.relative_to(R).as_posix()] = sha(p)
        for name, digest in read(p)['files'].items():
            if name.startswith('hw/linear_B_received/') or name.startswith('evidence/A06_acceptance/'):
                assert sha(R / name) == digest, name
                files[name] = digest
    for p in paths:
        if not p.is_file() or p.name in ['files.sha256.json', 'seal.json']:
            continue
        assert p.suffix != '.lic', 'Never seal a credential'
        files[p.relative_to(R).as_posix()] = sha(p)
    with (E / 'files.sha256.json').open('x', encoding='utf-8') as f:
        json.dump({'scope': 'A06_FINAL_OFFLINE_ACCEPTANCE_NOT_BOARD', 'files': dict(sorted(files.items())),
                   'excluded': ['self', 'in-flight commands/seal.json', 'license bodies'],
                   'new_commit': None}, f, indent=2)
    for name, digest in files.items():
        assert sha(R / name) == digest, name
    print(json.dumps({'status': report['status'], 'files': len(files),
                      'seal_sha256': sha(E / 'files.sha256.json'), 'BOARD': 'NOT_TESTED'}))


if __name__ == '__main__':
    main()
