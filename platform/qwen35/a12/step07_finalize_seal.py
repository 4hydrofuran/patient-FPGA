"""Verify unchanged historical evidence, snapshot current governance and seal recovery-only work."""
import ast
import json
from pathlib import Path
import shutil
from common import ROOT,sha,save

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


def main():
    for n in ('contracts_final','config_final','policy_pc_01','window_v2_pc_02','audit_02','closeout_01'):
        assert json.loads((OUT/(n+'.json')).read_text(encoding='utf-8'))['exit_code']==0
    status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    old=json.loads((OUT/'before/docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    for k,v in old.items():
        if k not in ('stage','stage_status'):assert status[k]==v,k
    current=status['a12_step07_finalize_20261024']
    assert current['new_computation']==0 and current['old_manager_exit']==-9 and current['finalizer_exit_code']==0
    assert not current['active_lease'] and not current['canonical_locks_held']
    assert current['step07_overall']=='PARTIAL_SINGLE_PROJECTION_ONLY_MLP_NOT_TESTED'
    for p in (ROOT/'platform/qwen35/a12').glob('step07_finalize_*.py'):ast.parse(p.read_text(encoding='utf-8'),str(p))
    v2=ROOT/'platform/qwen35/a12/window_closeout_v2.py';ast.parse(v2.read_text(encoding='utf-8'))
    tested=json.loads((OUT/'WINDOW_V2_PC_FINAL.json').read_text(encoding='utf-8'))
    assert tested['tested_source_sha256']==sha(v2)
    pins=json.loads((OUT/'SCRIPT_PINS.json').read_text(encoding='utf-8'))
    assert pins['policy_sha256']==sha(ROOT/'platform/qwen35/a12/step07_finalize_policy.py')
    assert pins['board_template_sha256']==sha(ROOT/'platform/qwen35/a12/step07_finalize_board.py')
    preserved=[]
    for folder in ('evidence/mlp_board_A/20261023-compute-acceptance-v1','evidence/model_pl_A/20261023-preboard-v1',
                   'evidence/model_pl_A/20261023-step06-v1','evidence/model_pl_A/20261023-step07-single-v1'):
        p=ROOT/folder/'SEAL.json';m=json.loads(p.read_text(encoding='utf-8'));bad=[]
        for name,row in m['files'].items():
            q=ROOT/name
            if not q.is_file() or q.stat().st_size!=row['bytes'] or sha(q)!=row['sha256']:bad.append(name)
        assert not bad,bad
        preserved.append(dict(path=p.relative_to(ROOT).as_posix(),files=len(m['files']),sha256=sha(p),status='ALL_BYTES_PRESERVED'))
        print(json.dumps(preserved[-1]),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',preserved)
    after=OUT/'after';after.mkdir()
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
                 'docs/handoffs/A_A12_STEP07_FINALIZE_COMPLETE_20261024.md'):
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source';source.mkdir()
    for p in (ROOT/'platform/qwen35/a12').glob('step07_finalize_*'):
        if p.is_file():shutil.copyfile(p,source/p.name)
    for p in (v2,ROOT/'platform/qwen35/a12/README_CLOSEOUT_V2.md'):shutil.copyfile(p,source/p.name)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_RECOVERY_FINALIZE_ONLY_OLD_ABNORMAL_EXIT_RETAINED_NO_NEW_COMPUTATION',
          files=files,historical_preserved=preserved,excluded=['SEAL.json','external receipt']))
    receipt=dict(status='SEALED_PASS_RECOVERY_FINALIZATION_ONLY',files=len(files),bytes=sum(v['bytes'] for v in files.values()),
       seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),
       argv=['D:/Python/Python314/python.exe','-B','platform/qwen35/a12/step07_finalize_seal.py'],exit_code=0,
       new_computation=0,old_manager_exit=-9,active_lease=False,canonical_locks_held=False)
    save(OUT.parent/'20261024-step07-finalize-v1-receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
