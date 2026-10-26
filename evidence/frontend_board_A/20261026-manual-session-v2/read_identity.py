import json,os,subprocess
from pathlib import Path
r=dict(kernel=os.uname().release,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),active_lease=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
p=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=4);r['gdm']=p.stdout.strip()
r['overlays']={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir()}
r['desktop_logged_in']=any(p.stat().st_uid==1000 and (p/'comm').read_text().strip()=='gsd-power' for p in Path('/proc').iterdir() if p.name.isdigit() and (p/'comm').exists())
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
