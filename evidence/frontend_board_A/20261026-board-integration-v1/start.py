import json,os,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/web-20261026-v1')
assert os.geteuid()==0
assert not (root/'started.json').exists()
with (root/'manager.stdout').open('xb') as out,(root/'manager.stderr').open('xb') as err:
    p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'board_entry.py')],
                       stdout=out,stderr=err,start_new_session=True)
result=dict(status='WEB_MANAGER_STARTED',pid=p.pid,root=str(root))
(root/'started.json').write_text(json.dumps(result))
print('__PL_BEGIN__');print(json.dumps(result));print('__PL_END__')
