import subprocess,json
code=r'''
import json,sys,time
from pathlib import Path
root=Path('/home/ubuntu/a12-resident-basic-20261026-v1');run=root/'run-v1'
r=json.loads((run/'RESULT.json').read_text());q=r['native_result'];ready=r['ready']
sys.path.insert(0,str(root/'a12-resident-20261026-v1/resident-app'))
from app.domain import load_case,Transcript
from app.planning import plan
from app.checking import check
t=Transcript.parse(dict(request_id='basic-cpu-01',text='疼痛在什么位置？',source='typed',final=True))
p=plan(load_case('SYN_CP_01'),t,[]);c=check(p,q['text'])
assert ready['execution_kind']==q['bridge']['a12_route']['execution_kind']=='CPU_REFERENCE'
assert q['type']=='result' and q['status']=='OK' and q['eos'] is True
assert q['state_cleared_before_response'] is True and q['state_position_after_clear']==-1
assert c['status']=='pass' and r['exit_code']==0 and r['process_still_live'] is False
timing={k:v for k,v in q.items() if any(x in k for x in ('_ms','_s','elapsed','time')) and isinstance(v,(int,float))}
review=dict(status='PASS_BOARD_CPU_SINGLE_GENERATION_AND_ORIGINAL_CONTENT_CHECK',question=t.text,text=q['text'],eos=q['eos'],content_check=c,exit_code=r['exit_code'],startup_s=r['startup_s'],native_timing=timing,CPU_calls=q['bridge']['cpu_run_count'],weight_count=q['bridge']['weight_count'],execution_kind='CPU_REFERENCE',PL_calls=0,review_of_existing_run=True,model_rerun=False,original_record='RESULT.json',harness_error='Missing enabled field; disabled route declares execution_kind=CPU_REFERENCE',live_application_delivery_completed=False,private_PLM_or_PL_acceptance=False)
with (run/'REVIEW-v2.json').open('x') as f:json.dump(review,f,ensure_ascii=False,indent=2)
print(json.dumps(review,ensure_ascii=False))
'''
p=subprocess.run(['sudo','-n','/usr/bin/python3','-B','-I','-c',code],capture_output=True,text=True,timeout=25)
print('__A12_UPLOAD_BEGIN__',flush=True)
print(json.dumps(dict(exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)),flush=True)
print('__A12_UPLOAD_END__',flush=True)
