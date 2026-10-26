import fcntl,json,os,signal,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v1')
central=Path('/var/lock/kv260-a1');active=central/'active'
raw=(active/'lease.json').read_bytes();lease=json.loads(raw);pid=lease['pid']
assert lease['window']=='a12-manual-web-20261026-v1' and pid==10471
proc=Path('/proc')/str(pid)
assert b'/var/lib/kv260-a12/manual-web-20261026-v1/interactive_entry.py' in (proc/'cmdline').read_bytes()
assert not Path('/sys/module/zocl').exists() and not (root/'bundle/run-v1/s2/worker').exists()
assert not (proc/'task'/str(pid)/'children').read_text().strip()
assert 'COMMAND_BEGIN' not in (root/'bundle/run-v1/lifecycle.jsonl').read_text()
for p in (proc/'fd').iterdir():assert not os.readlink(p).startswith(('/dev/dri/','/dev/xclmgmt'))
fd=os.pidfd_open(pid);signal.pidfd_send_signal(fd,signal.SIGUSR1);os.close(fd)
for _ in range(50):
    if not proc.exists():break
    time.sleep(.1)
assert not proc.exists()
locks=[]
try:
    for p in (central/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock')):
        fd=os.open(p,os.O_RDWR);locks.append(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    assert (active/'lease.json').read_bytes()==raw
    active.rename(central/'history/a12-manual-web-20261026-v1-prepl-abort')
finally:
    for fd in locks:os.close(fd)
r={'status':'OWN_ZERO_DEVICE_PREPL_WINDOW_ABORTED_AND_ARCHIVED','pid':pid,'signal':'SIGUSR1',
   'worker_started':False,'PL_commands':0,'normal_worker_exit_claimed':False}
(root/'prepl-abort.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
