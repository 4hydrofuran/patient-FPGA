import json,time
from pathlib import Path
def memory():return {s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith(('MemAvailable:','CmaFree:'))}
r={'before':memory(),'action':'one kernel memory compaction; no cache drop, file deletion, allocation test or persistent setting'}
Path('/proc/sys/vm/compact_memory').write_text('1\n')
r['after']=memory()
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
