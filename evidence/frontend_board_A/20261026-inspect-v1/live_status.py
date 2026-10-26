import json,subprocess,urllib.request,os
from pathlib import Path
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=5)
    return dict(rc=p.returncode,out=p.stdout,err=p.stderr)
r={'listeners':run(['ss','-ltnp']),'processes':run(['ps','-u','ubuntu','-o','pid,ppid,etimes,comm']),'locks':Path('/proc/locks').read_text()}
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/ui/v1/status',timeout=3) as f:r['status']=json.load(f)
except Exception as e:r['http_error']=str(e)
r['known_processes']={}
for pid in (6117,6124):
    p=Path('/proc')/str(pid)
    r['known_processes'][pid]=p.exists()
r['render_result_exists']=Path('/home/ubuntu/patient-web-demo-20261026/inspection-20261026-v1/render-result.json').exists()
print('__FRONTEND_'+'BEGIN__',flush=True)
print(json.dumps(r,ensure_ascii=True),flush=True)
print('__FRONTEND_'+'END__',flush=True)
