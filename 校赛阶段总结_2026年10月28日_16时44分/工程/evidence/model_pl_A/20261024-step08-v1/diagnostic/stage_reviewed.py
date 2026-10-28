import hashlib,json,os,shutil,subprocess,tarfile
from pathlib import Path
up={'bytes': 25272320, 'sha256': 'd54b5aa6f5f161717df4e510ecc551271e753e493e658e7ca32d080280964ed9', 'manifest_sha256': '6291710c7c9d33e66b919f73bb5c0a5d37093e2927737c7d887ede78563d3b7a', 'remote_upload': '/home/ubuntu/a12-step08-diagnostic-20261024-v1.tar', 'root': '/var/lib/kv260-a12/step08-diagnostic-20261024-v1'}
root=Path(up['root']);archive=Path(up['remote_upload'])
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='86e4938b-0f65-4166-9237-c547b67e1451'
assert not Path('/sys/module/zocl').exists() and not Path('/var/lock/kv260-a1/active').exists()
assert not os.path.lexists(root)
assert archive.stat().st_size==up['bytes'] and hashlib.sha256(archive.read_bytes()).hexdigest()==up['sha256']
os.umask(0o077)
with tarfile.open(archive) as tar:
 members=tar.getmembers();assert len(members)==len({m.name for m in members})
 assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
 raw=tar.extractfile('manifest.json').read();assert hashlib.sha256(raw).hexdigest()==up['manifest_sha256']
 manifest=json.loads(raw);assert {m.name for m in members}=={r['path'] for r in manifest['files']}|{'manifest.json'}
 for r in manifest['files']:
  data=tar.extractfile(r['path']).read();assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
 root.mkdir(mode=0o700)
 for m in members:
  dest=root/m.name;dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with dest.open('xb') as f:shutil.copyfileobj(tar.extractfile(m),f)
 os.chmod(root/'bin/qwen35-a12',0o700)
 env={k:v for k,v in os.environ.items() if not k.startswith(('SP_A12','LD_'))};env['LD_LIBRARY_PATH']=str(root/'bin')
 r=subprocess.run(['ldd',str(root/'bin/qwen35-a12')],env=env,capture_output=True,text=True,timeout=10)
 assert r.returncode==0 and 'not found' not in r.stdout and 'libxrt_' not in r.stdout
 (root/'ldd.txt').write_text(r.stdout)
print(json.dumps(dict(status='CAPACITY_ONLY_NEW_BUNDLE_STAGED_NO_PL_MUTATION',root=str(root),files=len(manifest['files']))),flush=True)
