import base64,hashlib,io,json,os,time,urllib.request,zipfile
from pathlib import Path
root=Path('/var/lib/kv260-a12/case20-random-20261027-v1');s=root/'continuous/bundle/run-v1/s2'
http=lambda p:json.load(urllib.request.urlopen('http://127.0.0.1:8000'+p,timeout=4))
status=http('/ui/v1/status');snapshot=http('/ui/v1/sessions/'+status['current_session_id'])
lease=json.loads(Path('/var/lock/kv260-a1/active/lease.json').read_text())
assert lease['window']=='a12-case20-random-20261027-v1' and status['ready'] and status['capabilities']['case_count']==20
assert status['answer_cache']['entries']==1320 and not status['busy']
verification=json.loads((s/'WEB_REAL_VERIFICATION.json').read_text());browser=json.loads((s/'CASE20_RANDOM_BROWSER.json').read_text())
def rss(pid):
 p=Path('/proc',str(pid),'status')
 if not p.exists():return None
 return next(int(l.split()[1]) for l in p.read_text().splitlines() if l.startswith('VmRSS:'))
identity=json.loads((s/'identity.json').read_text())
r=dict(status='BOARD_CASE20_RANDOM_LIVE_READY',machine_sha256=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
 window=lease['window'],owner_pid=lease['pid'],native_pid=identity['pid'],owner_intentionally_retained=True,remaining_seconds=status['remaining_seconds'],
 runtime_root=str(root),cases=20,case_selection='SERVER_RANDOM_PER_SESSION',manual_selector=False,cache_entries=1320,catalog_bytes=status['answer_cache']['bytes'],
 actual_FPGA_probe=verification['status'],actual_FPGA_probe_case=verification['case_id'],actual_FPGA_probe_seconds=verification['question_to_answer_seconds'],
 browser_check=browser['status'],cached_visible_ms=[x['timing']['submit_to_paint_ms'] for x in browser['rows']],cached_case_ids=[x['case_id'] for x in browser['rows']],
 session_id=snapshot['session_id'],case_id=snapshot['case_id'],session_closed=snapshot['closed'],turn_count=len(snapshot['turns']),active_request_id=snapshot['active_request_id'],
 manager_rss_kib=rss(lease['pid']),native_rss_kib=rss(identity['pid']),memory_kib={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.split(':')[0] in ('MemAvailable','CmaFree','CmaTotal')},
 observed_monotonic_ns=time.monotonic_ns(),reboots_this_task=0,normal_release_current_window='PENDING_UNTIL_USER_STOPS_SERVICE')
(root/'CASE20_LIVE_HANDOVER.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
files=['WEB_REAL_VERIFICATION.json','verification-turn.json','CASE20_RANDOM_BROWSER.json','ANSWER_CACHE_ENABLED.json','warm-result.json','graphical-allocation.json']
buf=io.BytesIO()
with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
 for n in files:
  p=s/n
  if p.exists():z.writestr(n,p.read_bytes())
 z.writestr('LIVE_HANDOVER.json',json.dumps(r,ensure_ascii=False,indent=2)+'\n')
raw=buf.getvalue();out=dict(status='BOARD_EVIDENCE_COLLECTED',summary=r,zip_sha256=hashlib.sha256(raw).hexdigest(),zip_base64=base64.b64encode(raw).decode())
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(out),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
