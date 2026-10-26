import io,json,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/gui-qa-20261026-v2');s2=root/'bundle/run-v1/s2'
verification=json.loads((s2/'WEB_REAL_VERIFICATION.json').read_text())
assert verification['status']=='PASS_REAL_GRAPHICAL_MODEL_FPGA_QUESTION'
user_ready=json.loads((s2/'USER_INPUT_READY.json').read_text())
def get(path):return json.load(urllib.request.urlopen('http://127.0.0.1:8000'+path,timeout=4))
status=get('/ui/v1/status');snapshot=get('/ui/v1/sessions/'+user_ready['session_id'])
rows=[json.loads(l) for l in (s2/'worker/stdout.jsonl').read_text().splitlines()]
result=next(x for x in reversed(rows) if x.get('type')=='result')
(s2/'verification-native-result.json').write_text(json.dumps(result))
state=dict(status='VERIFIED_AND_USER_SESSION_READY',web_status=status,user_session=snapshot,
    remaining_seconds=(user_ready['expires_monotonic_ns']-time.monotonic_ns())/1e9,
    actual_worker_result_status=result['status'],prefix_cache_request=result['prefix_cache_request'],
    host_verified_completions=result['bridge']['a12_route']['host_verified_completions'],
    hardware_global_count=None,active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
(root/'BASIC_READY.json').write_text(json.dumps(state,indent=2))
data=io.BytesIO()
with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
    for p in [root/'installed.json',root/'BASIC_READY.json',root/'manager.stderr',root/'web-config.json',root/'bundle/run-v1/pre-allocation-admission.json']+list(s2.glob('*.json'))+list(s2.glob('*.png'))+[s2/'browser.log']:
        if p.is_file():z.write(p,p.relative_to(root))
with urllib.request.urlopen(urllib.request.Request('http://192.168.2.1:8766/receipt.zip',data=data.getvalue(),method='POST'),timeout=10) as f:assert f.read()==b'RECEIVED'
print('__PL_BEGIN__');print(json.dumps(dict(verification=verification,state=state,receipt_bytes=len(data.getvalue()))));print('__PL_END__')
