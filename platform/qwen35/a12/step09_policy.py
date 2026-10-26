"""Actual application reject/clarify routes and explicit no-hardware registry."""
import json,sys
from common import ROOT,save
from step09_common import OUT
sys.path.insert(0,str(ROOT))
from system_qwen35.app.domain import load_case,Transcript
from system_qwen35.app.planning import plan
from system_qwen35.app.checking import check
from system_qwen35.app.default_e2e.policy import registry,HardwareUnavailable

if __name__=='__main__':
    questions=json.loads((ROOT/'eval/qwen35/a02/dev/questions-v2.json').read_text(encoding='utf-8'))
    frozen=json.loads((ROOT/'evidence/model_pl_A/20261024-step08-v1/REQUESTS.json').read_text(encoding='utf-8'))
    templates={r['id']:r['text'] for r in frozen['policy_only']};rows=[]
    for q in questions:
        if q['id'] not in templates:continue
        p=plan(load_case(q['case_id']),Transcript.parse(dict(request_id=q['id'],text=q['question'],source='typed',final=True)),[])
        assert p.route==q['expected_route'] and p.route in ('refuse','clarify')
        v=check(p,templates[q['id']]);assert v['status']=='pass'
        rows.append(dict(id=q['id'],route=p.route,text=templates[q['id']],checker=v,model_calls=0,hardware_submissions=0))
    assert len(rows)==7
    try:registry('fpga_required')
    except HardwareUnavailable as e:missing=str(e)
    else:raise AssertionError('missing HW accepted')
    cpu=registry('cpu_same_math');assert cpu['fallback']=='disabled' and cpu['actual_backend']=='CPU_REFERENCE'
    save(OUT/'POLICY_PC.json',dict(status='PASS_7_POLICY_ROUTES_NO_MODEL_NO_HW',rows=rows,missing_hardware_rejection=missing,explicit_CPU=cpu,BOARD_policy_templates='NOT_EXECUTED_NO_HARDWARE_PATH'))
    print('PASS_7_POLICY_ROUTES_AND_FAIL_CLOSED_REGISTRY')
