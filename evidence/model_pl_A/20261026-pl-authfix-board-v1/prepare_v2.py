import hashlib,json
from pathlib import Path
here=Path(__file__).parent;out=here.parent/'20261026-pl-authfix-board-v2';out.mkdir()
names=('identity.ps1','uart_payload.ps1','serve.py','preflight.py','start.py','collect.py','prepare_commands.py','prepare_start.py','finalize.py','PC_CHECKS.json')
for name in names:
 text=(here/name).read_text(encoding='utf-8-sig').replace('pl-authfix-20261026-v1','pl-authfix-20261026-v2').replace('20261026-pl-authfix-board-v1','20261026-pl-authfix-board-v2')
 if name=='preflight.py':
  text=text.replace("assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()","assert not Path('/sys/module/zocl').exists()")
  a=text.index("archive=Path('/var/lib/");b=text.index("bundle=ROOT/'bundle'",a)
  text=text[:a]+'''archive=ROOT/'bundle-fixed.zip'
with urllib.request.urlopen('http://192.168.2.1:8765/bundle.zip',timeout=30) as incoming, archive.open('xb') as target:
 while True:
  block=incoming.read(65536)
  if not block:break
  target.write(block)
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='fe8541f0840e40f2c10d28874af13af8e27f4f4cfb9557184f2f33199145f179'
'''+text[b:]
  needle="scan=collect(allow_ps_display=True);require_no_users(scan,True,boot_id=boot)"
  replacement=needle+'''
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
'''
  assert text.count(needle)==1;text=text.replace(needle,replacement)
  text=text.replace("(ROOT/'binding-source.py').write_bytes(binding)","(ROOT/'binding-source.py').write_bytes(binding)\n(bundle/'platform/qwen35/a12/resource_probe_binding.py').write_bytes(binding)")
  text=text.replace('acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa','fe8541f0840e40f2c10d28874af13af8e27f4f4cfb9557184f2f33199145f179')
 if name=='start.py':
  text=text.replace("EXPECTED_BASELINE='a4def789db1e6d73966b36a493a886b88a6673632279a8c3695412ed8065df2a'","EXPECTED_BASELINE='REVIEW_REQUIRED'")
  text=text.replace('from resource_probe_policy import validate_plan','from resource_probe_binding import require_manager_api\nrequire_manager_api(module)\nfrom resource_probe_policy import validate_plan')
 if name=='serve.py':
  text=text.replace("FILES={'/preflight.py':", "FILES={'/bundle.zip':ROOT/'evidence/model_pl_A/20261026-pl-authfix-board-v1/bundle-fixed-v1.zip','/preflight.py':")
 if name=='prepare_commands.py':text=text.replace('identity-irq2-v3.json','identity-irq2.json')
 if name=='collect.py':text=text.replace("'preflight.json','authorization.json'","'prior-boot-recovery.json','preflight.json','authorization.json'")
 if name=='finalize.py':
  text=text.replace("key='a12_pl_authorization_fix_board_20261026'","key='a12_pl_authorization_fix_board_repaired_20261026'")
  text=text.replace('定向 PC 验证：历史契约、新版配置、两项授权回归、一项普通三请求控制链测试均退出0。','定向 PC 验证：历史契约、新版配置、四项绑定与真实应用适配器导入回归、一项普通三请求控制链测试均退出0。')
 (out/name).write_text(text,encoding='utf-8')
boot=(here/'boot_once.ps1').read_text(encoding='utf-8-sig')
boot=boot.replace('6.8.0-1036-xilinx','6.8.12-a10irq2')
boot=boot.replace('test ! -d /sys/module/zocl; test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1;','test -d /sys/module/zocl; test -d /sys/kernel/config/device-tree/overlays/a12-pl-authfix-20261026-v1_image_1;')
old="test ! -e /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active;"
new="test -d /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active; sudo -n /usr/bin/python3 -c \"import json; r=json.load(open(''/var/lock/kv260-a1/active/lease.json'')); assert r[''window'']==''a12-pl-authfix-20261026-v1'' and r[''pid'']==2939 and r[''identity''].endswith('':0978088a-8d10-45b2-8f43-726d00209313'')\";"
assert boot.count(old)==1;boot=boot.replace(old,new)
(out/'boot_recover_once.ps1').write_text(boot,encoding='utf-8')
with (out/'AUTHORIZATION.json').open('x',encoding='utf-8') as f:
 json.dump(dict(user_answer='允许再一次恢复重启和临时引导',normal_reboots=1,temporary_irq2_boots=1,default_boot_changes=False,flash=False,
  fixed_package_sha256='fe8541f0840e40f2c10d28874af13af8e27f4f4cfb9557184f2f33199145f179',additional_user_scope='本次测试过程中排除可定位的问题'),f,ensure_ascii=False,indent=2)
print(out)
