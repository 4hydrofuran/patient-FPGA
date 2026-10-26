import json,subprocess
from pathlib import Path
root=Path('/var/lib/kv260-a12/gui-qa-20261026-v2')
assert not (root/'started.json').exists()
with (root/'manager.stdout').open('xb') as out,(root/'manager.stderr').open('xb') as err:
    p=subprocess.Popen(['/usr/bin/python3','-B','-I',str(root/'interactive_entry.py')],stdout=out,stderr=err,start_new_session=True)
r=dict(status='MANUAL_WEB_STARTING',pid=p.pid)
(root/'started.json').write_text(json.dumps(r))
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
