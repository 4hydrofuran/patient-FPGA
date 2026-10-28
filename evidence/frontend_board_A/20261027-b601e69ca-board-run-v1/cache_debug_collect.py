import base64,hashlib,io,json,os,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-debug-20261027-v1');s=root/'continuous/bundle/run-v1/s2'
http=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8000'+p,timeout=4))
status=http('/ui/v1/status');snapshot=http('/ui/v1/sessions/'+status['current_session_id']);lease=json.loads(Path('/var/lock/kv260-a1/active/lease.json').read_text())
assert lease['window']=='a12-case20-debug-20261027-v1' and status['ready'] and status['answer_cache']['entries']==1320
report=json.loads((s/'CACHE_DEBUG_BROWSER.json').read_text());assert report['status']=='PASS_BOARD_DEBUG_HIT_AND_REAL_FPGA_MISS'
r=dict(status='CACHE_DEBUG_BOARD_LIVE_READY',machine_sha256=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
 window=lease['window'],owner_pid=lease['pid'],runtime_root=str(root),owner_intentionally_retained=True,remaining_seconds=status['remaining_seconds'],
 case_count=20,case_selection='SERVER_RANDOM',catalog_entries=status['answer_cache']['entries'],catalog_sha256=status['answer_cache']['catalog_sha256'],
 cached_badge=report['rows'][0]['badge'],uncached_note=report['rows'][1]['note'],hit_ms=report['rows'][0]['timing']['submit_to_paint_ms'],miss_ms=report['rows'][1]['timing']['submit_to_paint_ms'],
 model_results_before=report['model_results_before'],model_results_after=report['model_results_after'],
 user_session_id=snapshot['session_id'],user_case_id=snapshot['case_id'],user_cache_mode=snapshot['cache_mode'],user_turn_count=len(snapshot['turns']),ready=status['ready'],busy=status['busy'],reboots_this_task=0,
 observed_monotonic_ns=time.monotonic_ns(),normal_release='PENDING_UNTIL_USER_SERVICE_STOP')
(root/'CACHE_DEBUG_LIVE_HANDOVER.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for name in ['CACHE_DEBUG_BROWSER.json','WEB_REAL_VERIFICATION.json','ANSWER_CACHE_ENABLED.json','verification-turn.json']:
  z.writestr(name,(s/name).read_bytes())
 z.writestr('LIVE_HANDOVER.json',json.dumps(r,ensure_ascii=False,indent=2)+'\n')
b=buf.getvalue();value=dict(status='CACHE_DEBUG_EVIDENCE_COLLECTED',summary=r,zip_sha256=hashlib.sha256(b).hexdigest(),zip_base64=base64.b64encode(b).decode())
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(value),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
