import fcntl,hashlib,json,os,sys
from pathlib import Path
assert os.geteuid()==0
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='c995ba67-1bac-41e7-9f63-e14e9ca2e6a1'
assert not Path('/sys/module/zocl').exists()
assert (Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip())=='applied'
central=Path('/var/lock/kv260-a1');active=central/'active'
raw=(active/'lease.json').read_bytes()
pin='85256eddb0a760a18e1a6bd4f645f90e87468f50fdef5278e2a3d41c631aa897'
assert hashlib.sha256(raw).hexdigest()==pin
lease=json.loads(raw);assert lease['window']=='a12-original-pl-20261026-v1'
assert lease['identity'].endswith(':8a0276fb-86d1-4ef8-b067-adcc903a999a') and not lease['identity'].endswith(':'+boot)
sys.path.insert(0,'/var/lib/kv260-a12/original-pl-20261026-v1/bundle/control/support')
from accelerator_release_gate_v2 import collect,require_no_users
fds=[]
try:
 for name in (central/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock')):
  fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600);fds.append(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=boot)
 dest=central/'history/a12-original-pl-20261026-v1-after-poweroff-authfix-v1'
 assert not dest.exists() and hashlib.sha256((active/'lease.json').read_bytes()).hexdigest()==pin
 active.rename(dest)
 result=dict(status='PRIOR_BOOT_FAILURE_ARCHIVED',current_boot=boot,old_lease_sha256=pin,archive=str(dest),normal_old_worker_exit=False,scan=scan)
 with (dest/'recovery-after-poweroff.json').open('x') as f:json.dump(result,f);f.flush();os.fsync(f.fileno())
 for folder in (central,central/'history'):
  fd=os.open(folder,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 print('__PL_BEGIN__');print(json.dumps(dict(status=result['status'],archive=str(dest),lease_sha256=pin,scan_complete=scan['scan_complete'])));print('__PL_END__')
finally:
 for fd in fds:os.close(fd)
