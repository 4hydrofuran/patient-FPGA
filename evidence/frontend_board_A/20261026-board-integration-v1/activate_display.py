import json,subprocess
def cmd(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=10)
    return dict(rc=p.returncode,out=p.stdout,err=p.stderr)
r={'start_graphics':cmd(['systemctl','start','gdm']),
   'activate_screen':cmd(['loginctl','activate','c3']),
   'session':cmd(['loginctl','show-session','c3','-p','Active','-p','Name','-p','Type','-p','VTNr'])}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
