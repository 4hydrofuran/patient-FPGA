param([ValidateSet('preflight','start')][string]$Stage='preflight')
$ErrorActionPreference='Stop';$folder=$PSScriptRoot
$pin=(Get-FileHash -LiteralPath (Join-Path $folder ($Stage+'.py')) -Algorithm SHA256).Hash.ToLowerInvariant()
$bootstrap="import urllib.request,hashlib; b=urllib.request.urlopen('http://192.168.2.1:8765/$Stage.py',timeout=15).read(65536); assert hashlib.sha256(b).hexdigest()=='$pin'; exec(compile(b,'reviewed_original_pl_$Stage','exec'))"
$command='sudo -p __A12_PL_AUTH__: /usr/bin/python3 -B -I -c "'+$bootstrap+'"'
$port=$null;$secret=$null;$report=[ordered]@{stage=$Stage;utc=[DateTime]::UtcNow.ToString('o');source_sha256=$pin;output='';error=$null;credentials_logged=$false}
try{
 $port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
 $port.DtrEnable=$false;$port.RtsEnable=$false;$port.Handshake=[IO.Ports.Handshake]::None;$port.WriteTimeout=3000
 $port.Open();$port.Write("`r");Start-Sleep -Milliseconds 200
 if($port.ReadExisting() -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated UART shell absent'}
 $port.Write($command+"`r");$buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew();$authenticated=$false
 $limit=if($Stage -eq 'preflight'){120}else{660}
 while($watch.Elapsed.TotalSeconds -lt $limit){
  $part=$port.ReadExisting();[void]$buffer.Append($part);$text=$buffer.ToString()
  if($text.Length -gt 1048576){throw 'UART response cap'}
  if(-not $authenticated -and $text -match '__A12_PL_AUTH__:\s*$'){
   $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe';$info.Arguments='KV260 original PL acceptance sudo (hidden input)'
   $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
   $child=[Diagnostics.Process]::Start($info);$secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
   if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret)){throw 'Authentication cancelled'}
   $port.Write($secret+"`r");$secret=$null;$authenticated=$true
  }
  if($Stage -eq 'start' -and $part -match 'PL_PROGRESS|PL_MANAGER_STARTED'){Write-Host $part.Trim()}
  if($text -match '(?m)^__PL_END__\s*$'){break}
  if($text -match '(?m)^Traceback \(most recent call last\):' -and $text -match 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Reviewed PL payload failed'}
  Start-Sleep -Milliseconds 50
 }
 $report.output=$buffer.ToString();if($report.output -notmatch '(?m)^__PL_END__\s*$'){throw 'PL completion not confirmed; no automatic retry'}
 Write-Host ('Completed '+$Stage)
}catch{$report.error=$_.Exception.Message;Write-Host $report.error;if($buffer){$report.output=$buffer.ToString()}}
finally{if($port){if($port.IsOpen){$port.Close()};$port.Dispose()};$secret=$null;$report.completed_utc=[DateTime]::UtcNow.ToString('o');$report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $folder ($Stage+'-uart.json')) -Encoding utf8 -NoNewline}
if($report.error){exit 1}
