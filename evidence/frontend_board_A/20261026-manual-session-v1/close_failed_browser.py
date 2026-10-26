import json,os,signal,time
from pathlib import Path
def memory():return {s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith(('MemAvailable:','CmaFree:'))}
p=Path('/proc/9225')
assert p.stat().st_uid==1000 and (p/'comm').read_text().strip()=='firefox'
r={'before':memory(),'pid':9225,'action':'normal SIGTERM to current failed-page browser; desktop retained'}
os.kill(9225,signal.SIGTERM)
for _ in range(60):
    if not p.exists():break
    time.sleep(.1)
r.update(browser_gone=not p.exists(),after=memory())
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
