import json,base64,subprocess
from pathlib import Path
shots=Path.home()/'snap/firefox/common/frontend-check-20261026-v1'
r={'screenshots':{n:base64.b64encode((shots/n).read_bytes()).decode() for n in ('ready.png','answered.png','evaluation.png')}}
for name,args in {'listeners':['ss','-ltnp'],'user_processes':['ps','-u','ubuntu','-o','pid,ppid,etimes,comm']}.items():
    p=subprocess.run(args,capture_output=True,text=True,timeout=5)
    r[name]={'rc':p.returncode,'out':p.stdout,'err':p.stderr}
r['owned_processes_remaining']=[pid for pid in (6117,6124,6343,6350,6864,6867) if (Path('/proc')/str(pid)).exists()]
print('__FRONTEND_'+'BEGIN__',flush=True)
print(json.dumps(r),flush=True)
print('__FRONTEND_'+'END__',flush=True)
