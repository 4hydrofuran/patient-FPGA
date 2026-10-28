import base64,json,sys,time,urllib.request
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-debug-20261027-v1');window=root/'continuous';out=window/'bundle/run-v1/s2'
sys.path.insert(0,str(window));from browser_bidi import Bidi
http=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8000'+p,timeout=4))
ws=Bidi();ws.s.settimeout(50);report=dict(status='RUNNING_CACHE_DEBUG_BOARD',rows=[])
try:
 caps=ws.call('session.new',{'capabilities':{}});context=ws.call('browsingContext.getTree',{})['contexts'][0]['context'];ws.call('browsingContext.activate',{'context':context})
 def ev(code):
  r=ws.call('script.evaluate',dict(expression=code,target={'context':context},awaitPromise=True))
  if r.get('type')=='exception':raise RuntimeError(str(r))
  return r.get('result',{}).get('value')
 def wait(code,seconds=35):
  x=ev('(async()=>{for(let i=0;i<'+str(seconds*10)+';i++){let x=('+code+');if(x)return x;await new Promise(r=>setTimeout(r,100));}return null;})()')
  if x is None:raise RuntimeError('Browser condition timed out: '+code)
  return x
 def count():return sum(json.loads(line).get('type')=='result' for line in (out/'worker/stdout.jsonl').read_text().splitlines())
 def ask():
  before=ev('patientResponseTimings().length')
  ev("document.getElementById('question').value='疼痛在什么位置？';document.getElementById('question-form').requestSubmit();true")
  timing=json.loads(wait("(()=>{let t=patientResponseTimings();return t.length>"+str(before)+" && t.at(-1).painted_ms!==undefined && !current.active_request_id ? JSON.stringify(t.at(-1)):null})()"))
  turn=http('/ui/v1/sessions/'+http('/ui/v1/status')['current_session_id']+'/turns/'+timing['request_id'])
  return timing,turn
 wait("typeof current!=='undefined' && current && !document.getElementById('send').disabled")
 sid=http('/ui/v1/status')['current_session_id'];assert not http('/ui/v1/sessions/'+sid)['turns'],'do not overwrite user questions'
 report['model_results_before']=count();report['browser']=caps['capabilities'].get('browserVersion')
 ev("document.getElementById('cache-debug-settings').open=true;document.getElementById('next-cache-mode').value='hit';document.getElementById('next-cache-mode').dispatchEvent(new Event('change'));document.getElementById('finish').click();true")
 wait("current.closed && !document.getElementById('new-session').disabled")
 ev("document.getElementById('new-session').click();true")
 wait("!current.closed && current.cache_mode==='hit' && !document.getElementById('send').disabled")
 timing,hit=ask();badge=ev("document.querySelector('#turns .answer-cache-source').textContent")
 assert hit['answer_source']=='MODEL_CACHE' and hit['execution_mode']=='FPGA' and hit['actual_backend'] is None and not hit['delivery_receipt']['model_called']
 assert badge=='FPGA 模式 · 缓存命中' and count()==report['model_results_before'] and timing['visibility_state']=='visible'
 report['rows'].append(dict(kind='hit',badge=badge,timing=timing,turn=hit))
 (out/'CACHE_DEBUG_HIT.png').write_bytes(base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data']))
 ev("document.getElementById('next-cache-mode').value='miss';document.getElementById('next-cache-mode').dispatchEvent(new Event('change'));true")
 assert http('/ui/v1/sessions/'+http('/ui/v1/status')['current_session_id'])['cache_mode']=='hit'
 ev("document.getElementById('finish').click();true");wait("current.closed && !document.getElementById('new-session').disabled")
 ev("document.getElementById('new-session').click();true");wait("!current.closed && current.cache_mode==='miss' && !document.getElementById('send').disabled")
 timing,miss=ask();note=ev("document.querySelector('#turns .turn-backend').textContent")
 assert miss['answer_source']=='MODEL' and miss['actual_backend']=='FPGA_REAL' and miss['delivery_receipt']['model_called'] and note=='FPGA'
 assert count()==report['model_results_before']+1 and ev("document.querySelectorAll('#turns .answer-cache-source').length")==0
 report['rows'].append(dict(kind='miss',note=note,timing=timing,turn=miss))
 (out/'CACHE_DEBUG_MISS.png').write_bytes(base64.b64decode(ws.call('browsingContext.captureScreenshot',{'context':context})['data']))
 ev("document.getElementById('next-cache-mode').value='auto';document.getElementById('next-cache-mode').dispatchEvent(new Event('change'));document.getElementById('finish').click();true")
 wait("current.closed && !document.getElementById('new-session').disabled");ev("document.getElementById('new-session').click();true")
 wait("!current.closed && current.cache_mode==='auto' && !document.getElementById('send').disabled")
 ready=http('/ui/v1/status');blank=http('/ui/v1/sessions/'+ready['current_session_id']);assert not blank['turns']
 ev("document.getElementById('cache-debug-settings').open=true;true")
 report.update(status='PASS_BOARD_DEBUG_HIT_AND_REAL_FPGA_MISS',model_results_after=count(),user_session_id=blank['session_id'],user_case_id=blank['case_id'],user_turn_count=0,user_cache_mode=blank['cache_mode'],ready=ready['ready'])
except Exception as e:report.update(status='FAILED_CACHE_DEBUG_BOARD',error=type(e).__name__+': '+str(e))
finally:
 (out/'CACHE_DEBUG_BROWSER.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 try:ws.call('session.end',{})
 finally:ws.s.close()
r={k:v for k,v in report.items() if k!='rows'};r['rows']=[dict(kind=x['kind'],note=x.get('badge',x.get('note')),source=x['turn']['answer_source'],model_called=x['turn']['delivery_receipt']['model_called'],submit_to_paint_ms=x['timing']['submit_to_paint_ms']) for x in report['rows']]
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
