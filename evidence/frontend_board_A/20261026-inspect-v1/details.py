import os,json,subprocess
from pathlib import Path
def run(argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=10)
        return dict(rc=p.returncode,out=p.stdout[:16000],err=p.stderr[:1500])
    except Exception as e:return dict(error=str(e))
base=Path('/home/ubuntu/patient-web-demo-20261026')
r={}
r['files']=run(['find',str(base),'-maxdepth','4','-type','f','-not','-path','*/__pycache__/*'])
r['readme']=(base/'web_gateway/README.md').read_text()[:24000]
r['permissions']=run(['ls','-ld','/opt/patient-qwen','/var/lib/kv260-a12','/home/ubuntu/patient-web-demo-20261026'])
r['user_units']=run(['find','/home/ubuntu/.config/systemd','/home/ubuntu/.config/autostart','/home/ubuntu/Desktop','-maxdepth','3','-type','f'])
r['sudo_cached']=run(['sudo','-n','true'])
r['firefox_version']=run(['/snap/bin/firefox','--version'])
r['session_status']=run(['loginctl','show-session','c1','-p','Name','-p','State','-p','Type','-p','Display'])
r['network']=run(['ip','-4','route'])
print('__FRONTEND_'+'BEGIN__',flush=True)
print(json.dumps(r,ensure_ascii=False),flush=True)
print('__FRONTEND_'+'END__',flush=True)
