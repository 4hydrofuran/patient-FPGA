import json,subprocess
from pathlib import Path
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return {'rc':p.returncode,'out':p.stdout[:8000],'err':p.stderr[:1000]}
r={'gdm':run(['systemctl','is-active','gdm']),
   'sessions':run(['loginctl','list-sessions','--no-legend']),
   'displays':{str(p):p.read_text().strip() for p in Path('/sys/class/drm').glob('card*-*/status')},
   'user_processes':run(['ps','-u','ubuntu','-o','pid,comm']),
   'active_lease':Path('/var/lock/kv260-a1/active').exists()}
print('__FRONTEND_'+'BEGIN__');print(json.dumps(r));print('__FRONTEND_'+'END__')
