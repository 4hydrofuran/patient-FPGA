import os,json,subprocess,shutil
from pathlib import Path
def run(argv):
    try:
        p=subprocess.run(argv,capture_output=True,text=True,timeout=8)
        return dict(rc=p.returncode,out=p.stdout[:20000],err=p.stderr[:1000])
    except Exception as e:return dict(error=str(e))
r=dict(host=os.uname().nodename,kernel=os.uname().release,boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
r['processes']=run(['ps','-eo','pid,ppid,etimes,comm'])
r['locks']=Path('/proc/locks').read_text()
r['lock_files']=[]
for base in ('/var/lock/kv260-a1','/run/lock'):
    for p in Path(base).glob('*'):
        if p.is_file():
            s=p.stat();r['lock_files'].append(dict(path=str(p),inode=s.st_ino,device=s.st_dev))
r['listeners']=run(['ss','-ltnp'])
r['browser_paths']={n:shutil.which(n) for n in ('firefox','chromium','chromium-browser','google-chrome','epiphany','cog','xdg-open')}
r['packages']=run(['dpkg-query','-W','-f=${Package} ${Version} ${Status}\n','*firefox*','*chromium*','*epiphany*','*webkit*','*nginx*','*nodejs*','*python3-flask*'])
r['snap']=run(['snap','list']) if shutil.which('snap') else None
r['sessions']=run(['loginctl','list-sessions','--no-legend'])
r['home_top']=[p.name for p in Path.home().iterdir()]
r['units']=run(['systemctl','list-units','--type=service','--state=running','--no-pager','--no-legend'])
r['app_files']=run(['find','/home/ubuntu','/opt','/var/www','-maxdepth','4','-type','f','(','-name','package.json','-o','-name','index.html','-o','-name','app.py','-o','-name','server.py','-o','-name','README.md','-o','-name','*.desktop',')'])
print('__FRONTEND_'+'BEGIN__',flush=True)
print(json.dumps(r,ensure_ascii=False),flush=True)
print('__FRONTEND_'+'END__',flush=True)
