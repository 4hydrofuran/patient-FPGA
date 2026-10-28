"""Seal stopped experiment; explicitly preserves a live retained owner as NOT_COMPLETE."""
import ast
import json
from pathlib import Path
import shutil
from common import ROOT,sha,save
from step07_protocol import OUT


def main():
    for n in ('contracts_final','config_final','audit_03','closeout_01'):
        assert json.loads((OUT/(n+'.json')).read_text(encoding='utf-8'))['exit_code']==0
    audit=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    current=status['a12_step07_single_20261024']
    assert current['step07_overall']=='PARTIAL_NOT_COMPLETE' and current['lifecycle']['manager_exit_code'] is None
    old=json.loads((OUT/'before/docs/PROJECT_STATUS.json').read_text(encoding='utf-8'))
    for k,v in old.items():
        if k not in ('stage','stage_status'):assert status[k]==v,k
    assert audit['actual_calls']==3 and audit['hardware_global_count'] is None
    assert all(x['bit_exact'] for x in audit['logits'].values()) and audit['hybrid_state']['bit_exact']
    for p in (ROOT/'platform/qwen35/a12').glob('step07_*.py'):ast.parse(p.read_text(encoding='utf-8'),str(p))
    # Ensure uploaded controls match the exact current source, never conceal a live patch.
    assert (OUT/'bundle-v1/control/step07_manager.py').read_bytes()==(ROOT/'platform/qwen35/a12/step07_manager.py').read_bytes()
    plan=(ROOT/'docs/A12_STEP_PLAN_20261023.md').read_text(encoding='utf-8')
    s=plan[plan.index('### 07｜'):plan.index('### 08｜')]
    assert s.count('- [x]')==1 and 'STOPPED' in s
    preserved=[]
    for folder in ('evidence/mlp_board_A/20261023-compute-acceptance-v1',
                   'evidence/model_pl_A/20261023-preboard-v1','evidence/model_pl_A/20261023-step06-v1'):
        p=ROOT/folder/'SEAL.json';seal=json.loads(p.read_text(encoding='utf-8'))
        failed=[]
        for name,row in seal['files'].items():
            f=ROOT/name
            if not f.is_file() or f.stat().st_size!=row['bytes'] or sha(f)!=row['sha256']:failed.append(name)
        assert not failed,failed
        preserved.append(dict(path=p.relative_to(ROOT).as_posix(),files=len(seal['files']),sha256=sha(p),status='ALL_BYTES_PRESERVED'))
        print(json.dumps(preserved[-1]),flush=True)
    save(OUT/'HISTORICAL_PRESERVATION.json',preserved)
    after=OUT/'after';after.mkdir()
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
                 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
                 'docs/handoffs/A_A12_STEP07_SINGLE_STOPPED_20261024.md'):
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source-tools';source.mkdir()
    for p in (ROOT/'platform/qwen35/a12').glob('step07_*'):
        if p.is_file():shutil.copyfile(p,source/p.name)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))
           for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_SINGLE_PROJECTION_NUMERIC_CONSUMER_PASS_LIFECYCLE_STOPPED_OWNER_RETAINED',
                            files=files,excluded=['SEAL.json','external receipt'],historical_preserved=preserved))
    receipt=dict(status='SEALED_STOPPED_NOT_OVERALL_PASS',seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),
        sha256=sha(OUT/'SEAL.json'),files=len(files),bytes=sum(x['bytes'] for x in files.values()),
        argv=['D:/Python/Python314/python.exe','-B','platform/qwen35/a12/step07_seal.py'],exit_code=0,
        active_lease_retained=True,manager_exit_code=None)
    save(OUT.parent/'20261023-step07-single-v1-receipt.json',receipt)
    print(json.dumps(receipt),flush=True)


if __name__=='__main__':main()
