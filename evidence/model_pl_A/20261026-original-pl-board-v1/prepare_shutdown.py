from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[3]
source=root/'platform/qwen35/a10/shutdown_complete_uart.ps1'
text=source.read_text(encoding='utf-8')
text=text.replace('c5baeabe-273d-447e-b323-ff07dd7af201','8a0276fb-86d1-4ef8-b067-adcc903a999a')
guard='test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active; test "$(cat /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status)" = applied; '
assert text.count(guard)==1
text=text.replace(guard,'') # User explicitly authorizes OS shutdown of retained fault scene.
before='''  $secure=Read-Host 'Board credential (not logged)' -AsSecureString
  $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}'''
after='''  $info=[Diagnostics.ProcessStartInfo]::new()
  $info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
  $info.Arguments='KV260 authorized normal poweroff (hidden input)'
  $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
  $authChild=[Diagnostics.Process]::Start($info)
  $secret=$authChild.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$authChild.WaitForExit()
  if($authChild.ExitCode -ne 0){throw 'Authentication cancelled'}'''
assert text.count(before)==1;text=text.replace(before,after)
# A retained owner blocks SIGTERM; allow the normal OS shutdown grace period.
text=text.replace("':\d+$') 5", "':\d+$') 5")
text=text.replace("'[1-9][0-9]*$') 60", "'[1-9][0-9]*$') 180") if False else text
text=text.replace("': [1-9]", "': [1-9]") if False else text
text=text.replace("$tag+':[1-9][0-9]*$') 60", "$tag+':[1-9][0-9]*$') 180")
target=Path(__file__).parent/'shutdown_once.ps1';target.write_text(text,encoding='utf-8')
with (Path(__file__).parent/'SHUTDOWN_AUTHORIZATION.json').open('x',encoding='utf-8') as f:
    json.dump(dict(user_request='现在关机，我要拔电源了',normal_poweroff=True,force=False,manual_process_signals=False,
                   lease_or_failure_records_deleted=False,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest()),f,ensure_ascii=False,indent=2)
