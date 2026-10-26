param([Parameter(Mandatory=$true)][string]$Script,[Parameter(Mandatory=$true)][string]$Output,[int]$WaitSeconds=35)
$ErrorActionPreference='Stop'
$port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake='None';$port.DtrEnable=$false;$port.RtsEnable=$false;$port.WriteTimeout=2000
$port.Encoding=[Text.UTF8Encoding]::new($false)
$capture=[Text.StringBuilder]::new()
try {
 $port.Open();$port.Write("`r");Start-Sleep -Milliseconds 350
 $prompt=$port.ReadExisting()
 if($prompt -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Console is not at the existing ubuntu shell; no script sent'}
 $port.Write("python3 -B -I <<'PY_FRONTEND_CHECK'`r")
 foreach($line in [IO.File]::ReadAllLines((Resolve-Path -LiteralPath $Script))){$port.Write($line+"`r");Start-Sleep -Milliseconds 12}
 $port.Write("PY_FRONTEND_CHECK`r")
 $timer=[Diagnostics.Stopwatch]::StartNew()
 while($timer.Elapsed.TotalSeconds -lt $WaitSeconds){
  [void]$capture.Append($port.ReadExisting())
  if($capture.ToString() -match '(?m)^__FRONTEND_END__\r?$'){break}
  Start-Sleep -Milliseconds 150
 }
 [IO.File]::WriteAllText($Output,$capture.ToString(),[Text.UTF8Encoding]::new($false))
 $match=[regex]::Match($capture.ToString().Replace("`r",''),'(?s)__FRONTEND_BEGIN__\n+(.*?)\n+__FRONTEND_END__')
 if(-not $match.Success){throw 'No complete structured result; console operation may still be running, do not replay'}
 Write-Output $match.Groups[1].Value
} finally {if($port.IsOpen){$port.Close()};$port.Dispose()}
