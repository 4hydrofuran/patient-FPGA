from pathlib import Path
root=Path(__file__).resolve().parents[3]
source=(root/'evidence/model_pl_A/20261026-pl-authfix-board-v2/uart_payload.ps1').read_text(encoding='utf-8-sig')
old="if($port.ReadExisting() -notmatch 'ubuntu@kria:[^\\r\\n]*\\$\\s*$'){throw 'Authenticated UART shell absent'}"
new=r'''$hello=$port.ReadExisting()
 if($hello -match 'kria login:\s*$'){
  $port.Write("ubuntu`r");Start-Sleep -Milliseconds 500
  if($port.ReadExisting() -notmatch 'Password:\s*$'){throw 'Expected login password prompt absent'}
  $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
  $info.Arguments='KV260 console login (hidden input)';$info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
  $child=[Diagnostics.Process]::Start($info);$secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
  if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret)){throw 'Login cancelled'}
  $port.Write($secret+"`r");$secret=$null;$hello=''
  for($attempt=0;$attempt -lt 24;$attempt++){Start-Sleep -Milliseconds 500;$hello+=$port.ReadExisting();if($hello -match 'ubuntu@kria:[^\r\n]*\$\s*$'){break}}
 }
 if($hello -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated UART shell absent'}'''
assert source.count(old)==1
Path(__file__).with_name('uart_payload.ps1').write_text(source.replace(old,new),encoding='utf-8')
