"""Read-only bulk evidence over the already pinned board SSH connection."""
import base64
import gzip
import hashlib
from pathlib import Path
import sys
import argparse
import re

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
import fetch_single_result as transport

original=transport.plan
WINDOW='a11-open-20261023-v2'

def plan(cleanup=False):
    if cleanup: raise ValueError('read-only only')
    argv,_=original(False)
    code='''import os,json,sys,base64,zlib,hashlib,subprocess,time
from pathlib import Path
p=Path('/var/lib/kv260-a11/a11-open-20261023-v2');sys.path.insert(0,str(p))
from accelerator_release_gate_v2 import collect
assert os.geteuid()==0
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8422f92f-d01f-4849-ad19-6e66b640a9ad'
def pack(b):return dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),zlib_base64=base64.b64encode(zlib.compress(b)).decode())
names=('launcher-pid.json','host-exit.json','worker-result.json','worker.stderr.txt','host.stderr.txt','worker.stdout.jsonl','lifecycle.jsonl','mlp-receipt.json','review.json','trial-profile.json','native-attempt.json','worker-baseline.json','baseline.raw.txt','host.stdout.jsonl','STOP.json')
files={n:pack((p/n).read_bytes()) for n in names if (p/n).is_file()}
for output in sorted((p/'outputs').glob('job-*.f32')):
 assert not output.is_symlink()
 files['actual-'+output.name]=pack(output.read_bytes())
k=subprocess.run(['dmesg','--raw'],capture_output=True);assert k.returncode==0 and not k.stderr
locks=Path('/proc/locks').read_text().splitlines();matched={}
for n in ('/var/lock/kv260-a1/deployment.lock','/run/lock/patient-qwen-linear.lock'):
 s=Path(n).stat();key=f'{os.major(s.st_dev):02x}:{os.minor(s.st_dev):02x}:{s.st_ino}';matched[n]=[l for l in locks if key in l.split()]
r=dict(files=files,kernel_log=pack(k.stdout),active_lease=None,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,scan=collect(allow_ps_display=True),overlays={x.parent.name:x.read_text().strip() for x in Path('/sys/kernel/config/device-tree/overlays').glob('*/status')},fpga=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),gdm=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True).stdout.strip(),zocl=Path('/sys/module/zocl').exists(),active_lease_exists=os.path.lexists('/var/lock/kv260-a1/active'),locks=matched,temperatures=[int(x.read_text()) for x in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],read_monotonic_ns=time.monotonic_ns())
print(json.dumps(r))
'''
    code=code.replace('a11-open-20261023-v2',WINDOW)
    pin=hashlib.sha256(code.encode()).hexdigest()
    blob=base64.b64encode(gzip.compress(code.encode())).decode()
    argv[-1]='sudo -S -p '+transport.PROMPT.decode()+' /usr/bin/python3 -B -I -c "import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode(\''+blob+'\')); assert hashlib.sha256(b).hexdigest()==\''+pin+'\'; exec(compile(b,\'read_open_evidence\',\'exec\'))"'
    return argv,pin

if __name__=='__main__':
    ap=argparse.ArgumentParser(add_help=False);ap.add_argument('--window',default=WINDOW)
    args,remaining=ap.parse_known_args();WINDOW=args.window
    if not re.fullmatch(r'a11-(?:open|mlp)-20261023-v[1-9][0-9]*',WINDOW):raise ValueError('invalid window')
    sys.argv=[sys.argv[0],*remaining]
    transport.plan=plan
    raise SystemExit(transport.main())
