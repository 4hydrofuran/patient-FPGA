"""Read-only fixed-task scene capture. No signals, lock operations or device changes."""
import hashlib,json,os,time
from pathlib import Path

ROOT=Path('/var/lib/kv260-a12/tt10-01-20261024-v1')
assert os.uname().machine=='aarch64'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
result=dict(event='READ_ONLY_TASK_SCENE',monotonic_ns=time.monotonic_ns(),files={},processes=[])
for p in sorted((ROOT/'run-v1').rglob('*')):
    if not p.is_file():continue
    name=p.relative_to(ROOT).as_posix();st=p.stat()
    if p.suffix in ('.json','.jsonl','.txt') or p.name.endswith('.log'):
        item=dict(bytes=st.st_size,mtime=st.st_mtime)
        if p.suffix=='.json' and st.st_size<200000:item['json']=json.loads(p.read_text())
        elif st.st_size:
            with p.open('rb') as f:f.seek(max(0,st.st_size-3000));item['tail']=f.read().decode(errors='replace')
        result['files'][name]=item
for p in Path('/proc').iterdir():
    if not p.name.isdigit():continue
    try:
        argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
        if str(ROOT) not in argv:continue
        result['processes'].append(dict(pid=int(p.name),argv=argv,stat=(p/'stat').read_text(),
            status=(p/'status').read_text(),io=(p/'io').read_text(),wchan=(p/'wchan').read_text()))
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
result['meminfo']=Path('/proc/meminfo').read_text()
print(json.dumps(result),flush=True)
