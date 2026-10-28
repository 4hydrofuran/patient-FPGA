"""Explicit one-job recovery, only after A read the completed failure and processes."""
import fcntl, json, os, sys
from pathlib import Path
q=Path('/home/member-a/kv260-build/ra02-coordinator')
expected=sys.argv[1]
if '/' in expected or not expected:raise ValueError('job id required')
with (q/'queue.lock').open('a+') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    active=json.loads((q/'active.json').read_text())
    receipt=json.loads((q/'results'/(expected+'.json')).read_text())
    if active['job']!=expected or receipt['job']!=expected or receipt['status']!='FAILED' or receipt['exit_code']==0:
        raise ValueError('exact completed failure required')
    # Reject if another process still executes the job entry point.
    entry=active['argv'][-1].encode()
    for p in Path('/proc').glob('[0-9]*/cmdline'):
        if int(p.parent.name)==os.getpid():continue
        try:args=p.read_bytes().split(b'\0')
        except (OSError,PermissionError):continue
        if entry in args:raise RuntimeError('job process remains')
    dest=q/('active.failed-'+expected+'.json')
    if dest.exists():raise FileExistsError(dest)
    (q/'active.json').rename(dest)
    print(json.dumps({'archived_exact_failed_job':expected,'evidence_retained':str(dest)}))
