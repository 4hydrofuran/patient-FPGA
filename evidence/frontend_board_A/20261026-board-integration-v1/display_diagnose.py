import json,subprocess
from pathlib import Path
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return dict(rc=p.returncode,out=p.stdout[-8000:],err=p.stderr[:500])
r={}
for name in ('status','enabled','dpms','modes','edid'):
    p=Path('/sys/class/drm/card0-DP-1')/name
    if p.exists():r[name]=len(p.read_bytes()) if name=='edid' else p.read_text()
for name in ('/sys/kernel/debug/dri/0/state','/sys/class/graphics/fb0/blank'):
    p=Path(name)
    if p.exists():r[name]=p.read_text()[-10000:]
r['gdm_log']=run(['journalctl','-b','-u','gdm','-n','25','--no-pager'])
r['display_log']=run(['sh','-c','dmesg | grep -Ei "drm|displayport|dp-1|xilinx-dp|link.train|edid" | tail -30'])
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
