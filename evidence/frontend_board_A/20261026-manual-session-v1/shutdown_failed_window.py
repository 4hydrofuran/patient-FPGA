import json,os,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');s2=root/'bundle/run-v1/s2'
lease=json.loads(Path('/var/lock/kv260-a1/active/lease.json').read_text());pid=lease['pid']
assert lease['window']=='a12-manual-web-20261026-v4' and pid==15867
last=json.loads((s2/'worker/stdout.jsonl').read_text().splitlines()[-1])
assert last['type']=='result' and last['status']=='ERROR' and last['state_cleared_before_response'] and last['state_position_after_clear']==-1
assert last['bridge']['a12_route']['host_verified_completions']==648
rows=[json.loads(l) for l in (s2/'worker/events.jsonl').read_text().splitlines()]
assert sum(x.get('event')=='PERMISSION' and x.get('request',{}).get('phase')=='submit' and x.get('allow') is True for x in rows)==648
wp=Path('/proc/16027');assert (wp/'exe').resolve()==root/'bundle/bin/qwen35-a12'
pipe=os.readlink(wp/'fd/0');fds=[p for p in (Path('/proc')/str(pid)/'fd').iterdir() if os.readlink(p)==pipe];assert len(fds)==1
fd=os.open(fds[0],os.O_WRONLY);os.write(fd,b'{"op":"shutdown"}\n');os.close(fd)
r={'shutdown_sent':True,'unmatched_compute_submissions':0,'exit_code':None}
for _ in range(150):
    if not wp.exists():r['process_gone_without_exit_observation']=True;break
    fields=(wp/'stat').read_text().rsplit(')',1)[1].split()
    if fields[0]=='Z':r['exit_code']=int(fields[49]);break
    time.sleep(.1)
(root/'USER_SHUTDOWN.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
