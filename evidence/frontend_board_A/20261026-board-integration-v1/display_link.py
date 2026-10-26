import json,subprocess
from pathlib import Path
def run(a):
    p=subprocess.run(a,capture_output=True,text=True,timeout=8)
    return dict(rc=p.returncode,out=p.stdout[-9000:],err=p.stderr[:1000])
r={'cmdline':Path('/proc/cmdline').read_text(),
   'dp_debug':[str(p) for p in Path('/sys/kernel/debug/dri/0/DP-1').rglob('*')],
   'aux_nodes':[str(p) for p in Path('/dev').glob('drm_dp_aux*')],
   'display_boot':run(['sh','-c','dmesg | grep -Ei "zynqmp.*dp|zynqmp.*display|drm|aux|edid|displayport|mst" | head -45']),
   'drm_driver':run(['readlink','-f','/sys/class/drm/card0/device/driver']),
   'edid_len':len(Path('/sys/class/drm/card0-DP-1/edid').read_bytes())}
for p in Path('/dev').glob('drm_dp_aux*'):
    try:
        with p.open('rb',buffering=0) as f:r[str(p)]=f.read(32).hex()
    except Exception as e:r[str(p)]=str(e)
print('__PL_BEGIN__');print(json.dumps(r));print('__PL_END__')
