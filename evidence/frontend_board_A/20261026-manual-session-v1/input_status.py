import json,shutil,subprocess,sys
sys.path.insert(0,'/var/lib/kv260-a12/manual-web-20261026-v1')
from interactive_case import desktop_environment
env=desktop_environment();prefix=['runuser','-u','ubuntu','--','env',*[k+'='+v for k,v in env.items()]]
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return {'rc':p.returncode,'out':p.stdout[-3000:],'err':p.stderr[:500]}
r={'sources':run(prefix+['gsettings','get','org.gnome.desktop.input-sources','sources']),
   'osk':run(prefix+['gsettings','get','org.gnome.desktop.a11y.applications','screen-keyboard-enabled']),
   'ibus':shutil.which('ibus'),
   'pinyin':run(['dpkg-query','-W','-f=${Package} ${Status}\n','ibus-libpinyin','ibus-pinyin'])}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
