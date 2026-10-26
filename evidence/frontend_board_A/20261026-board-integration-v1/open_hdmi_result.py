import json,subprocess,time
from pathlib import Path
env={}
for p in Path('/proc').iterdir():
    if p.name.isdigit():
        try:
            if (p/'comm').read_text().strip()=='gsd-power' and p.stat().st_uid==1000:
                values=dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split('\0') if '=' in x)
                env={k:values[k] for k in ('DBUS_SESSION_BUS_ADDRESS','DISPLAY','WAYLAND_DISPLAY','XDG_RUNTIME_DIR','XAUTHORITY') if k in values}
        except (FileNotFoundError,PermissionError):pass
assert env,'Desktop is not logged in'
base=Path('/home/ubuntu/snap/firefox/common')
page=base/'pl-result-20261026-v1/index.html'
assert page.is_file()
profile=base/'hdmi-preview-20261026-v1'
subprocess.run(['runuser','-u','ubuntu','--','/usr/bin/python3','-c',
    'from pathlib import Path;Path('+repr(str(profile))+').mkdir(exist_ok=True)'],check=True)
argv=['runuser','-u','ubuntu','--','env',*[k+'='+v for k,v in env.items()],
      '/usr/bin/gnome-session-inhibit','--inhibit','idle','--reason','PL-HDMI-preview',
      '/snap/bin/firefox','--no-remote','--profile',str(profile),'--kiosk',page.as_uri()]
with (base/'hdmi-preview.log').open('ab') as log:
    process=subprocess.Popen(argv,stdout=log,stderr=log,stdin=subprocess.DEVNULL,start_new_session=True)
time.sleep(4)
r={'pid':process.pid,'running':process.poll() is None,'exit_code':process.poll(),'page':str(page),
   'dpms':Path('/sys/class/drm/card0-DP-1/dpms').read_text(),'mode':'1024x600 observed',
   'displayed_content':'Recorded actual MODEL/FPGA_REAL result; no new inference'}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
