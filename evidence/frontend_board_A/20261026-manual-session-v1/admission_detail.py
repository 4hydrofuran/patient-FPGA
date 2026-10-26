import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v1')
pid=json.loads((root/'started.json').read_text())['pid']
r={'pid':pid,'admission':json.loads((root/'bundle/run-v1/pre-allocation-admission.json').read_text()),
   'zocl':Path('/sys/module/zocl').exists(),
   'memory':{l.split(':')[0]:l.split(':')[1].strip() for l in Path('/proc/meminfo').read_text().splitlines() if l.startswith(('MemAvailable:','CmaFree:','CmaTotal:','Cached:','Dirty:','Writeback:'))},
   'manager_fds':{p.name:os.readlink(p) for p in (Path('/proc')/str(pid)/'fd').iterdir()},
   'worker_dir_exists':(root/'bundle/run-v1/s2/worker').exists()}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
