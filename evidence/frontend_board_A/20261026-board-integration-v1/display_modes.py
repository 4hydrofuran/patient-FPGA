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
code="from gi.repository import Gio;import json;b=Gio.bus_get_sync(Gio.BusType.SESSION,None);r=b.call_sync('org.gnome.Mutter.DisplayConfig','/org/gnome/Mutter/DisplayConfig','org.gnome.Mutter.DisplayConfig','GetCurrentState',None,None,Gio.DBusCallFlags.NONE,5000,None);print(json.dumps(r.unpack()))"
p=subprocess.run(['runuser','-u','gdm','--','env',*[k+'='+v for k,v in env.items()],'/usr/bin/python3','-c',code],capture_output=True,text=True,timeout=8)
r={'rc':p.returncode,'state':p.stdout,'err':p.stderr,'drm':Path('/sys/kernel/debug/dri/0/state').read_text()[-3500:]}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
