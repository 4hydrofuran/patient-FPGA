import json,subprocess,shutil
from pathlib import Path
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return dict(rc=p.returncode,out=p.stdout[-14000:],err=p.stderr[:500])
r={'shell_log':run(['journalctl','-b','_UID=114','-n','55','--no-pager']),
   'kernel_tail':run(['dmesg','--raw','--level=err,warn']),
   'drm_debug_files':[str(p) for p in Path('/sys/kernel/debug/dri/0').glob('*')],
   'tools':{n:shutil.which(n) for n in ('modetest','xrandr','xset','gnome-session-inhibit')},
   'uinput':Path('/dev/uinput').exists(),
   'vt':Path('/sys/class/tty/tty0/active').read_text()}
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
