"""Qualitative follow-on assessment, preserving the initial automated recommendation."""
import json
import os
from pathlib import Path

OUT=Path(__file__).resolve().parents[3]/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


if __name__=='__main__':
    path=OUT/'HOTSPOTS.json';before=path.read_bytes();data=json.loads(before)
    with (OUT/'HOTSPOTS.initial-assessment.json').open('xb') as stream:stream.write(before)
    phase=data['phases']['prefill'];categories={r['category']:r['wall_ms']/1000 for r in phase['exclusive_categories']}
    roles={}
    for row in phase['alternate_role_shape_view']:
        if row['category']=='matrix':roles[row['role']]=roles.get(row['role'],0)+row['wall_ms']/1000
    assessment=dict(status='DIAGNOSIS_SUFFICIENT_TASK01_COMPLETE',measured_prefill_matrix_s=categories['matrix'],measured_prefill_data_movement_s=categories['data_movement'],
        alternate_matrix_role_view_s=roles,priority='02 fresh health/owner/record representation work while preserving persistence; largest next CPU compute candidate is 05 linear-attention projections',
        task03='Peer still owns its independent candidate; integrate and measure separately. Entire movement category is not an estimate of reducible CONCAT time.',
        recoverable_savings_s=None,optimization_implemented=False,observation='Do not add MLP inclusive to nested permission/service; do not add role view to exclusive category view.')
    with (OUT/'NEXT_STEPS.json').open('x',encoding='utf-8') as stream:json.dump(assessment,stream,indent=2);stream.write('\n')
    data['recommended_next']=assessment['priority'];data['followon_assessment']='NEXT_STEPS.json; initial automated recommendation preserved as HOTSPOTS.initial-assessment.json'
    assert {k:v for k,v in data.items() if k not in ('recommended_next','followon_assessment')}=={k:v for k,v in json.loads(before).items() if k!='recommended_next'}
    temp=path.with_name('HOTSPOTS.assessment.tmp')
    with temp.open('x',encoding='utf-8') as stream:json.dump(data,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    assert path.read_bytes()==before
    os.replace(temp,path)
    print(json.dumps(assessment))
