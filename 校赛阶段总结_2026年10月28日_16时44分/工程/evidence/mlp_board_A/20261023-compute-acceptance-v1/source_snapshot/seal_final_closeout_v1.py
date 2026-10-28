"""PC-only evidence snapshot/seal. Never connects to or changes the board."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[3]
EV = ROOT / 'evidence/mlp_board_A/20261023-final-closeout-v1'
HANDOFF = ROOT / 'docs/handoffs/A11_CROSS_CHAT_HANDOFF_20261023.md'
DESKTOP = Path('C:/Users/Fang/Desktop/KV260_Qwen35_A11_跨对话交付_20261023.md')


def digest(path):
    return dict(bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def copy_new(source, target):
    assert source.is_file() and not target.exists(), str(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert digest(source) == digest(target)


def main():
    assert not (EV / 'SEAL.json').exists(), 'Never overwrite a seal'
    audit = json.loads((EV / 'AUDIT.json').read_bytes())
    assert audit['status'] == 'PASS_CLOSEOUT_ONLY_NOT_A11'
    assert audit['A11'] == 'NOT_PASSED' and audit['A12'] == 'NOT_ELIGIBLE'
    assert audit['locks_held'] == 0 and audit['active_lease_absent']
    for name in ('contracts_01.json', 'config_01.json', 'tests_v2_01.json',
                 'tests_v2_02.json', 'audit_01.json'):
        assert json.loads((EV / name).read_bytes())['exit_code'] == 0, name
    assert 'Ran 16 tests' in json.loads((EV / 'tests_v2_02.json').read_bytes())['stderr']
    for name in ('execute_02', 'readback_01'):
        assert json.loads((EV / name / 'receipt.json').read_bytes())['exit_code'] == 0
    receipt = json.loads((EV / 'execute_02/receipt.json').read_bytes())
    assert receipt['helper_sha256'] == digest(ROOT / 'platform/qwen35/a11/final_closeout_v2.py')['sha256']
    assert digest(HANDOFF) == digest(DESKTOP), 'Desktop must match repository handoff'
    sources = ('final_closeout_v1.py', 'final_closeout_host_v1.py', 'test_final_closeout_v1.py',
               'final_closeout_v2.py', 'final_closeout_host_v2.py', 'test_final_closeout_v2.py',
               'final_closeout_readback_v1.py', 'audit_final_closeout_v1.py', 'seal_final_closeout_v1.py')
    for name in sources:
        source = ROOT / 'platform/qwen35/a11' / name
        ast.parse(source.read_text(encoding='utf-8'))
        copy_new(source, EV / 'source_snapshot' / name)
    for name in ('docs/PROJECT_STATUS.json', 'docs/status/A.md', 'docs/DECISIONS.md',
                 'docs/DESIGN_GAP.md', 'docs/TEST_MATRIX.md', 'docs/AI_ASSISTANCE.md',
                 'docs/handoffs/A11_CROSS_CHAT_HANDOFF_20261023.md'):
        copy_new(ROOT / name, EV / 'governance_snapshot' / name)
    current = json.loads((ROOT / 'docs/PROJECT_STATUS.json').read_bytes())['a11_final_closeout_20261023']
    assert current['status'] == audit['status'] and current['locks_held'] == 0
    prior = ROOT / 'evidence/mlp_board_A/20261023-cleanup-board-v3/execute_02/receipt.json'
    assert json.loads(prior.read_bytes())['exit_code'] == 4294967295
    copy_new(prior, EV / 'prior_supervisor_transport_receipt.json')
    # Recheck the historical immutable snapshots without changing any of them.
    for name, count in audit['old_seals_verified'].items():
        entries = json.loads((ROOT / name).read_bytes())['files']
        assert len(entries) == count
        for relative, entry in entries.items():
            assert digest(ROOT / relative) == entry, relative
    files = {}
    for path in sorted(EV.rglob('*')):
        if not path.is_file() or path.name in ('SEAL.json', 'seal_01.json'):
            continue
        assert not path.is_symlink(), str(path)
        files[path.relative_to(ROOT).as_posix()] = digest(path)
    seal = dict(status='SEALED_PASS_CLOSEOUT_ONLY_NOT_A11', A11='NOT_PASSED', A12='NOT_ELIGIBLE',
                files=files, desktop_document=dict(path=str(DESKTOP), **digest(DESKTOP)),
                repository_handoff=str(HANDOFF), board_contact=False,
                excluded=['SEAL.json (self)', 'seal_01.json (live recorder, kept outside seal)'])
    with (EV / 'SEAL.json').open('x', encoding='utf-8') as stream:
        json.dump(seal, stream, ensure_ascii=False, indent=2)
    # Immediate independent byte comparison after serialization, not just an index count.
    saved = json.loads((EV / 'SEAL.json').read_bytes())
    for name, entry in saved['files'].items():
        assert digest(ROOT / name) == entry, name
    print(json.dumps(dict(status=seal['status'], sealed_files=len(files),
                         desktop=str(DESKTOP), handoff_sha256=digest(DESKTOP)['sha256'],
                         board_contact=False), ensure_ascii=False))


if __name__ == '__main__':
    main()
