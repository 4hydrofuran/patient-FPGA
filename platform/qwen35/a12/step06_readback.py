"""Wait/read back the one CPU window; no signals, device access or restoration."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import time

ROOT=Path('/var/lib/kv260-a12/step06-20261023-v1')


def main():
    assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
    for i in range(120):
        if (ROOT/'manager-exit.json').exists() or (ROOT/'run-v1/STOP.json').exists():break
        time.sleep(1)
    sys.path.insert(0,str(ROOT/'control'))
    from accelerator_release_gate_v2 import collect,require_no_users
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();scans=[]
    for i in range(4):
        s=collect(allow_ps_display=True)
        try:require_no_users(s,True,boot_id=boot);s['no_users_gate']=True
        except RuntimeError as e:s['no_users_gate']=False;s['gate_reason']=str(e)
        scans.append(s)
        if s['no_users_gate']:break
        time.sleep(.1)
    locktext=Path('/proc/locks').read_text();locks={}
    for p in (Path('/var/lock/kv260-a1/deployment.lock'),Path('/run/lock/patient-qwen-linear.lock')):
        st=p.stat();key=(os.major(st.st_dev),os.minor(st.st_dev),st.st_ino);rows=[]
        for line in locktext.splitlines():
            for part in line.split():
                if part.count(':')==2:
                    try:a,b,c=part.split(':');candidate=(int(a,16),int(b,16),int(c))
                    except ValueError:continue
                    if candidate==key:rows.append(line)
        locks[str(p)]=rows
    kr=subprocess.run(['dmesg','--raw'],capture_output=True,timeout=3);assert kr.returncode==0 and not kr.stderr
    gdm=subprocess.run(['systemctl','is-active','gdm'],capture_output=True,text=True,timeout=3)
    names=('manager-exit.json','manager-pid.json','manager.stdout.jsonl','manager.stderr.txt',
           'run-v1/STOP.json','run-v1/result.json','run-v1/worker-identity.json','run-v1/ready.json')
    state=dict(schema='A12_STEP06_INDEPENDENT_READBACK_V1',boot_id=boot,kernel=os.uname().release,
       files={n:(ROOT/n).read_text() for n in names if (ROOT/n).is_file()},
       scans=scans,locks=locks,active_lease_exists=Path('/var/lock/kv260-a1/active').exists(),
       module_present=Path('/sys/module/zocl').exists(),kernel_raw=kr.stdout.decode('utf-8'),
       kernel_sha256=hashlib.sha256(kr.stdout).hexdigest(),gdm_state=gdm.stdout.strip(),
       fpga_state=Path('/sys/class/fpga_manager/fpga0/state').read_text().strip(),
       overlays={p.name:(p/'status').read_text().strip() for p in Path('/sys/kernel/config/device-tree/overlays').iterdir() if p.is_dir()},
       temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')],
       memory_raw=Path('/proc/meminfo').read_text())
    if (ROOT/'manager-exit.json').exists():
        package=ROOT/'readback-v1.tar.gz'
        with package.open('xb') as stream:
            with tarfile.open(fileobj=stream,mode='w:gz',compresslevel=1) as tar:
                for p in sorted((ROOT/'run-v1').rglob('*')):
                    if p.is_file():tar.add(p,arcname=p.relative_to(ROOT).as_posix(),recursive=False)
                for name in ('manager-exit.json','manager-pid.json','manager.stdout.jsonl','manager.stderr.txt','ldd.txt','deployment-manifest.json'):
                    tar.add(ROOT/name,arcname=name,recursive=False)
        h=hashlib.sha256()
        with package.open('rb') as f:
            for block in iter(lambda:f.read(1048576),b''):h.update(block)
        state['package']=dict(path=str(package),bytes=package.stat().st_size,sha256=h.hexdigest())
        os.chmod(package,0o644) # no credentials/private user data; synthetic test evidence only
        public=Path('/home/ubuntu/a12-step06-readback-20261023-v1.tar.gz')
        with public.open('xb') as out,package.open('rb') as src:
            import shutil
            shutil.copyfileobj(src,out,1048576)
        os.chown(public,1000,1000);os.chmod(public,0o600);state['package']['download']=str(public)
    print(json.dumps(state),flush=True)


if __name__=='__main__':main()
