"""Verify all earlier sealed bytes; snapshot source/governance and seal task07 MLP."""
import ast
import json
from pathlib import Path
import shutil
import subprocess
from common import ROOT,sha,save
from step07_mlp_prepare import OUT

def j(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    for name in ('contracts_final','config_final','audit_01','final_check_01','closeout_01'):
        assert j(OUT/(name+'.json'))['exit_code']==0
    status=j(ROOT/'docs/PROJECT_STATUS.json');old=j(OUT/'before/docs/PROJECT_STATUS.json')
    for k,v in old.items():
        if k not in ('stage','stage_status'):assert status[k]==v,k
    assert status['a12_step07_mlp_20261024']['task07']=='COMPLETE_WITH_DOCUMENTED_DOMAIN_LIMITS'
    assert status['a12_step07_mlp_20261024']['task08']=='NOT_STARTED'
    preserved=[]
    for folder in ('evidence/mlp_board_A/20261023-compute-acceptance-v1','evidence/model_pl_A/20261023-preboard-v1',
                   'evidence/model_pl_A/20261023-step06-v1','evidence/model_pl_A/20261023-step07-single-v1',
                   'evidence/model_pl_A/20261024-step07-finalize-v1'):
        p=ROOT/folder/'SEAL.json';m=j(p)
        for name,row in m['files'].items():
            q=ROOT/name;assert q.is_file() and q.stat().st_size==row['bytes'] and sha(q)==row['sha256'],name
        preserved.append(dict(path=p.relative_to(ROOT).as_posix(),files=len(m['files']),sha256=sha(p),status='ALL_BYTES_PRESERVED'))
        print(json.dumps(preserved[-1]),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',preserved)
    after=OUT/'after';after.mkdir()
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
                 'docs/handoffs/A_A12_STEP07_MLP_COMPLETE_20261024.md'):
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source';source.mkdir()
    for p in (ROOT/'platform/qwen35/a12').glob('step07_mlp_*.py'):
        ast.parse(p.read_text(encoding='utf-8'),str(p));shutil.copyfile(p,source/p.name)
    for name in ('window_closeout_v2.py','step07_finalize_policy.py','step07_supervisor.py','step06_preflight.py'):
        shutil.copyfile(ROOT/'platform/qwen35/a12'/name,source/name)
    build=j(OUT.parent/'20261023-step07-single-v1/BUILD.json')
    dependency=dict(native_build_manifest=build,native_build_manifest_sha256=sha(OUT.parent/'20261023-step07-single-v1/BUILD.json'),
       pc_window_tests=j(OUT.parent/'20261024-step07-finalize-v1/WINDOW_V2_PC_FINAL.json'),
       old_supervisor_protocol=j(OUT.parent/'20261023-step07-single-v1/PROTOCOL_REGRESSION.json'),
       math_and_native_changed=False,scope_change_only_plus_closeout_v2=True)
    save(OUT/'DEPENDENCIES.json',dependency)
    for cmd,name in ((['git','status','--short'],'worktree-status.txt'),(['git','diff','--stat'],'worktree-diff-stat.txt')):
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True);assert r.returncode==0
        with (OUT/name).open('xb') as f:f.write(r.stdout)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_PASS_TASK07_SINGLE_MLP_BOARD_NORMAL_CLOSEOUT',files=files,
       historical_preserved=preserved,excluded=['SEAL.json','external receipt']))
    receipt=dict(status='SEALED_PASS_A12_STEP07_SINGLE_MLP_BOARD',files=len(files),
       seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),
       argv=['D:/Python/Python314/python.exe','-B','platform/qwen35/a12/step07_mlp_seal.py'],exit_code=0,
       hardware_calls=9,manager_exit_code=0,task08='NOT_STARTED',task06_failures='UNCHANGED_DEFERRED_BY_USER')
    save(OUT.parent/'20261024-step07-mlp-v1-receipt.json',receipt)
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':main()
