import json,os,subprocess
from pathlib import Path
r={}
for argv in (['loginctl','list-sessions','--no-legend'],['systemctl','is-active','gdm'],['ps','-eo','pid,uid,comm'],['cat','/var/lib/kv260-a12/manual-web-20261026-v3/ime-install-result.json']):
    p=subprocess.run(argv,capture_output=True,text=True,timeout=5)
    out=p.stdout
    if argv[0]=='ps':out='\n'.join(l for l in out.splitlines() if any(s in l for s in ('gnome','gsd','firefox','ibus','Xorg','gdm')))
    r[str(argv)]=dict(exit=p.returncode,stdout=out,stderr=p.stderr)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
