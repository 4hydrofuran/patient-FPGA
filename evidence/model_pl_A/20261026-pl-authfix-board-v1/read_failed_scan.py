import json,os
from pathlib import Path
root=Path('/var/lib/kv260-a12/pl-authfix-20261026-v1')
p=root/'bundle/run-v1/s2/owner-initial-resource-scan.json'
q=json.loads(p.read_text())
issues=q['scan_issues']
for row in issues:
 if 'pid' in row:
  cmd=Path('/proc')/str(row['pid'])/'cmdline'
  if cmd.exists():row['current_command']=cmd.read_bytes().replace(b'\0',b' ').decode(errors='replace')
print('__PL_BEGIN__');print(json.dumps(dict(scan_complete=q['scan_complete'],boot_id=q['boot_id'],scan_issues=issues,
 active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())));print('__PL_END__')
