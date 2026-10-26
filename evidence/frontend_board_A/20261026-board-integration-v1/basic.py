import json,os,subprocess
from pathlib import Path
def cmd(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=5)
    return dict(rc=p.returncode,out=p.stdout[:2500],err=p.stderr[:500])
r=dict(kernel=os.uname().release,boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),active=Path('/var/lock/kv260-a1/active').exists(),zocl=Path('/sys/module/zocl').exists())
r['sudo']=cmd(['sudo','-n','true'])
r['addresses']=cmd(['ip','-4','-br','addr','show','eth0'])
r['listeners']=cmd(['ss','-ltn'])
r['front']=Path('/home/ubuntu/patient-web-demo-20261026/web_gateway/src/patient_web/managed.py').is_file()
print('__FRONTEND_'+'BEGIN__');print(json.dumps(r));print('__FRONTEND_'+'END__')
