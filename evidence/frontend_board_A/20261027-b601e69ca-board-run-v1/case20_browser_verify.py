import base64,json,sys,time,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-random-20261027-v1');window=root/'continuous';out=window/'bundle/run-v1/s2'
sys.path.insert(0,str(window));from browser_bidi import Bidi
http=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8000'+p,timeout=4))
ws=Bidi();ws.s.settimeout(50);report=dict(status='RUNNING_BOARD_RANDOM_CACHE_VERIFICATION',rows=[])
try:
 caps=ws.call('session.new',{'capabilities':{}});context=ws.call('browsingContext.getTree',{})['contexts'][0]['context']
 ws.call('browsingContext.activate',{'context':context})
 def ev(code):
  r=ws.call('script.evaluate',dict(expression=code,target={'context':context},awaitPromise=True))
  if r.get('type')=='exception':raise RuntimeError(str(r))
  return r.get('result',{}).get('value')
 def wait(code,seconds=15):
  result=ev('(async()=>{for(let i=0;i<'+str(seconds*10)+';i++){let r=('+code+');if(r)return r;await new Promise(r=>setTimeout(r,100));}return null;})()')
  if result is None:raise RuntimeError('Browser condition timed out: '+code)
  return result
 def model_results():
  return sum(json.loads(line).get('type')=='result' for line in (out/'worker/stdout.jsonl').read_text().splitlines())
 wait("typeof current!=='undefined' && current && !current.closed && !document.getElementById('send').disabled")
 before=http('/ui/v1/status');sid=before['current_session_id'];assert not http('/ui/v1/sessions/'+sid)['turns'],'do not add tests to a user consultation'
 assert ev("document.getElementById('cases')===null") is True
 assert before['capabilities']['case_selection']=='random' and before['capabilities']['case_count']==20 and before['answer_cache']['entries']==1320
 report.update(browser=caps['capabilities'].get('browserVersion'),model_results_before=model_results(),cache_hits_before=before['answer_cache']['hits'])
 for i in range(3):
  if i:
   ev("document.getElementById('new-session').click();true")
   wait("!current.closed && !document.getElementById('send').disabled")
  sid=http('/ui/v1/status')['current_session_id'];snapshot=http('/ui/v1/sessions/'+sid);cid=snapshot['case_id']
  if i==0:
   ws.call('browsingContext.reload',{'context':context})
   wait("typeof current!=='undefined' && current?.session_id==="+json.dumps(sid)+" && !document.getElementById('send').disabled")
   assert http('/ui/v1/sessions/'+sid)['case_id']==cid
  count=ev('patientResponseTimings().length')
  ev("document.getElementById('question').value='疼痛在什么位置？';document.getElementById('question-form').requestSubmit();true")
  timing=json.loads(wait("(()=>{const t=patientResponseTimings();return t.length>"+str(count)+" && t.at(-1).painted_ms!==undefined && !current.active_request_id ? JSON.stringify(t.at(-1)):null})()"))
  turn=http('/ui/v1/sessions/'+sid+'/turns/'+timing['request_id'])
  assert turn['answer_source']=='MODEL_CACHE' and turn['actual_backend'] is None and turn['delivery_receipt']['model_called'] is False
  assert timing['visibility_state']=='visible'
  report['rows'].append(dict(case_id=cid,session_id=sid,answer=turn['answer'],timing=timing,turn=turn))
  if i==0:(out/'CASE20_RANDOM_CACHE.png').write_bytes(base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data']))
  ev("document.getElementById('finish').click();true")
  wait("current.closed && !document.getElementById('evaluation-result').hidden")
 ev("document.getElementById('new-session').click();true")
 wait("!current.closed && !document.getElementById('send').disabled")
 after=http('/ui/v1/status');blank=http('/ui/v1/sessions/'+after['current_session_id'])
 assert not blank['turns'] and not blank['closed']
 assert model_results()==report['model_results_before']
 report.update(status='PASS_BOARD_RANDOM_CASES_CACHE_AND_REFRESH',model_results_after=model_results(),cache_hits_after=after['answer_cache']['hits'],
  ready=after['ready'],user_session_id=blank['session_id'],user_case_id=blank['case_id'],user_turn_count=0,pool_size=20,manual_selector=False)
 (out/'CASE20_RANDOM_USER_READY.png').write_bytes(base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data']))
except Exception as e:
 report.update(status='FAILED_BOARD_RANDOM_CACHE_VERIFICATION',error=type(e).__name__+': '+str(e))
finally:
 (out/'CASE20_RANDOM_BROWSER.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 try:ws.call('session.end',{})
 finally:ws.s.close()
small={k:v for k,v in report.items() if k!='rows'};small['rows']=[dict(case_id=r['case_id'],answer=r['answer'],submit_to_paint_ms=r['timing']['submit_to_paint_ms'],source=r['turn']['answer_source']) for r in report['rows']]
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(small),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
