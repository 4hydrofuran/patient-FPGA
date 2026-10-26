import json,os,shutil,subprocess
from pathlib import Path
tasks=[]
for p in Path('/proc').iterdir():
    if not p.name.isdigit() or int(p.name)==os.getpid():continue
    try:
        name=(p/'comm').read_text().strip()
        if name.startswith(('qwen','llama')):tasks.append(dict(pid=int(p.name),name=name))
    except (OSError,ValueError):pass
mem={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith(('MemAvailable:','CmaFree:'))}
disk=shutil.disk_usage('/home/ubuntu')
result=dict(scope='UPLOAD_ONLY_NO_COMPUTE',kernel=os.uname().release,model_tasks=tasks,memory_kib=mem,home_free_bytes=disk.free)
print('__A12_UPLOAD_BEGIN__',flush=True)
print(json.dumps(result),flush=True)
print('__A12_UPLOAD_END__',flush=True)
