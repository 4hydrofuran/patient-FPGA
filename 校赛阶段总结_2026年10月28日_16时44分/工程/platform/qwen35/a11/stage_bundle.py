"""Root-only additive copy of a pinned A11 bundle; no PL or native calls."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import uuid

SOURCE=Path('/home/ubuntu/a11-mlp-20261023-v1')
TARGET=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1')
PIN='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
MACHINE='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise RuntimeError(reason)


def stage(boot):
    need(str(uuid.UUID(boot))==boot and os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2' and
         os.uname().machine=='aarch64','wrong platform')
    need(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot and sha(Path('/etc/machine-id'))==MACHINE,'wrong identity')
    need(not Path('/sys/module/zocl').exists() and not os.path.lexists('/var/lock/kv260-a1/active'),'active maintenance')
    need(Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied','not default')
    need(not os.path.lexists(TARGET) and not SOURCE.is_symlink() and sha(SOURCE/'manifest.json')==PIN,'target/pin differs')
    man=json.loads((SOURCE/'manifest.json').read_text())
    need(man['schema']=='A11_MLP_BUNDLE_V1' and man['authorization_included'] is False and
         man['board_accepted'] is False and man['max_submissions']==23,'wrong manifest')
    files=dict(man['files']);files['manifest.json']=dict(bytes=(SOURCE/'manifest.json').stat().st_size,sha256=PIN)
    all_paths=list(SOURCE.rglob('*'))
    need(all(not p.is_symlink() for p in all_paths),'symlink payload')
    need({str(p.relative_to(SOURCE)) for p in all_paths if p.is_file()}==set(files),'payload inventory differs')
    for name,meta in files.items():
        need(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name,'unsafe name')
        p=SOURCE/name;s=p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_uid==1000 and s.st_size==meta['bytes'] and sha(p)==meta['sha256'],'bad source '+name)
    temps=[int(p.read_text()) for p in Path('/sys/class/hwmon').glob('hwmon*/temp*_input')]
    need(temps and all(0<t<55000 for t in temps),'temperature')
    need(shutil.disk_usage('/var/lib').free>128*1024*1024,'disk reserve')
    os.umask(0o077)
    if not TARGET.parent.exists():TARGET.parent.mkdir(mode=0o700)
    info=TARGET.parent.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid==0 and not info.st_mode&0o022,'untrusted parent')
    TARGET.mkdir(mode=0o700)
    for name,meta in files.items():
        target=TARGET/name;target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with (SOURCE/name).open('rb') as a,target.open('xb') as b:
            shutil.copyfileobj(a,b,1024*1024);b.flush();os.fsync(b.fileno())
        need(sha(target)==meta['sha256'],'copy mismatch')
    return dict(status='ROOT_BUNDLE_STAGED_NOT_EXECUTED',boot_id=boot,files=len(files),manifest_sha256=PIN,
                target=str(TARGET),pl_loads=0,compute_runs=0)


if __name__=='__main__':
    need(len(sys.argv)==2,'exact boot required');print(json.dumps(stage(sys.argv[1])))
