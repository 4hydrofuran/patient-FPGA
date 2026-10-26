import json
from pathlib import Path
out=Path(__file__).parent
def read(name):
    r=json.loads((out/name).read_text(encoding='utf-8-sig'))
    assert r['error'] is None
    return json.loads(r['output'].rsplit('__PL_BEGIN__',1)[1].split('__PL_END__')[0])
session=read('user-exit-diagnosis-uart.json');detail=read('turn-failure-details-uart.json');health=read('health-failure-uart.json');restored=read('user-exit-restored-uart.json')
for name,data in (('USER_EXIT_DIAGNOSIS.json',session),('TURN_FAILURE_DETAILS.json',detail),('HEALTH_FAILURE.json',health),('USER_EXIT_RESTORED.json',restored)):
    (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
result=dict(status='FAILED_MANUAL_FIRST_QUESTION_CLEANED_UP',physical_domain='BOARD',case_id=session['session_after']['case_id'],
    session_closed=True,published_answer=False,prefix_hit=True,reused_prefix_tokens=70,prompt_tokens=107,new_tokens=37,
    new_PL_submissions=0,warm_PL_completions=648,output_tokens=0,worker_exit_code=2,
    gate_rejection='UNREVIEWED_OR_DUPLICATE_DIAGNOSTIC',rejected_diagnostic='kauditd_printk_skb: 4 callbacks suppressed',
    kernel_gate_bypassed_for_compute=False,active_lease=False,zocl=False,default_PL_restored=True,model_question_pass=False)
(out/'MANUAL_RESULT.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
