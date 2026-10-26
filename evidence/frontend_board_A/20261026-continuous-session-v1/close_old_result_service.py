import json,os,signal,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/gui-qa-20261026-v2')
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
result=json.loads((root/'bundle/run-v1/result.json').read_text());assert result['worker_exit_code']==0 and result['lease_archived']
closed=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=(p/'cmdline').read_bytes().split(b'\0')
        if (p/'comm').read_text().strip()=='firefox' and b'--kiosk' in args and b'/home/ubuntu/snap/firefox/common/manual-pl-20261026-v2' in args:
            fd=os.pidfd_open(int(p.name));signal.pidfd_send_signal(fd,signal.SIGTERM);os.close(fd);closed.append(int(p.name))
    except FileNotFoundError:pass
pid=json.loads((root/'started.json').read_text())['pid'];p=Path('/proc')/str(pid)
if p.exists():
    assert str(root/'interactive_entry.py').encode() in (p/'cmdline').read_bytes()
    fd=os.pidfd_open(pid);signal.pidfd_send_signal(fd,signal.SIGUSR1);os.close(fd)
    for _ in range(50):
        if not p.exists():break
        time.sleep(.1)
    assert not p.exists()
r=dict(status='PREVIOUS_FINISHED_RESULT_SERVICE_STOPPED',old_worker_exit=0,manager_pid=pid,closed_browser_pids=closed,active_lease=False)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
