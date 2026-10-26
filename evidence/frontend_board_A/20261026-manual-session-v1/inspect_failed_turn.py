import json,os,signal,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4');s2=root/'bundle/run-v1/s2';r={}
rows=[json.loads(l) for l in (s2/'worker/stdout.jsonl').read_text().splitlines()]
last=next(x for x in reversed(rows) if x.get('type')=='result')
r['terminal']={k:v for k,v in last.items() if k not in ('bridge','prefix_cache','prefix_cache_request','tokens','token_ids','logits')}
route=last.get('bridge',{}).get('a12_route',{})
r['route']={k:v for k,v in route.items() if any(s in k for s in ('error','fault','reason','count','runs','completion','budget','status')) and not isinstance(v,(list,dict))}
r['worker_files']=[p.name for p in (s2/'worker').iterdir()]
for p in (s2/'worker').iterdir():
    if p.is_file() and p.name!='stdout.jsonl':
        raw=p.read_text(errors='replace')
        if p.suffix=='.jsonl':r[p.name]=[l[-1800:] for l in raw.splitlines() if any(w in l for w in ('FAULT','REFUSED','BAD_EXIT','CLOSE_','WORKER_EXITED','CANCEL','"allow": false'))][-8:]
        else:r[p.name]=raw[-1800:]
for n in ('ISOLATED.json','native-result.json','manual-compute-closed.json','manual-session.json'):
    p=s2/n
    if p.exists():r[n]=p.read_text()[-1800:]
closed=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        args=(p/'cmdline').read_bytes().split(b'\0')
        if (p/'comm').read_text().strip()=='firefox' and b'--kiosk' in args and b'/home/ubuntu/snap/firefox/common/manual-pl-20261026-v1' in args:
            fd=os.pidfd_open(int(p.name));signal.pidfd_send_signal(fd,signal.SIGTERM);os.close(fd);closed.append(int(p.name))
    except FileNotFoundError:pass
r['closed_own_firefox_pids']=closed
(root/'TURN_FAILURE_DETAILS.json').write_text(json.dumps(r,indent=2))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
