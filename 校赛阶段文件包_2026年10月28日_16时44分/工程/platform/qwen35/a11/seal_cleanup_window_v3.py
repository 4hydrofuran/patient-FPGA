"""PC-only closure of evidence, NOT closure of the board maintenance lease."""
import ast
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3'


def main():
    audit=json.loads((EV/'AUDIT.json').read_bytes())
    assert audit['status']=='DEFAULT_RESTORED_FINALIZATION_BLOCKED'
    for name in ('contracts_01.json','config_01.json','transport_tests_03.json','final_stop_tests_02.json','audit_02.json'):
        assert json.loads((EV/name).read_bytes())['exit_code']==0
    assert 'Ran 10 tests' in json.loads((EV/'transport_tests_03.json').read_bytes())['stderr']
    assert 'Ran 2 tests' in json.loads((EV/'final_stop_tests_02.json').read_bytes())['stderr']
    sources=('cleanup_window_v3_remote.py','cleanup_window_v3_host.py','test_cleanup_window_v3.py',
             'audit_cleanup_window_v3.py','test_cleanup_final_stop_v3.py','seal_cleanup_window_v3.py')
    for name in sources:
        p=ROOT/'platform/qwen35/a11'/name;ast.parse(p.read_text())
        target=EV/'source_snapshot'/name;target.parent.mkdir(exist_ok=True)
        assert not target.exists();shutil.copyfile(p,target)
    for name in ('docs/PROJECT_STATUS.json','docs/status/A.md','docs/DECISIONS.md','docs/DESIGN_GAP.md',
                 'docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md'):
        target=EV/'governance_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True)
        assert not target.exists();shutil.copyfile(ROOT/name,target)
    status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_bytes())['a11_cleanup_board_v3_20261023']
    assert status['status']==audit['status'] and status['A11']=='NOT_PASSED' and status['locks_and_active_lease_retained']
    old=ROOT/'evidence/mlp_board_A/20261023-recovery-continuation-v1/execute_01/host_receipt.json'
    assert json.loads(old.read_bytes())['exit_code']==4294967295
    shutil.copyfile(old,EV/'prior_waiter_host_receipt.json')
    files={}
    roots=(EV,ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3-readonly-01',
           ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3-readonly-02')
    for directory in roots:
        for p in directory.rglob('*'):
            if not p.is_file() or p.name in ('SEAL.json','seal_01.json') or EV/'execute_02' in p.parents:continue
            assert not p.is_symlink()
            files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest())
    with (EV/'SEAL.json').open('x') as f:
        json.dump(dict(status='SEALED_DEFAULT_RESTORED_FINALIZATION_BLOCKED',files=files,
            live_excluded=['evidence/mlp_board_A/20261023-cleanup-board-v3/execute_02/'],
            supervisor_still_running=True,A11='NOT_PASSED'),f,indent=2)
    print(json.dumps(dict(sealed_files=len(files),status=audit['status'],board_contact=False)))


if __name__=='__main__':main()
