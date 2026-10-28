import hashlib,json,time,urllib.request
from pathlib import Path
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='98886b24-96d3-409e-a783-ce9c54873da9'
root=Path('/var/lib/kv260-a12/b601e69ca-hotpath-20261027-v7')
lease=json.loads(Path('/var/lock/kv260-a1/active/lease.json').read_text());assert lease['window']=='a12-b601e69ca-hotpath-20261027-v7'
with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3) as f:status=json.load(f)
with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/sessions/'+status['current_session_id'],timeout=3) as f:snapshot=json.load(f)
(root/'CASE20_HANDOVER_SNAPSHOT.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
(root/'continuous/stop-request.json').write_text(json.dumps(dict(reason='USER_AUTHORIZED_CASE20_RANDOM_DEPLOYMENT',requested_monotonic_ns=time.monotonic_ns()))+'\n')
r=dict(status='ORIGINAL_OWNER_NORMAL_STOP_REQUESTED',busy=status['busy'],preserved_session_id=snapshot['session_id'],preserved_turn_count=len(snapshot['turns']),old_owner_pid=lease['pid'],forced_hardware_stop=False)
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
