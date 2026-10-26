import json
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-multi-20261026-v1');r=dict(active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
for name in ('bundle/run-v1/s2/manual-compute-closed.json','bundle/run-v1/result.json','bundle/run-v1/s2/ISOLATED.json','manager.stderr'):
    p=root/name
    if p.exists():r[name]=p.read_text(errors='replace')[-1800:]
r['overlays']={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir()}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
