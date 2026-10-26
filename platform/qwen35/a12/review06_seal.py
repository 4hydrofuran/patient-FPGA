"""Preserve all prior evidence, snapshot current sources/docs and seal failure review."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
from common import ROOT,sha,save
from review06_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    for n in ('contracts_final','config_final','audit_01','closeout_01','controller_repro_01'):
        assert j(OUT/(n+'.json'))['exit_code']==0,n
    current=j(ROOT/'docs/PROJECT_STATUS.json');old=j(OUT/'before/docs/PROJECT_STATUS.json')
    for k,v in old.items():
        if k not in ('stage','stage_status'):assert current[k]==v,k
    reviewed=current['a12_step06_failure_review_20261024']
    assert not reviewed['numeric_blocker_for_step08'] and not reviewed['capacity_blocker_for_step08']
    assert reviewed['step08']=='NOT_STARTED' and reviewed['model_kernel_submissions_this_review']==0
    for name in ('review06_manager.py','capacity_policy.py','window_capacity_only.py','review06_loadonly_supervisor.py'):
        folder='control' if name=='review06_manager.py' else 'platform/qwen35/a12'
        assert sha(ROOT/'platform/qwen35/a12'/name)==sha(OUT/'bundle-v1'/folder/name)
    preserved=[]
    for rel in ('evidence/mlp_board_A/20261023-compute-acceptance-v1','evidence/model_pl_A/20261023-preboard-v1',
                'evidence/model_pl_A/20261023-step06-v1','evidence/model_pl_A/20261023-step07-single-v1',
                'evidence/model_pl_A/20261024-step07-finalize-v1','evidence/model_pl_A/20261024-step07-mlp-v1'):
        p=ROOT/rel/'SEAL.json';m=j(p)
        for name,row in m['files'].items():
            q=ROOT/name;assert q.is_file() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256'],name
        row=dict(seal=p.relative_to(ROOT).as_posix(),files=len(m['files']),sha256=sha(p),status='ALL_BYTES_PRESERVED')
        preserved.append(row);print(json.dumps(row),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',preserved)
    after=OUT/'after';after.mkdir()
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
                 'docs/handoffs/A_A12_STEP06_FAILURE_REVIEW_COMPLETE_20261024.md'):
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source';source.mkdir()
    paths=list((ROOT/'platform/qwen35/a12').glob('review06_*.py'))
    paths += [ROOT/'platform/qwen35/a12'/n for n in ('capacity_policy.py','window_capacity_only.py','step06_preflight.py')]
    for p in paths:ast.parse(p.read_text(encoding='utf-8'),str(p));shutil.copyfile(p,source/p.name)
    for argv,name in ((['git','status','--short'],'worktree-status.txt'),(['git','diff','--stat'],'worktree-diff-stat.txt')):
        r=subprocess.run(argv,cwd=ROOT,capture_output=True);assert r.returncode==0
        with (OUT/name).open('xb') as f:f.write(r.stdout)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_TWO_FAILURE_REVIEW_NO_BLOCKER_CONTROLLED_STEP08',
       files=files,historical_preserved=preserved,excluded=['SEAL.json','external receipt']))
    receipt=dict(status='SEALED_PASS_STEP06_FAILURE_REVIEW',files=len(files),
       seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),
       argv=['D:/Python/Python314/python.exe','-B','platform/qwen35/a12/review06_seal.py'],exit_code=0,
       preserved_files=sum(p['files'] for p in preserved),reference_cases=17,
       actual_weight_loads=72,actual_BO_count=148,actual_BO_bytes=140591104,
       new_model_kernel_runs=0,step08='NOT_STARTED',old_failures='PRESERVED',
       next_step='FRESH_CONTROLLED_STEP08_WINDOW_ELIGIBLE_AFTER_LIVE_GATES')
    save(OUT.parent/'20261024-step06-review-v1-receipt.json',receipt)
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
