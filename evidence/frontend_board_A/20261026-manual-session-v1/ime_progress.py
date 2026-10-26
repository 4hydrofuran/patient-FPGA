import json
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v3');r={}
for n in ('ime-install-result.json','ime-install.log'):
    p=root/n
    if p.exists():r[n]=p.read_text(errors='replace')[-2200:]
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
