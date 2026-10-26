import hashlib,json
from pathlib import Path
here=Path(__file__).parent
root=here.resolve().parents[2]
raw=here/'board-receipt'
run=raw/'bundle/run-v1'
case=run/'s2'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
web=read(case/'web-report.json');turn=read(case/'web-turn.json')
native=read(case/'native-result.json');evaluation=read(case/'web-evaluation.json')
platform=read(run/'result.json');final=read(here/'final-board.json')
events=[json.loads(line) for line in (case/'worker/stdout.jsonl').read_text().splitlines() if line]
assert len([e for e in events if e.get('type')=='result'])==1
assert web['verdict']=='PASS_BOARD_WEB_PL_SINGLE_QA' and web['error']==''
assert turn['answer_source']=='MODEL' and turn['actual_backend']=='FPGA_REAL'
receipt=turn['delivery_receipt']
assert receipt['model_called'] is True and receipt['validation_status']=='pass'
assert hashlib.sha256(turn['answer'].encode()).hexdigest()==receipt['answer_sha256']
assert native['text']==turn['answer'] and native['eos'] is True
assert native['state_cleared_before_response'] is True and native['state_position_after_clear']==-1
assert evaluation['rule_score']['score']==10 and evaluation['summary_source']=='RULE_TEMPLATE'
assert platform['permission_submissions']==platform['backend_host_verified_completions']==web['permission_runs']==1656
assert web['weight_loads']==72 and web['browser_exit']==0 and web['web_thread_stopped']
assert not final['active'] and not final['zocl'] and final['gdm']=='active'
assert final['overlays']=={'k26-starter-kits_image_1':'applied'}
summary=dict(status='PASS_BOARD_FRONTEND_PL_SINGLE_QA',verification_level='BOARD_WEB_AND_REAL_PL',
    deployment='/var/lib/kv260-a12/web-20261026-v1',question=turn['question'],answer=turn['answer'],
    actual_backend=turn['actual_backend'],model_called=True,model_requests=1,
    browser='Firefox 158.0 headless 1024x600',browser_question_to_answer_s=web['browser_question_to_answer_s'],
    score=10,score_max=100,chief_summary_source='RULE_TEMPLATE',
    permission_submissions=1656,backend_host_verified_completions=1656,weight_loads=72,
    hardware_global_count=None,worker_exit_code=0,browser_exit_code=0,
    manager_exit_code=None,manager_exit_code_note='Detached child was not waitpid-collected; normal terminal message and absent PID verified',
    manager_normal_terminal_message=True,manager_pid_absent=True,
    default_PL_restored=True,gdm_active=True,active_lease=False,zocl=False,
    UI_service_running_after_test=False,board_left_powered_on=True,
    physical_screen_touch='NOT_TESTED',audio='NOT_TESTED',long_term_service='NOT_TESTED',
    PL_rebuild=False,reboot=False,flashing=False,medical_review='PENDING_TEACHER_REVIEW',
    receipt_zip_sha256=final['sha256'])
(here/'RESULT.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
status_path=root/'docs/PROJECT_STATUS.json'
status=read(status_path)
key='web_frontend_pl_single_20261026'
assert key not in status
status[key]={k:summary[k] for k in ('status','verification_level','deployment','model_requests',
    'actual_backend','browser_question_to_answer_s','permission_submissions','weight_loads',
    'worker_exit_code','browser_exit_code','manager_exit_code','default_PL_restored','active_lease',
    'zocl','physical_screen_touch','audio','long_term_service')}
status[key]['evidence']='evidence/frontend_board_A/20261026-board-integration-v1/REPORT.md'
status_path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
monitor_path=root/'evidence/frontend_board_A/20261026-integration-prep-v1/monitor-state.json'
monitor=read(monitor_path);monitor.update(status='COMPLETE_BOARD_SINGLE_QA',board_deployment=summary['deployment'],
    result=str((here/'RESULT.json').relative_to(root)).replace('\\','/'),automation_deleted=True)
monitor_path.write_text(json.dumps(monitor,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
