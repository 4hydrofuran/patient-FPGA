import json,subprocess,sys,time
from pathlib import Path
root=Path('/var/lib/kv260-a12/manual-web-20261026-v4')
sys.path.insert(0,str(root))
from interactive_case import desktop_environment
env=desktop_environment();base=['runuser','-u','ubuntu','--','env',*[k+'='+v for k,v in env.items()]]
result=[]
commands=[['gsettings','set','org.gnome.desktop.input-sources','sources',"[('ibus', 'libpinyin'), ('xkb', 'us')]"],
 ['gsettings','set','org.gnome.desktop.input-sources','mru-sources',"[('ibus', 'libpinyin'), ('xkb', 'us')]"],
 ['gsettings','set','org.gnome.desktop.a11y.applications','screen-keyboard-enabled','true'],
 ['ibus-daemon','--daemonize','--replace','--xim','--panel=disable']]
for argv in commands:
    p=subprocess.run(base+argv,capture_output=True,text=True,timeout=8)
    result.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr));assert p.returncode==0
time.sleep(1)
for argv in (['ibus','engine','libpinyin'],['ibus','engine'],['gsettings','get','org.gnome.desktop.input-sources','sources'],['gsettings','get','org.gnome.desktop.a11y.applications','screen-keyboard-enabled']):
    p=subprocess.run(base+argv,capture_output=True,text=True,timeout=8)
    result.append(dict(argv=argv,exit=p.returncode,stdout=p.stdout,stderr=p.stderr))
(root/'ime-configured.json').write_text(json.dumps(result))
print('__PL_BEGIN__');print(json.dumps(result));print('__PL_END__')
