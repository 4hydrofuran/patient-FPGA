"""Final task10 evidence/source/docs seal; no board operations or default activation."""
import ast,json,shutil,subprocess
from common import ROOT,sha,save
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))
if __name__=='__main__':
    for name in ('contracts_01','config_01','sources_01','scope_01','controllers_01','controller_revision_01',
                 'journal_guard_01','build_run_01','build_run_02','pc_native_02','pc_control_01',
                 'pc_supervisor_01','pc_journal_01','historical_01','build_capture_01','pc_artifacts_01',
                 'audit_baseline_01','audit_optimized_01','lifecycle_baseline_01','lifecycle_optimized_01',
                 'decide_01','closeout_01','findings_01','contracts_final','config_final','static_final'):
        assert j(OUT/(name+'.json'))['exit_code']==0,name
    assert j(OUT/'pc_native_01.json')['exit_code']==1
    assert j(OUT/'health_micro_01/receipt.json')['exit_code']==0
    before=j(OUT/'before/docs/PROJECT_STATUS.json');status=j(ROOT/'docs/PROJECT_STATUS.json')
    for key,value in before.items():
        if key not in ('stage','stage_status'):assert status[key]==value,key
    assert status['a12_step10_performance_20261024']==j(OUT/'SUMMARY.json')
    for variant in ('baseline','optimized'):
        folder=OUT/variant
        for name in ('stage_01','launch_01','status_final','readback_01','delayed_01','monitor_01'):
            assert j(folder/name/'receipt.json')['exit_code']==0,(variant,name)
        for name in ('upload_01','download_01'):assert j(folder/(name+'.json'))['exit_code']==0
        for row in j(folder/'bundle-v1/manifest.json')['files']:
            p=folder/'bundle-v1'/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],p
        assert sha(folder/'bundle-v1/control/step10_manager.py')==sha(ROOT/'platform/qwen35/a12/step10_manager.py')
        assert sha(folder/'readback-v1.tar.gz')==j(folder/'readback_01/stdout.txt')['package']['sha256']
    for name,row in j(OUT/'BUILD-v2.json')['files'].items():
        p=OUT/'arm-bin-v2'/name;assert sha(p)==row['sha256']
    after=OUT/'after';after.mkdir()
    docs=('docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
          'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md',
          'docs/handoffs/A_A12_STEP10_COMPLETE_20261024.md','runtime/qwen35_w4a8/a12/PERFORMANCE_CANDIDATE.json')
    for name in docs:
        p=after/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,p)
    source=OUT/'source';source.mkdir()
    paths=list((ROOT/'platform/qwen35/a12').glob('step10*.py'))
    paths+=list((ROOT/'platform/qwen35/a12').glob('step10*.sh'))
    paths += [ROOT/'platform/qwen35/a12'/n for n in ('common.py','supervisor.py','step07_supervisor.py',
             'window_closeout_v2.py','step08_health.py','capacity_policy.py','step08_transport.py',
             'step06_preflight.py','step08_audit.py','step09_lifecycle_supplement.py')]
    for p in paths:
        if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'),str(p))
        shutil.copyfile(p,source/p.name)
    for name in ('runtime/qwen35_w4a8/cpu_backend.cpp','runtime/qwen35_w4a8/tiled_simd.hpp','quant/reference/w4a8.cpp','quant/reference/w4a8.hpp','platform/qwen35/a12/CMakeLists.txt'):
        shutil.copyfile(ROOT/name,source/name.replace('/','__'))
    for argv,name in ((['git','status','--short'],'worktree-status.txt'),(['git','diff','--stat'],'worktree-diff-stat.txt')):
        r=subprocess.run(argv,cwd=ROOT,capture_output=True);assert r.returncode==0
        with (OUT/name).open('xb') as f:f.write(r.stdout)
    files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(OUT.rglob('*')) if p.is_file()}
    save(OUT/'SEAL.json',dict(status='SEALED_TASK10_FAIR_PERFORMANCE_WITH_LIMITATIONS',files=files,
         prior_seals=j(OUT/'HISTORICAL_PRESERVATION.json'),excluded=['SEAL.json','external receipt']))
    result=dict(status='SEALED_A12_STEP10_PERFORMANCE_TASK11_PENDING',files=len(files),
         seal=(OUT/'SEAL.json').relative_to(ROOT).as_posix(),sha256=sha(OUT/'SEAL.json'),exit_code=0,
         prior_files_preserved=24691,real_calls=j(OUT/'SUMMARY.json')['real_calls'],
         next_step='11_NOT_STARTED',default_FPGA_enabled=False)
    save(OUT.parent/'20261024-step10-v1-receipt.json',result);print(json.dumps(result),flush=True)
