"""Final local evidence/docs/source consistency; no new board calculation."""
import ast,json
from common import ROOT,sha
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))
if __name__=='__main__':
    paths=list((ROOT/'platform/qwen35/a12').glob('step10*.py'))
    for p in paths:ast.parse(p.read_text(encoding='utf-8'),str(p))
    summary=j(OUT/'SUMMARY.json');status=j(ROOT/'docs/PROJECT_STATUS.json')
    assert summary['status']=='PASS_A12_STEP10_PERFORMANCE_WITH_LIMITATIONS_TASK11_PENDING'
    assert status['a12_step10_performance_20261024']==summary
    before=j(OUT/'before/docs/PROJECT_STATUS.json')
    for key,value in before.items():
        if key not in ('stage','stage_status'):assert status[key]==value,key
    assert summary['default_FPGA_enabled'] is False and summary['A12_final']=='NOT_COMPLETE_TASK11_PENDING'
    assert summary['physical_total_peak_bytes'] is None and summary['device_cycles'] is None and summary['AXI_measured_bytes'] is None
    assert j(OUT/'pc_native_01.json')['exit_code']==1 and j(OUT/'pc_native_02.json')['exit_code']==0
    assert summary['real_calls']==j(OUT/'BASELINE_AUDIT.json')['actual_calls']+j(OUT/'OPTIMIZED_AUDIT.json')['actual_calls']
    for variant in ('baseline','optimized'):
        audit=j(OUT/(variant.upper()+'_AUDIT.json'))
        for row in audit['rows']:
            root=OUT/variant/'readback-v1/run-v1'
            cpu=j(root/'s1'/row['id']/'result.json')
            pl=j(root/'s2'/row['id']/'result.json')
            assert cpu['request_profile']['cpu_counters']['run_count_delta']==row['calls']
            assert pl['request_profile']['cpu_counters']['run_count_delta']==0
    assert j(OUT/'BOTTLENECK_FINDINGS.json')['status']=='MEASURED_BOTTLENECKS_RANKED'
    micro=j(OUT/'health_micro_01/stdout.txt')
    final=j(OUT/'optimized/delayed_01/stdout.txt')
    assert all(r['kernel_sha256']==final['kernel_sha256'] for r in micro['rows'])
    candidate=j(ROOT/summary['performance_candidate'])
    assert candidate['default_enabled'] is False
    assert candidate['manifest_sha256']==sha(OUT/'optimized/bundle-v1/manifest.json')
    for name,pin in j(OUT/'FROZEN_CONTROLLERS.json')['files'].items():assert sha(ROOT/'platform/qwen35/a12'/name)==pin
    plan=(ROOT/'docs/A12_STEP_PLAN_20261023.md').read_text(encoding='utf-8')
    section=plan.split('### 10｜',1)[1].split('### 11｜',1)[0]
    assert '- [x]' in section and '- [ ]' not in section
    assert '- [ ]' in plan.split('### 11｜',1)[1]
    print(json.dumps(dict(status='PASS_TASK10_LOCAL_SOURCE_REPORT_CONSISTENCY',sources=len(paths))))
