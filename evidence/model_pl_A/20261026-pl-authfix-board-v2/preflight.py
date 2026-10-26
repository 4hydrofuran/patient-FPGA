"""Fresh ordinary PL binding, using the unchanged frozen workload and gates."""
import hashlib,json,os,shutil,subprocess,sys,urllib.request,zipfile
from pathlib import Path
ROOT=Path('/var/lib/kv260-a12/pl-authfix-20261026-v2')
assert os.geteuid()==0 and os.uname().release=='6.8.12-a10irq2'
assert hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()=='ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'
assert not Path('/sys/module/zocl').exists()
ROOT.mkdir(mode=0o700)
archive=ROOT/'bundle-fixed.zip'
with urllib.request.urlopen('http://192.168.2.1:8765/bundle.zip',timeout=30) as incoming, archive.open('xb') as target:
 while True:
  block=incoming.read(65536)
  if not block:break
  target.write(block)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='fe8541f0840e40f2c10d28874af13af8e27f4f4cfb9557184f2f33199145f179'
bundle=ROOT/'bundle';bundle.mkdir(mode=0o700)
with zipfile.ZipFile(archive) as z:z.extractall(bundle)
sys.path.insert(0,str(bundle/'platform/qwen35/a12'))
sys.path.insert(0,str(bundle/'control/support'))
from resource_probe_policy import validate_plan
from accelerator_release_gate_v2 import collect,require_no_users
from kernel_log_gate import diagnostics
boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=boot)
central=Path('/var/lock/kv260-a1');active=central/'active'
if active.exists():
 import fcntl
 raw_lease=(active/'lease.json').read_bytes();old=json.loads(raw_lease)
 assert old['window']=='a12-pl-authfix-20261026-v1'
 assert old['identity'].endswith(':0978088a-8d10-45b2-8f43-726d00209313') and not old['identity'].endswith(':'+boot)
 assert {d.name:(d/'status').read_text().strip() for d in Path('/sys/kernel/config/device-tree/overlays').iterdir() if d.is_dir()}=={'k26-starter-kits_image_1':'applied'}
 descriptors=[]
 try:
  for name in (central/'deployment.lock',Path('/run/lock/patient-qwen-linear.lock')):
   fd=os.open(name,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600);descriptors.append(fd);fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
  dest=central/'history/a12-pl-authfix-20261026-v1-priorboot-recovery'
  assert not dest.exists() and (active/'lease.json').read_bytes()==raw_lease
  active.rename(dest)
  recovery=dict(old_lease_sha256=hashlib.sha256(raw_lease).hexdigest(),old_boot=old['identity'],current_boot=boot,normal_old_worker_exit=False,scan=scan)
  (ROOT/'prior-boot-recovery.json').write_text(json.dumps(recovery))
  for directory in (central,central/'history'):
   fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
 finally:
  for fd in descriptors:os.close(fd)
assert not active.exists()

lock=Path('/run/lock/patient-qwen-linear.lock')
if not lock.exists():
 with lock.open('xb'):pass
 lock.chmod(0o600)
binding=urllib.request.urlopen('http://192.168.2.1:8765/binding.py',timeout=15).read(16384)
namespace={};exec(compile(binding,'reviewed_resource_probe_binding','exec'),namespace)
spec=json.loads((bundle/'control/window-spec.json').read_text())
requests=json.loads((bundle/'control/requests.json').read_text())
spec=namespace['bind_workload'](requests,spec,window_id='a12-pl-authfix-20261026-v2')
assert validate_plan(requests,spec)==3024 and spec['authorization_included'] is False
(bundle/'control/window-spec.json').write_text(json.dumps(spec,indent=2))
(ROOT/'binding-source.py').write_bytes(binding)
(bundle/'platform/qwen35/a12/resource_probe_binding.py').write_bytes(binding)
# Existing firmware-file refusal remains. Preserve the known stale DTBO by rename.
history=ROOT/'precompute-staging-history';history.mkdir(mode=0o700)
for name in ('a11-mlp.dtbo','a11-mlp.bit.bin'):
 p=Path('/lib/firmware')/name
 if os.path.lexists(p):
  assert not p.is_symlink() and hashlib.sha256(p.read_bytes()).digest()==hashlib.sha256((bundle/'hardware'/name).read_bytes()).digest()
  p.rename(history/name)
raw=subprocess.check_output(['dmesg','--raw']).decode()
baseline=hashlib.sha256(raw.encode()).hexdigest()
(bundle/'control/preflight.json').write_text(json.dumps(dict(boot_id=boot,kernel_raw=raw,kernel_sha256=baseline)))
(bundle/'control/activation.json').write_text(json.dumps(dict(status='BOUND_TO_USER_PL_ACCEPTANCE',execution_enabled=True,authorization_included=False)))
authorization=dict(user_request='修复授权字段并重新进行实际PL验收，不额外增加安全检查',boot_id=boot,kernel=os.uname().release,
 window_id=spec['window_id'],authorized_compute=True,max_runs=5000,max_loads=72,max_session_seconds=spec['max_session_seconds'],
 no_heavy_diagnostics=True,original_bundle_sha256='fe8541f0840e40f2c10d28874af13af8e27f4f4cfb9557184f2f33199145f179')
(ROOT/'authorization.json').write_text(json.dumps(authorization,ensure_ascii=False,indent=2))
manifest=json.loads((bundle/'manifest.json').read_text());manifest.update(module_id='A12_PL_AUTHFIX_BOUND_V2',authorization_included=False,budget=spec)
manifest['files']=[dict(path=p.relative_to(bundle).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(bundle.rglob('*')) if p.is_file() and p!=bundle/'manifest.json']
(bundle/'manifest.json').write_text(json.dumps(manifest,indent=2))
result=dict(status='BOUND_WORKLOAD_POLICY_PASS_PENDING_BASELINE_REVIEW',boot_id=boot,kernel=os.uname().release,
 baseline_sha256=baseline,kernel_raw=raw,diagnostics=diagnostics(raw),scan_complete=scan['scan_complete'],
 authorization_included=spec['authorization_included'],owner_authorized_compute=True,submission_budget=3024,
 memory={r.split(':')[0]:int(r.split()[1]) for r in Path('/proc/meminfo').read_text().splitlines() if r.startswith(('MemAvailable:','CmaFree:'))},PL_mutations=0)
(ROOT/'preflight.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('__PL_BEGIN__',flush=True);print(json.dumps(result),flush=True);print('__PL_END__',flush=True)
