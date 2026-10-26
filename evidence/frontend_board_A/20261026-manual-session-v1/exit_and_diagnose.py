import datetime,json,time,urllib.request,uuid
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');run=root/'bundle/run-v1';r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
def get(path):
    return json.load(urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=4))
try:
    status=get('/ui/v1/status');r['status_before']=status;sid=status['current_session_id']
    if sid:
        r['session_before']=get('/ui/v1/sessions/'+sid)
        if not r['session_before']['closed'] and not status['busy']:
            req=urllib.request.Request('http://127.0.0.1:8000/ui/v1/sessions/'+sid+'/finish',data=json.dumps({'request_id':uuid.uuid4().hex}).encode(),headers={'Content-Type':'application/json'})
            r['finish']=json.load(urllib.request.urlopen(req,timeout=5))
        else:r['finish']={'already_closed':r['session_before']['closed'],'busy':status['busy']}
        r['session_after']=get('/ui/v1/sessions/'+sid)
        if r['session_after']['closed']:r['evaluation']=get('/ui/v1/sessions/'+sid+'/evaluation')
    r['status_after']=get('/ui/v1/status')
except Exception as e:r['http_error']=str(e)
for n in ('manager.stderr','bundle/run-v1/s2/ISOLATED.json','bundle/run-v1/s2/manual-compute-closed.json','bundle/run-v1/result.json','bundle/run-v1/s2/manual-session.json'):
    p=root/n
    if p.is_file():r[n]=p.read_text(errors='replace')[-3500:]
p=run/'s2/INTERACTIVE_READY.json'
if p.exists():r['remaining_seconds']=(json.loads(p.read_text())['expires_monotonic_ns']-time.monotonic_ns())/1e9
p=run/'s2/worker/stdout.jsonl'
if p.exists():
    rows=[json.loads(l) for l in p.read_text().splitlines()]
    r['worker_terminal']=[{k:x.get(k) for k in ('type','id','status','message','prefix_cache_request')} for x in rows if x.get('type') in ('ready','cache_created','result','error')]
p=Path('/var/lock/kv260-a1/active/lease.json');r['lease']=json.loads(p.read_text()) if p.exists() else None
r['zocl']=Path('/sys/module/zocl').exists()
(root/'USER_EXIT_DIAGNOSIS.json').write_text(json.dumps(r,indent=2))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
