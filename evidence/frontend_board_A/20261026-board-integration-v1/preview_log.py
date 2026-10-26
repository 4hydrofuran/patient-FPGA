import json
from pathlib import Path
r={'log':Path('/home/ubuntu/snap/firefox/common/hdmi-preview.log').read_text(errors='replace')[-2500:],'desktop_env':{}}
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        try:
            comm=(p/'comm').read_text().strip()
            if comm in ('gnome-shell','gsd-power','gsd-media-keys') and p.stat().st_uid==1000:
                values=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
                r['desktop_env'][comm]={k:values[k] for k in ('DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY') if k in values}
        except (FileNotFoundError,PermissionError):pass
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
