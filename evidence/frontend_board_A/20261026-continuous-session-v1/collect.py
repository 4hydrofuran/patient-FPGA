import io,json,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-multi-20261026-v1');s2=root/'bundle/run-v1/s2'
verification=json.loads((s2/'CONTINUOUS_VERIFICATION.json').read_text());assert verification['status']=='PASS_CONTINUOUS_GUI_MULTI_TURN_AND_NEW_SESSION'
def get(path):return json.load(urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=4))
status=get('/ui/v1/status');snapshot=get('/ui/v1/sessions/'+status['current_session_id'])
ready=json.loads((s2/'ready.json').read_text());route=ready['bridge']['a12_route']
messages=[json.loads(l) for l in (s2/'worker/stdout.jsonl').read_text().splitlines()]
warm_count=sum(x.get('type')=='cache_created' for x in messages)
state=dict(status='CONTINUOUS_SERVICE_VERIFIED_AND_READY',web_status=status,user_session=snapshot,
    loaded_backend_run_budget=route['a12_max_runs'],loaded_weight_count=route['weight_load_count'],warm_count=warm_count,
    bo_bytes=route['owned_bo_charged_bytes'],bo_count=route['a11_explicit_bo_allocations_host_counter'],
    active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
assert state['loaded_backend_run_budget']==60000 and warm_count==1 and state['loaded_weight_count']==72
(root/'BASIC_READY.json').write_text(json.dumps(state,indent=2))
data=io.BytesIO()
with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
    files=[root/'installed.json',root/'BASIC_READY.json',root/'manager.stderr',root/'web-config.json',root/'bundle/control/window-spec.json',root/'bundle/evidence/RESOURCE_CALL_BUDGET.json']
    files+=list(s2.glob('*.json'))+list(s2.glob('*.png'))+list((s2/'consultations').glob('*.json'))+[s2/'browser.log']
    for p in files:
        if p.is_file():z.write(p,p.relative_to(root))
with urllib.request.urlopen(urllib.request.Request('http://192.168.2.1:8766/receipt.zip',data=data.getvalue(),method='POST'),timeout=10) as f:assert f.read()==b'RECEIVED'
print('__PL_BEGIN__');print(json.dumps(dict(verification=verification,state=state,receipt_bytes=len(data.getvalue()))));print('__PL_END__')
