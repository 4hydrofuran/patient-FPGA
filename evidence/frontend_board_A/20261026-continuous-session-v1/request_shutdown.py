import json,os,signal
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-multi-20261026-v1')
p=Path('/var/lock/kv260-a1/active/lease.json')
lease=json.loads(p.read_text()) if p.exists() else None
assert lease is None or lease['window']=='a12-web-multi-20261026-v1'
(root/'stop-request.json').write_text(json.dumps(dict(reason='USER_REQUESTED_NORMAL_SHUTDOWN')))
closed=[]
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        args=(proc/'cmdline').read_bytes().split(b'\0')
        if (proc/'comm').read_text().strip()=='firefox' and b'--kiosk' in args and b'/home/ubuntu/snap/firefox/common/continuous-pl-20261026-v1' in args:
            fd=os.pidfd_open(int(proc.name));signal.pidfd_send_signal(fd,signal.SIGTERM);os.close(fd);closed.append(int(proc.name))
    except FileNotFoundError:pass
print('__PL_BEGIN__');print(json.dumps(dict(status='NORMAL_SERVICE_STOP_REQUESTED',closed_browser_pids=closed,active_lease=lease is not None)));print('__PL_END__')
