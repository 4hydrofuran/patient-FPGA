"""Snapshot task08 provenance and docs, verify pins, then seal final evidence."""
import ast
import json
import shutil
import subprocess
from common import ROOT,sha,save
from step08_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    for name in ('contracts_final','config_final','closeout_01','audit_diagnostic_01','audit_generation_01','quality_01','static_final','static_final_04','powershell_parse_03'):
        assert j(OUT/(name+'.json'))['exit_code']==0,name
    status=j(ROOT/'docs/PROJECT_STATUS.json');old=j(OUT/'before/docs/PROJECT_STATUS.json')
    for key,value in old.items():
        if key not in ('stage','stage_status'):assert status[key]==value,key
    assert status['a12_step08_full_model_20261024']==j(OUT/'SUMMARY.json')
    for variant in ('diagnostic','generation'):
        folder=OUT/variant
        for receipt in ('stage_01','launch_01','status_final','readback_01','delayed_01'):
            assert j(folder/receipt/'receipt.json')['exit_code']==0
        for receipt in ('upload_01','download_01'):assert j(folder/(receipt+'.json'))['exit_code']==0
        manifest=j(folder/'bundle-v1/manifest.json')
        for row in manifest['files']:
            p=folder/'bundle-v1'/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
        assert sha(folder/'bundle-v1/control/step08_manager.py')==sha(ROOT/'platform/qwen35/a12/step08_manager.py')
        assert sha(folder/'readback-v1.tar.gz')==j(folder/'readback_01/stdout.txt')['package']['sha256']
    assert j(OUT/'generation/monitor_01/receipt.json')['exit_code']==0
    after=OUT/'after';after.mkdir()
    for name in ('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
        'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md','docs/handoffs/A_A12_STEP08_COMPLETE_20261024.md'):
        dest=after/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
    source=OUT/'source';source.mkdir()
    paths=list((ROOT/'platform/qwen35/a12').glob('step08*'))
    paths += [ROOT/'platform/qwen35/a12'/n for n in ('capacity_policy.py','window_closeout_v2.py','step07_supervisor.py','supervisor.py','step06_preflight.py')]
    paths += [ROOT/'platform/qwen35/a10/cold_boot_irq2_once.ps1']
    for p in paths:
        if not p.is_file():continue
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'),str(p))
        shutil.copyfile(p,source/p.name)
    for argv,name in ((['git','status','--short'],'worktree-status.txt'),(['git','diff','--stat'],'worktree-diff-stat.txt')):
        r=subprocess.run(argv,cwd=ROOT,capture_output=True);assert r.returncode==0
        with (OUT/name).open('xb') as f:f.write(r.stdout)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_TASK08_FULL_MODEL_BOARD_WITH_LIMITATIONS',files=files,
        prior_seals=j(OUT/'HISTORICAL_PRESERVATION.json'),excluded=['SEAL.json','external receipt']))
    result=dict(status='SEALED_A12_STEP08_FULL_MODEL_BOARD_WITH_LIMITATIONS',files=len(files),
        seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),exit_code=0,
        prior_files_preserved=sum(r['files'] for r in j(OUT/'HISTORICAL_PRESERVATION.json')),
        actual_diagnostic_calls=216,actual_generation_calls=j(OUT/'GENERATION_AUDIT.json')['actual_calls'],
        next_step='09_NOT_STARTED',default_FPGA_enabled=False,physical_peak_bytes=None,speedup=None)
    save(OUT.parent/'20261024-step08-v1-receipt.json',result)
    print(json.dumps(result),flush=True)
