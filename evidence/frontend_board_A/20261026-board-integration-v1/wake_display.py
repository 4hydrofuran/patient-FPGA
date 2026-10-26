import json,os,subprocess
from pathlib import Path
env=None
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        try:
            if (p/'comm').read_text().strip()=='gnome-shell' and p.stat().st_uid==114:
                values=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
                env={k:values[k] for k in ('DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR') if k in values}
        except (FileNotFoundError,PermissionError):pass
assert env is not None,'No login-screen compositor'
def run(args):
    p=subprocess.run(['runuser','-u','gdm','--','env',*[k+'='+v for k,v in env.items()],*args],capture_output=True,text=True,timeout=8)
    return dict(rc=p.returncode,out=p.stdout,err=p.stderr)
base=['gdbus','call','--session','--dest','org.gnome.Mutter.DisplayConfig','--object-path','/org/gnome/Mutter/DisplayConfig','--method']
r={'before':run(base+['org.freedesktop.DBus.Properties.Get','org.gnome.Mutter.DisplayConfig','PowerSaveMode'])}
r['wake']=run(base+['org.freedesktop.DBus.Properties.Set','org.gnome.Mutter.DisplayConfig','PowerSaveMode','<int32 0>'])
r['after']=run(base+['org.freedesktop.DBus.Properties.Get','org.gnome.Mutter.DisplayConfig','PowerSaveMode'])
r['dpms']=Path('/sys/class/drm/card0-DP-1/dpms').read_text()
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
