import base64,hashlib,json
from pathlib import Path
E=Path(__file__).resolve().parent
raw=(E/'bundle-v2/manifest.json').read_bytes();pin=hashlib.sha256(raw).hexdigest()
oldpin=hashlib.sha256((E/'bundle-v1/manifest.json').read_bytes()).hexdigest()
launch=(E/'launch_mlp_v2.py').read_text().replace('a11-mlp-20261023-v2','a11-mlp-20261023-v3').replace(oldpin,pin)
(E/'launch_mlp_v3.py').write_bytes(launch.encode())
payload={n:base64.b64encode(b).decode() for n,b in [('manifest.json',raw),('launch_mlp_once.py',launch.encode())]}
script='''import base64,hashlib,json,os
from pathlib import Path
old=Path('/var/lib/kv260-a11/a11-mlp-20261023-v2');new=Path('/var/lib/kv260-a11/a11-mlp-20261023-v3')
assert os.geteuid()==0 and not os.path.lexists('/var/lock/kv260-a1/active') and not Path('/sys/module/zocl').exists()
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='8422f92f-d01f-4849-ad19-6e66b640a9ad'
assert json.loads((old/'host-exit.json').read_bytes())['exit_code']==1
assert not (old/'attempt.json').exists() and not (old/'native-attempt.json').exists() and not (old/'review.json').exists()
assert hashlib.sha256((old/'manifest.json').read_bytes()).hexdigest()==OLDPIN
payload=PAYLOAD;m=json.loads(base64.b64decode(payload['manifest.json']))
os.umask(0o077);new.mkdir(mode=0o700)
for n,e in m['files'].items():
 p=(Path('/var/lib/kv260-a11/a11-mlp-20261023-v1') if n=='vectors/manifest.json' else old)/n
 b=p.read_bytes();assert len(b)==e['bytes'] and hashlib.sha256(b).hexdigest()==e['sha256']
 target=new/n;target.parent.mkdir(mode=0o700,exist_ok=True,parents=True)
 with target.open('xb') as f:f.write(b)
for n in ('manifest.json','launch_mlp_once.py'):
 with (new/n).open('xb') as f:f.write(base64.b64decode(payload[n]))
assert hashlib.sha256((new/'manifest.json').read_bytes()).hexdigest()==NEWPIN
print(json.dumps(dict(status='STAGED_NOT_EXECUTED',manifest_sha256=NEWPIN)))
'''.replace('OLDPIN',repr(oldpin)).replace('NEWPIN',repr(pin)).replace('PAYLOAD',repr(payload))
(E/'stage_v3.py').write_bytes(script.encode())
(E/'start_v3.py').write_bytes((E/'start_v2.py').read_text().replace('a11-mlp-20261023-v2','a11-mlp-20261023-v3').encode())
print(json.dumps(dict(manifest_sha256=pin)))
