import json,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-20261026-v1')
pid=json.loads((root/'started.json').read_text())['pid']
r=dict(manager_pid=pid,process_exists=(Path('/proc')/str(pid)).exists(),
       active=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
for name in ('manager.stdout','manager.stderr','bundle/run-v1/result.json','bundle/run-v1/s2/web-report.json','bundle/run-v1/s2/ISOLATED.json'):
    p=root/name
    if p.is_file():r[name]=p.read_text(errors='replace')[-2400:]
r['basic_files']=[str(p.relative_to(root)) for p in root.glob('bundle/run-v1/s2/*.json')]
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
