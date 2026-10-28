"""Final preservation and evidence seal, no hardware/network access."""
import json
from pathlib import Path
import shutil
from common import ROOT,EVIDENCE,sha,save


def main():
    baseline=json.loads((EVIDENCE/'BASELINE.json').read_text())
    preserved={}
    for name,expected in baseline['before'].items():
        if name.startswith('runtime/qwen35_w4a8/') or name.startswith('system_qwen35/app/') or name in ('modules/linear_A/manifest.json','config/qwen35/selection.json','AGENTS.md'):
            assert sha(ROOT/name)==expected,'existing protected source changed: '+name
            preserved[name]=expected
    seal=json.loads((ROOT/'evidence/mlp_board_A/20261023-compute-acceptance-v1/SEAL.json').read_text())
    for name,row in seal['files'].items():assert sha(ROOT/name)==row['sha256'],'A11 seal changed: '+name
    queue_files=[]
    for name in ('pc_build_01','pc_build_02','pc_build_03','pc_build_04','arm_build_01','arm_build_02'):
        outer=json.loads((EVIDENCE/(name+'.json')).read_text());row=json.loads(outer['stdout'])
        source=Path(row['cwd'])
        assert source.parent==Path('/home/member-a/kv260-build/ra02-coordinator/work')
        for filename in ('stdout.txt','stderr.txt'):
            target=EVIDENCE/'queue_logs'/row['job']/filename;target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():raise FileExistsError(target)
            shutil.copyfile(source/filename,target);queue_files.append(str(target.relative_to(ROOT)))
    final_logs=['contracts_final_01','config_final_01','package_selftest_01','bundle_tests_01','session_01']
    for name in final_logs:assert json.loads((EVIDENCE/(name+'.json')).read_text())['exit_code']==0
    status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text())
    assert status['stage']=='A12' and status['a11_acceptance_20261023']['A11']=='PASS_WITH_LIMITATIONS'
    assert status['a12_preboard_20261023']['BOARD']=='NOT_TESTED'
    plan=(ROOT/'docs/A12_STEP_PLAN_20261023.md').read_text()
    before,after=plan.split('### 06｜',1)
    assert '- [ ]' not in before[before.index('### 01｜'):] and '- [x]' not in after
    current=(ROOT/'runtime/qwen35_w4a8/a12/route.cpp').read_bytes()
    assert current==(EVIDENCE/'source-v4/route.cpp').read_bytes()
    save(EVIDENCE/'FINAL_CHECK.json',dict(status='PASS_PC_FINAL_CONSISTENCY',
        A11_sealed_files_unchanged=len(seal['files']),old_sources_and_defaults_unchanged=preserved,
        saved_queue_logs=queue_files,source_v4_matches_final=True,
        A12='01_05_PC_CROSS_BUILD_COMPLETE_BOARD_PENDING',BOARD='NOT_TESTED',
        board_connected=False,committed=False,pushed=False))
    files={}
    scopes=[EVIDENCE,ROOT/'platform/qwen35/a12',ROOT/'runtime/qwen35_w4a8/a12',
            ROOT/'release/a12_preboard_20261023_v1']
    for scope in scopes:
        for p in scope.rglob('*'):
            if not p.is_file() or p.suffix=='.pyc' or '__pycache__' in p.parts:continue
            if p.name in ('SEAL.json','final_check_01.json'):continue
            files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=sha(p))
    for name in ('system_qwen35/app/native_pl.py','docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md',
                 'docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
                 'docs/handoffs/A_A12_PREBOARD_01_05_20261023.md'):
        original=ROOT/name;target=EVIDENCE/'governance_snapshot'/name
        target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        files[target.relative_to(ROOT).as_posix()]=dict(bytes=target.stat().st_size,sha256=sha(target))
    save(EVIDENCE/'SEAL.json',dict(status='SEALED_A12_PREBOARD_PC_CROSS_BUILD_NOT_BOARD',files=files,
        self_and_running_receipt_excluded=['SEAL.json','final_check_01.json']))
    print(json.dumps(dict(status='PASS_PC_FINAL_CONSISTENCY',sealed_files=len(files),old_A11_unchanged=len(seal['files']))))


if __name__=='__main__':main()
