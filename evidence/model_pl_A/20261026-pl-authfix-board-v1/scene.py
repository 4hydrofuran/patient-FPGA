import hashlib,json,os,subprocess
from pathlib import Path
p=Path('/var/lock/kv260-a1/active/lease.json')
files={}
for name in ('/boot/firmware/image.fit','/boot/firmware/boot.scr.uimg','/boot/firmware/a10-candidate-irq2-20261021.fit'):
 q=Path(name);files[name]=hashlib.sha256(q.read_bytes()).hexdigest()
over=Path('/sys/kernel/config/device-tree/overlays')
print('__PL_BEGIN__')
print(json.dumps(dict(boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=os.uname().release,
 machine=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),
 lease=json.loads(p.read_text()) if p.exists() else None,lease_sha=hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,
 zocl=Path('/sys/module/zocl').exists(),overlays={d.name:(d/'status').read_text().strip() for d in over.iterdir() if d.is_dir()},
 files=files,addresses=subprocess.check_output(['ip','-j','-4','addr','show','dev','eth0'],text=True),
 links={n:os.readlink('/lib/firmware/'+n) if Path('/lib/firmware/'+n).is_symlink() else Path('/lib/firmware/'+n).exists() for n in ('a11-mlp.dtbo','a11-mlp.bit.bin')})))
print('__PL_END__')
