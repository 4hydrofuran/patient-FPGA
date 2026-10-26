import json
from pathlib import Path
folder=Path(__file__).parent
def captured(name,needle):
    r=json.loads((folder/name).read_text(encoding='utf-8-sig'))
    return next(json.loads(line.strip()) for line in r['output'].splitlines() if line.strip().startswith('{') and needle in line)
attempt=captured('start2-uart.json','manager_pid')
scene=json.loads(captured('final-scene.json','exit_code')['stdout'])
result=dict(status='FAILED_PL_ACCEPTANCE_BEFORE_MODEL_REQUEST',task_started_utc='2026-10-26T10:14:25Z',
 completed_within_25_minutes=True,kernel_mismatch_resolved=True,kernel=scene['kernel'],boot_id=scene['boot_id'],
 normal_reboots=1,RAM_candidate_boots=1,flash=False,default_boot_files_changed=False,
 cause='Binding code incorrectly set spec.authorization_included=true; original workload policy requires that field false and separates compute authorization into the Owner review.',
 operator_binding_error=True,model_requests_sent=0,model_acceptance='NOT_PASSED',hardware_completion_count=None,
 manager_pid=2907,worker_pid=3039,resources_retained=True,safe_release=False,forced_signals=0,
 current_scene=scene,attempt=attempt,scope='Original ordinary R0/warm/hit baseline; new optimized candidate not executed')
with (folder/'RESULT.json').open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
status=folder.parents[2]/'docs/PROJECT_STATUS.json'
data=json.loads(status.read_text(encoding='utf-8'))
data['a12_original_pl_board_attempt_20261026']=dict(status=result['status'],kernel=scene['kernel'],boot_id=scene['boot_id'],
 manager_pid=2907,worker_pid=3039,resources_retained=True,safe_release=False,model_requests_sent=0,
 evidence='evidence/model_pl_A/20261026-original-pl-board-v1/REPORT.md',operator_binding_error=True)
status.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(result['status'])
