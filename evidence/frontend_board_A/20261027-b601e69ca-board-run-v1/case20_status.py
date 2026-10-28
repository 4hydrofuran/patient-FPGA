import json,urllib.request,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-random-20261027-v1');s=root/'continuous/bundle/run-v1/s2'
r=dict(status='CASE20_RANDOM_STARTUP_STATUS',root=str(root),files={})
for n in ('STARTED.json','continuous/bundle/run-v1/result.json','continuous/bundle/run-v1/s2/WEB_REAL_VERIFICATION.json','continuous/bundle/run-v1/s2/ANSWER_CACHE_ENABLED.json','continuous/bundle/run-v1/s2/USER_INPUT_READY.json'):
 p=root/n
 if p.exists():r['files'][n]=json.loads(p.read_text())
p=root/'manager.stderr'
if p.exists():r['stderr_tail']=p.read_text()[-1700:]
try:
 with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3) as f:r['http']=json.load(f)
 sid=r['http'].get('current_session_id')
 if sid:
  with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/sessions/'+sid,timeout=3) as f:x=json.load(f)
  r['session']={k:x.get(k) for k in ('session_id','case_id','closed','active_request_id')};r['session']['turn_count']=len(x['turns'])
except Exception as e:r['http_error']=str(e)
r['observed_monotonic_ns']=time.monotonic_ns()
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
