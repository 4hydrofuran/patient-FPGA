"""Use audited baseline costs to enable only the pre-reviewed, same-semantics candidate."""
import json
from common import save
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))
if __name__=='__main__':
    assert j(OUT/'BASELINE_AUDIT.json')['status']=='PASS_BOARD_TASK10_BASELINE'
    assert j(OUT/'BASELINE_LIFECYCLE_SUPPLEMENT.json')['status']=='PASS_EXACT_ARCHIVED_LEASE_AND_COMPLETE_FINAL_SCAN'
    rows=[]
    for name in ('short_profile','natural_profile'):
        p=OUT/'baseline/readback-v1/run-v1/s2'/name
        result=j(p/'result.json');client=j(p/'client-timing.json');prof=result['request_profile']
        wall=prof['native_request_wall_ms'];phases=prof['pl_profile']['phases'].values()
        report=sum(r['completion_report_wall_ms'] for r in phases)
        permission=sum(r['backend']['a12_permission_wait_ms'] for r in phases)
        service=sum(r['backend']['service_ms'] for r in phases)
        manager=client['permission_metrics_delta']
        rows.append(dict(id=name,native_wall_ms=wall,completion_report_ms=report,completion_report_fraction=report/wall,
            permission_wait_ms=permission,permission_wait_fraction=permission/wall,backend_service_ms=service,
            health_check_ms=manager['health_check_ms'],durable_permit_record_ms=manager['durable_permission_record_ms'],
            owner_check_ms=manager['owner_check_ms']))
    material=any(r['completion_report_fraction']>=.05 or r['permission_wait_fraction']>=.10 for r in rows)
    assert material,'No measured material redundant-report/control cost; do not activate an unsupported optimization'
    decision=dict(status='BASELINE_AUDITED_MATERIAL_COST_IDENTIFIED',apply_compact_completion_and_journal=True,
        baseline=rows,fixes=['private completion reader returns the exact same validated last completion without serializing stable BO inventory',
            'retain every fresh per-permit health check and durable bound permission record; compact only repeated unchanged lifecycle health journal rows'],
        safety_proof=['31 control-double cases 1041 checks including compact/full completion equivalence',
            'native raw logits/state and on/off profile comparisons',
            'actual permission ordering/cancel/no-reuse/normal-close test',
            'actual health checks never skipped; rejected observations always durable'],
        preserves=['public ABI and numerical thresholds','received B hardware','all BO/lease/timeout/POISONED/restore rules'],
        activation='NEW_BOUNDED_WINDOW_ONLY_AFTER_DEFAULT_RESTORED',production_default=False)
    save(OUT/'FIX_DECISION.json',decision);print(json.dumps(decision,ensure_ascii=False,indent=2))
