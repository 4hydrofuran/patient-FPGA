"""Final docs/source snapshot and content seal; no board operations."""
import ast,json,shutil,subprocess
from common import ROOT,sha,save
from step09_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    for name in ('contracts_01','config_01','pc_matrix_01','supervisor_pc_01','permission_pc_01','boundary_pc_01','policy_pc_01','app_state_pc_02','audit_short_01','audit_context_01','lifecycle_short_01','lifecycle_context_01','closeout_01','contracts_final','config_final','static_final'):
        assert j(OUT/(name+'.json'))['exit_code']==0,name
    status=j(ROOT/'docs/PROJECT_STATUS.json');before=j(OUT/'before/docs/PROJECT_STATUS.json')
    for key,value in before.items():
        if key not in ('stage','stage_status'):assert status[key]==value,key
    assert status['a12_step09_state_cancel_20261024']==j(OUT/'SUMMARY.json')
    for variant in ('short','context'):
        folder=OUT/variant
        for name in ('stage_01','launch_01','status_final','readback_01','delayed_01','monitor_01'):assert j(folder/name/'receipt.json')['exit_code']==0,(variant,name)
        for name in ('upload_01','download_01'):assert j(folder/(name+'.json'))['exit_code']==0
        for row in j(folder/'bundle-v1/manifest.json')['files']:
            p=folder/'bundle-v1'/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
        expected=OUT/'short-manager-source.py' if variant=='short' else ROOT/'platform/qwen35/a12/step09_manager.py'
        assert sha(folder/'bundle-v1/control/step09_manager.py')==sha(expected)
        assert sha(folder/'readback-v1.tar.gz')==j(folder/'readback_01/stdout.txt')['package']['sha256']
    after=OUT/'after';after.mkdir()
    docs=('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md','docs/handoffs/A_A12_STEP09_COMPLETE_20261024.md')
    for name in docs:
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source';source.mkdir()
    paths=list((ROOT/'platform/qwen35/a12').glob('step09*.py'))
    paths += [ROOT/'platform/qwen35/a12'/n for n in ('common.py','supervisor.py','step07_supervisor.py','window_closeout_v2.py','step08_health.py','capacity_policy.py','step08_transport.py','step06_preflight.py','step08_audit.py')]
    for p in paths:
        ast.parse(p.read_text(encoding='utf-8'),str(p));shutil.copyfile(p,source/p.name)
    shutil.copyfile(ROOT/'system_qwen35/app/default_e2e/test_policy.py',source/'app_test_policy.py')
    for argv,name in ((['git','status','--short'],'worktree-status.txt'),(['git','diff','--stat'],'worktree-diff-stat.txt')):
        r=subprocess.run(argv,cwd=ROOT,capture_output=True);assert r.returncode==0
        with (OUT/name).open('xb') as f:f.write(r.stdout)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_TASK09_STATE_CANCEL_BOARD_WITH_LIMITATIONS',files=files,prior_seals=j(OUT/'HISTORICAL_PRESERVATION.json'),excluded=['SEAL.json','external receipt']))
    result=dict(status='SEALED_A12_STEP09_STATE_CANCEL_BOARD_WITH_LIMITATIONS',files=len(files),seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),exit_code=0,prior_files_preserved=16202,real_calls=j(OUT/'SUMMARY.json')['real_calls'],next_step='10_NOT_STARTED',default_FPGA_enabled=False,physical_peak_bytes=None,speedup=None)
    save(OUT.parent/'20261024-step09-v1-receipt.json',result);print(json.dumps(result),flush=True)
