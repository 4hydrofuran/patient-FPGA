"""Generate one exact archive stage, only into new root-owned directories."""
import json
from common import ROOT,save
from step06_prepare import OUT


if __name__=='__main__':
    up=json.loads((OUT/'UPLOAD.json').read_text());manifest=json.loads((OUT/'deployment-manifest.json').read_text())
    body='''import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
expected=EXPECTED
archive=Path(expected['remote_upload'])
assert os.geteuid()==0 and os.uname().machine=='aarch64' and os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()==MACHINE
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert archive.stat().st_size==expected['bytes']
h=hashlib.sha256()
with archive.open('rb') as f:
 for block in iter(lambda:f.read(1048576),b''):h.update(block)
assert h.hexdigest()==expected['sha256'],'uploaded archive hash differs'
root=Path('/var/lib/kv260-a12/step06-20261023-v1');assets=Path('/opt/patient-qwen')
assert not os.path.lexists(root) and not os.path.lexists(assets),'refuse existing roots'
for p in (Path('/opt'),Path('/var/lib')):
 st=p.lstat();assert p.is_dir() and not p.is_symlink() and st.st_uid==0 and not st.st_mode&0o022
with tarfile.open(archive,'r') as tar:
 members=tar.getmembers();assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
 assert len({m.name for m in members})==len(members)
 raw=tar.extractfile('deployment-manifest.json').read()
 assert hashlib.sha256(raw).hexdigest()==expected['manifest_sha256']
 m=json.loads(raw);assert set(x.name for x in members)==set(m['files'])|{'deployment-manifest.json','kernel-baseline.raw.txt'}
 for name,row in m['files'].items():
  f=tar.extractfile(name);h=hashlib.sha256();size=0
  for b in iter(lambda:f.read(1048576),b''):h.update(b);size+=len(b)
  assert size==row['bytes'] and h.hexdigest()==row['sha256'],name
 baseline=tar.extractfile('kernel-baseline.raw.txt').read();assert hashlib.sha256(baseline).hexdigest()==m['kernel_baseline_sha256']
 os.umask(0o077);root.parent.mkdir(mode=0o700,exist_ok=True);root.mkdir(mode=0o700);assets.mkdir(mode=0o700)
 for member in members:
  target=(assets/member.name[len('assets/'):]) if member.name.startswith('assets/') else root/member.name
  target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with target.open('xb') as f:shutil.copyfileobj(tar.extractfile(member),f,1048576)
  if member.name in m['files']:
   assert hashlib.sha256(target.read_bytes()).hexdigest()==m['files'][member.name]['sha256']
 os.chmod(root/'runtime/qwen35-a12',0o700)
 env=dict(os.environ,LD_LIBRARY_PATH=str(root/'runtime'));env.pop('SP_A12_CONFIG',None)
 r=subprocess.run(['/usr/bin/ldd',str(root/'runtime/qwen35-a12')],env=env,capture_output=True,text=True,timeout=10)
 assert r.returncode==0 and 'not found' not in r.stdout and 'libxrt_' not in r.stdout,(r.stdout,r.stderr)
 (root/'ldd.txt').write_text(r.stdout)
 print(json.dumps(dict(status='CPU_ONLY_ASSETS_STAGED',files=len(m['files']),root=str(root),assets=str(assets),ldd=r.stdout,PL_submissions=0)),flush=True)
'''
    body=body.replace('expected=EXPECTED','expected='+repr(up)).replace('==BOOT','=='+repr(manifest['boot_id'])).replace('==MACHINE','=='+repr(manifest['machine_sha256']))
    (OUT/'stage_reviewed.py').write_text(body,encoding='utf-8')
    print('Exact stage generated; no board contact')
