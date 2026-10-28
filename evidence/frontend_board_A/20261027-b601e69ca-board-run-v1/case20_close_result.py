import hashlib,json,os,signal,time
from pathlib import Path
old=Path('/var/lib/kv260-a12/b601e69ca-hotpath-20261027-v7')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='98886b24-96d3-409e-a783-ce9c54873da9'
done=json.loads((old/'continuous/bundle/run-v1/result.json').read_text())
assert done['worker_exit_code']==0 and done['lease_archived'] is True
assert not Path('/var/lock/kv260-a1/active').exists() and not Path('/sys/module/zocl').exists()
assert Path('/sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status').read_text().strip()=='applied'
pid=json.loads((old/'STARTED.json').read_text())['pid'];proc=Path('/proc',str(pid));closed=False
if proc.exists():
 assert str(old).encode() in (proc/'cmdline').read_bytes()
 fds=[]
 for fd in (proc/'fd').iterdir():
  try:fds.append(os.readlink(fd))
  except FileNotFoundError:pass
 assert not any(x.startswith('/dev/dri/') for x in fds)
 # This process now only sleeps while retaining the released results HTTP view.
 # Its hardware Owner has blocked SIGTERM; end this result view only after release.
 os.kill(pid,signal.SIGKILL);closed=True
profile=json.loads((old/'continuous/web-config.json').read_text())['browser_profile'].encode();browsers=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if (p/'comm').read_text().strip()=='firefox' and profile in (p/'cmdline').read_bytes().split(b'\0'):
   os.kill(int(p.name),signal.SIGTERM);browsers.append(int(p.name))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
r=dict(status='RELEASED_RESULT_VIEW_CLOSED',old_result_pid=pid,closed=closed,hardware_owner_already_released=True,default_overlay='applied',browser_termination_requested=browsers,old_sessions_preserved=True)
(old/'CASE20_RESULT_VIEW_CLOSE.json').write_text(json.dumps(r,indent=2)+'\n')
print('__TT10_UART_ROOT_SCENE_BEGIN__',flush=True);print(json.dumps(r),flush=True);print('__TT10_UART_ROOT_SCENE_END__',flush=True)
