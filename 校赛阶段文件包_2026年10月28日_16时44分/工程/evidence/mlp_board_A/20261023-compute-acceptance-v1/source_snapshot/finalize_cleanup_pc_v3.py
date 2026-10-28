"""Offline final checks/seal. Does not run any candidate action."""
import ast
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3'


def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    receipts=['contracts_01.json','config_01.json','tests_01.json','tests_02.json','tests_03.json','tests_04.json','route_01.json','package_01.json']
    for name in receipts:assert json.loads((EV/name).read_bytes())['exit_code']==0,name
    assert 'Ran 30 tests' in json.loads((EV/'tests_04.json').read_bytes())['stderr']
    package=json.loads((EV/'PACKAGE.json').read_bytes());candidate=EV/'candidate/cleanup-v3-20261023'
    manifest=json.loads((candidate/'candidate.json').read_bytes())
    assert digest(candidate/'candidate.json')==package['candidate_manifest_sha256']
    for name,entry in manifest['files'].items():
        p=candidate/name;assert p.stat().st_size==entry['bytes'] and digest(p)==entry['sha256']
        if name.endswith('.py'):assert digest(ROOT/'platform/qwen35/a11'/name)==entry['sha256']
    archive=ROOT/package['archive']['path'];assert digest(archive)==package['archive']['sha256']
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar.getmembers():
            assert member.isfile() and len(Path(member.name).parts)==2 and Path(member.name).parts[0]=='cleanup-v3-20261023'
            raw=tar.extractfile(member).read()
            assert hashlib.sha256(raw).hexdigest()==digest(candidate/Path(member.name).name)
    sources=['cleanup_board_v3.py','cleanup_controller_v3.py','cleanup_control_v3.py','cleanup_recovery_plan_v3.py',
             'test_cleanup_v3.py','package_cleanup_v3.py','finalize_cleanup_pc_v3.py']
    snapshot=EV/'source_snapshot';snapshot.mkdir(exist_ok=False)
    for name in sources:
        src=ROOT/'platform/qwen35/a11'/name;ast.parse(src.read_text());shutil.copyfile(src,snapshot/name)
    documents=['docs/A11_CLEANUP_RECOVERY_PLAN_20261023.md','docs/PROJECT_STATUS.json','docs/status/A.md',
        'docs/DECISIONS.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md']
    for name in documents:
        dst=EV/'governance_snapshot'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dst)
    status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_bytes())['a11_cleanup_pc_fix_v3_20261023']
    assert status['tests']==30 and status['board_connections']==status['board_mutations']==0 and status['A11']=='NOT_PASSED'
    audit=dict(status='PC_PASS_BOARD_NOT_TESTED',tests=30,board_connections=0,board_mutations=0,
        candidate_sources_match_tests_and_archive=True,source_files=sources,plan=documents[0],
        old_seals_verified=package['prior_seals_verified'],A11='NOT_PASSED',A12='NOT_ELIGIBLE')
    with (EV/'AUDIT.json').open('x') as f:json.dump(audit,f,indent=2)
    entries={}
    for p in EV.rglob('*'):
        if p.is_file() and p.name not in ('SEAL.json','finalize_01.json'):
            entries[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=digest(p))
    with (EV/'SEAL.json').open('x') as f:json.dump(dict(status='PC_ONLY_SEALED',files=entries),f,indent=2)
    print(json.dumps(dict(status=audit['status'],sealed_files=len(entries),board_actions=0)))


if __name__=='__main__':main()
