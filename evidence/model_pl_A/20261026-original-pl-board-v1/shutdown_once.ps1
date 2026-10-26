param([Parameter(Mandatory=$true)][string]$OutputPath,[switch]$ValidateOnly,[switch]$AuthorizedOnce)
$ErrorActionPreference='Stop'
# Fixed completed-run identity; not a generic remote command executor.
$command='set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = 8a0276fb-86d1-4ef8-b067-adcc903a999a; test "$(uname -r)" = 6.8.12-a10irq2; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; sudo -n /usr/bin/systemctl poweroff'
if($ValidateOnly){@{board_contact=$false;command=$command;force=$false;retries=0}|ConvertTo-Json;exit 0}
if(-not $AuthorizedOnce){throw 'Explicit shutdown authorization required'}
$receipt=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_NORMAL_SHUTDOWN_V1';utc=[DateTime]::UtcNow.ToString('o');command=$command;events=@();status='RESERVED';closed=$false;error=$null;compute_runs=0}
$serial=$null;$secret=$null
function Normal([string]$s){return ([regex]::Replace($s,'\x1b\[[0-?]*[ -/]*[@-~]','')).Replace("`r",'')}
function Record([string]$s){if($secret){$s=$s.Replace($secret,'[REDACTED]')};$report.events+=@{utc=[DateTime]::UtcNow.ToString('o');text=$s}}
function Receive([string]$pattern,[int]$seconds){
 $b=[Text.StringBuilder]::new();$w=[Diagnostics.Stopwatch]::StartNew()
 while($w.Elapsed.TotalSeconds -lt $seconds){
  if($serial.BytesToRead -gt 0){[void]$b.Append($serial.ReadExisting());if($b.Length -gt 262144){throw 'Receive cap'};if((Normal $b.ToString()) -match $pattern){Record $b.ToString();return $b.ToString()}}
  Start-Sleep -Milliseconds 30
 };Record $b.ToString();throw 'Deadline: no automatic retry, reset or forced shutdown'
}
try{
 $p=Get-PnpDevice -Class Ports -PresentOnly|Where-Object{$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
 if(-not $p){throw 'COM5 identity mismatch'}
 $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
 $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
 $serial.Open();$serial.Write("`r")
 $hello=Receive '(?m)^ubuntu@kria:[^\n]*\$\s*$|login:|password:|ZynqMP>' 3
 if((Normal $hello) -notmatch '(?m)^ubuntu@kria:[^\n]*\$\s*$' -or $hello -match 'login:|password:|ZynqMP>'){throw 'Authenticated shell not confirmed'}
 $tag='AUTH_'+[guid]::NewGuid().ToString('N')
 $serial.Write('sudo -p ''__A10_SHUTDOWN_AUTH__:'' -v; a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'+"`r")
 $raw=Receive ('(?m)^__A10_SHUTDOWN_AUTH__:\s*$|^'+$tag+':\d+$') 5
 if((Normal $raw) -match '(?m)^__A10_SHUTDOWN_AUTH__:\s*$'){
  Write-Host 'Exact board sudo challenge verified. Hidden credential input required.'
  $info=[Diagnostics.ProcessStartInfo]::new()
  $info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
  $info.Arguments='KV260 authorized normal poweroff (hidden input)'
  $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
  $authChild=[Diagnostics.Process]::Start($info)
  $secret=$authChild.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$authChild.WaitForExit()
  if($authChild.ExitCode -ne 0){throw 'Authentication cancelled'}
  if(-not $secret -or $secret.Contains("`r") -or $secret.Contains("`n")){throw 'Invalid credential'}
  $serial.Write($secret+"`r");$raw=Receive ('(?m)^'+$tag+':\d+$|^__A10_SHUTDOWN_AUTH__:\s*$') 5
 }
 if((Normal $raw) -notmatch ('(?m)^'+$tag+':0$')){throw 'Authorization unconfirmed'}
 $tag='STOP_'+[guid]::NewGuid().ToString('N')
 $serial.Write('( '+$command+' ); a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'+"`r")
 $raw=Receive ('(?m)^.*reboot: Power down\s*$|^'+$tag+':[1-9][0-9]*$') 180
 if((Normal $raw) -notmatch '(?m)^.*reboot: Power down\s*$'){throw 'Power down not confirmed'}
 $report.status='LINUX_NORMAL_POWER_DOWN_CONFIRMED'
}catch{$report.status='STOPPED';$report.error=$_.Exception.Message}
finally{
 if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()};$report.closed=$true
 $json=$report|ConvertTo-Json -Depth 8;if($secret){$json=$json.Replace($secret,'[REDACTED]')};$secret=$null
 $bytes=[Text.Encoding]::UTF8.GetBytes($json);$receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose()
}
Write-Host $report.status
if($report.error){Write-Host $report.error;exit 2}
