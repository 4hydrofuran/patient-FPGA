import json,subprocess
from pathlib import Path
env={}
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        try:
            if (p/'comm').read_text().strip()=='gnome-shell' and p.stat().st_uid==114:
                values=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
                env={k:values[k] for k in ('DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR') if k in values}
        except (FileNotFoundError,PermissionError):pass
code="""from gi.repository import Gio,GLib
import json
b=Gio.bus_get_sync(Gio.BusType.SESSION,None)
def call(dest,path,iface,method,args):
 return b.call_sync(dest,path,iface,method,args,None,Gio.DBusCallFlags.NONE,5000,None).unpack()
d='org.gnome.Mutter.DisplayConfig';p='/org/gnome/Mutter/DisplayConfig'
s=call(d,p,d,'GetCurrentState',None)
a=GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})',(s[0],1,[(0,0,1.0,0,True,[('DP-1','800x600@60.317',{})])],{}))
r={'mode':call(d,p,d,'ApplyMonitorsConfig',a)}
try:r['saver']=call('org.gnome.ScreenSaver','/org/gnome/ScreenSaver','org.gnome.ScreenSaver','SetActive',GLib.Variant('(b)',(False,)))
except Exception as e:r['saver_error']=str(e)
r['wake']=call(d,p,'org.freedesktop.DBus.Properties','Set',GLib.Variant('(ssv)',(d,'PowerSaveMode',GLib.Variant('i',0))))
print(json.dumps(r))
"""
p=subprocess.run(['runuser','-u','gdm','--','env',*[k+'='+v for k,v in env.items()],'/usr/bin/python3','-c',code],capture_output=True,text=True,timeout=20)
r={'rc':p.returncode,'out':p.stdout,'err':p.stderr,'dpms':Path('/sys/class/drm/card0-DP-1/dpms').read_text()}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
