import json,hashlib,base64,os
from pathlib import Path
old=Path('/var/lib/kv260-a11/a11-mlp-20261023-v1');new=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8422f92f-d01f-4849-ad19-6e66b640a9ad'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert not os.path.lexists('/var/lock/kv260-a1/active') and not Path('/sys/module/zocl').exists()
assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
assert hashlib.sha256((old/'manifest.json').read_bytes()).hexdigest()=='3b3c46700f92565839abda962e07e557018b8fd1be9e7846613ff46ecf89f11c'
import gzip
patch=Path('/home/ubuntu/a11-compute-patch-20261023-v1/patch.json.gz').read_bytes()
assert hashlib.sha256(patch).hexdigest()=='f4ea1795327e489d3c65b9089e3ff88cab903c87f05869ff1b4cec7bb184b234'
payload=json.loads(gzip.decompress(patch))
manifest=base64.b64decode(payload['manifest.json']);assert hashlib.sha256(manifest).hexdigest()=='5c1a3ee720606351bd38fd5f90579c5fa843a85d64b3683daa5c50224ec58846'
m=json.loads(manifest);previous=json.loads((old/'manifest.json').read_bytes())
os.umask(0o077);new.mkdir(mode=0o700)
for name,e in m['files'].items():
 if name in payload:data=base64.b64decode(payload[name])
 else:
  assert previous['files'][name]==e
  data=(old/name).read_bytes()
 assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256']
 target=new/name;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
 with target.open('xb') as f:f.write(data)
for name in ('manifest.json','launch_mlp_once.py'):
 with (new/name).open('xb') as f:f.write(base64.b64decode(payload[name]))
print(json.dumps(dict(status='STAGED_NOT_EXECUTED',manifest_sha256='5c1a3ee720606351bd38fd5f90579c5fa843a85d64b3683daa5c50224ec58846')))
