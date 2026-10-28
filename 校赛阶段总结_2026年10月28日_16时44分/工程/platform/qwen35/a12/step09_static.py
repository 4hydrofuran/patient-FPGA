"""Final local source/report consistency checks; no board operations."""
import ast
import json
from common import ROOT
from step09_common import OUT


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


if __name__ == '__main__':
    sources = list((ROOT / 'platform/qwen35/a12').glob('step09*.py'))
    sources.append(ROOT / 'system_qwen35/app/default_e2e/test_policy.py')
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8'), str(path))
    summary = read_json(OUT / 'SUMMARY.json')
    assert summary['status'] == 'PASS_A12_STEP09_STATE_CANCEL_BOARD_WITH_LIMITATIONS'
    assert summary['real_calls'] == 24192
    assert summary['short_real_calls'] == 5400
    assert summary['context_real_calls'] == 18792
    assert summary['diagnostic_real_consumed_outputs'] == 1656
    assert summary['default_FPGA_enabled'] is False
    assert summary['board_speedup'] is None
    assert summary['R0_full_prefill_latency_risk'] is True
    assert summary['extension2048'] == 'NOT_TESTED'
    assert summary['BOARD_inflight_timeout_poison_removal'] == 'NOT_TESTED'
    assert summary['next_step'] == '10_NOT_STARTED'
    assert summary['A12_final'] == 'NOT_COMPLETE_TASK10_11_PENDING'
    for case in read_json(OUT / 'SHORT_AUDIT.json')['cases']:
        for row in case.get('logits', {}).values():
            assert row['failures'] == 0 and row['max_abs'] == 0
        if case.get('logits'):
            run = OUT / 'short/readback-v1/run-v1'
            for name in case['logits']:
                assert (run / 's1' / case['id'] / 'diag' / name).read_bytes() == (
                    run / 's2' / case['id'] / 'diag' / name).read_bytes()
    status = read_json(ROOT / 'docs/PROJECT_STATUS.json')
    assert status['a12_step09_state_cancel_20261024'] == summary
    before = read_json(OUT / 'before/docs/PROJECT_STATUS.json')
    for key, value in before.items():
        if key not in ('stage', 'stage_status'):
            assert status[key] == value, key
    plan = (ROOT / 'docs/A12_STEP_PLAN_20261023.md').read_text(encoding='utf-8')
    task09 = plan.split('### 09｜', 1)[1].split('### 10｜', 1)[0]
    task10 = plan.split('### 10｜', 1)[1].split('### 11｜', 1)[0]
    assert '- [ ]' not in task09 and '- [x]' in task09
    assert '- [ ]' in task10 and '- [x]' not in task10
    failures = read_json(OUT / 'FAILURES.json')
    assert failures['unexpected_execution_failures'][0]['initial_exit_code'] == 1
    assert failures['unexpected_execution_failures'][0]['rerun_exit_code'] == 0
    assert read_json(OUT / 'app_state_pc_01.json')['exit_code'] == 1
    assert read_json(OUT / 'app_state_pc_02.json')['exit_code'] == 0
    print(json.dumps({'status': 'PASS_LOCAL_SOURCE_AND_REPORT_CONSISTENCY',
                      'python_sources': len(sources), 'board_operations': 0}))
