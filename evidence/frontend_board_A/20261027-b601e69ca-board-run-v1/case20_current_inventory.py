import hashlib,json,os,subprocess,urllib.request
from pathlib import Path
machine=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
assert machine=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
r=dict(status='CURRENT_BOARD_READ_ONLY',machine_sha256=machine,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release)
p=Path('/var/lock/kv260-a1/active/lease.json')
lease=json.loads(p.read_text()) if p.exists() else None
r['lease']=None if lease is None else {k:lease.get(k) for k in ('window','identity','pid','owner','expires_monotonic_ns')}
r['interfaces']=json.loads(subprocess.run(['ip','-j','-4','addr','show','dev','eth0'],capture_output=True,text=True,check=True).stdout)
r['memory_kib']={l.split(':')[0]:int(l.split()[1]) for l in Path('/proc/meminfo').read_text().splitlines() if l.split(':')[0] in ('MemAvailable','CmaFree')}
r['zocl_loaded']=Path('/sys/module/zocl').exists()
try:
 with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3) as f:r['http']=json.load(f)
 sid=r['http'].get('current_session_id')
 if sid:
  with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/sessions/'+sid,timeout=3) as f:s=json.load(f)
  r['session']={k:s.get(k) for k in ('session_id','case_id','closed','active_request_id')};r['session']['turn_count']=len(s['turns'])
except Exception as e:r['http_error']=type(e).__name__+': '+str(e)
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
