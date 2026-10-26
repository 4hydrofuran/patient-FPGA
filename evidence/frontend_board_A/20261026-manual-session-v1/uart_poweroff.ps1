param([Parameter(Mandatory)][string]$PayloadPath,[Parameter(Mandatory)][string]$ReceiptPath,[int]$Seconds=90)
$ErrorActionPreference='Stop';$port=$null;$secret=$null
$report=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');output='';error=$null;credentials_logged=$false}
try {
 $pin=(Get-FileHash -LiteralPath $PayloadPath -Algorithm SHA256).Hash.ToLowerInvariant();$report.source_sha256=$pin
 $encoded=[Convert]::ToBase64String([IO.File]::ReadAllBytes($PayloadPath))
 $command='sudo -p __A12_PL_AUTH__: /usr/bin/python3 -B -I -c "import base64;exec(compile(base64.b64decode('''+$encoded+'''),''a12_authfix'',''exec''))"'
 if($command.Length -gt 4000){throw 'UART command too large; use bounded HTTP bootstrap'}
 $device=@(Get-PnpDevice -Class Ports -PresentOnly|Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.Status -eq 'OK'})
 if($device.Count -ne 1){throw 'Registered UART unavailable'}
 $port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
 $port.DtrEnable=$false;$port.RtsEnable=$false;$port.Handshake=[IO.Ports.Handshake]::None;$port.WriteTimeout=3000
 $port.Open();$port.Write("`r");Start-Sleep -Milliseconds 250
 if($port.ReadExisting() -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated UART shell absent'}
 $port.Write($command+"`r");$buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew();$authenticated=$false
 while($watch.Elapsed.TotalSeconds -lt $Seconds){
  $part=$port.ReadExisting();[void]$buffer.Append($part);$text=$buffer.ToString()
  if($text.Length -gt 1048576){throw 'UART output exceeds cap'}
  if(-not $authenticated -and $text -match '__A12_PL_AUTH__:\s*$'){
   $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
   $info.Arguments='KV260 PL acceptance sudo (hidden input)';$info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
   $child=[Diagnostics.Process]::Start($info);$secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
   if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret)){throw 'Authentication cancelled'}
   $port.Write($secret+"`r");$secret=$null;$authenticated=$true
  }
  if($part -match 'PL_PROGRESS|PL_MANAGER_STARTED'){Write-Host $part.Trim()}
  if($text -match '(?m)^.*reboot: Power down\s*$'){break}
  if($text -match '(?m)^Traceback \(most recent call last\):' -and $text -match 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Payload failed'}
  Start-Sleep -Milliseconds 50
 }
 $report.output=$buffer.ToString()
 if($report.output -notmatch '(?m)^.*reboot: Power down\s*$'){throw 'Power down not confirmed; no automatic replay'}
}catch{$report.error=$_.Exception.Message;if($buffer){$report.output=$buffer.ToString()}}
finally{if($port){if($port.IsOpen){$port.Close()};$port.Dispose()};$secret=$null;$report.completed_utc=[DateTime]::UtcNow.ToString('o');$report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $ReceiptPath -Encoding utf8 -NoNewline}
if($report.error){Write-Output $report.error;exit 1};Write-Output 'NORMAL_POWER_DOWN_CONFIRMED'
