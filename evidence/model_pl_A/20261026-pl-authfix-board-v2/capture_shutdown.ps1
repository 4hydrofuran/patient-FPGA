$ErrorActionPreference='Stop';$port=$null;$buffer=[Text.StringBuilder]::new();$stopped=$false
try {
 $port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
 $port.DtrEnable=$false;$port.RtsEnable=$false;$port.Handshake=[IO.Ports.Handshake]::None;$port.Open()
 $watch=[Diagnostics.Stopwatch]::StartNew()
 while($watch.Elapsed.TotalSeconds -lt 45){
  [void]$buffer.Append($port.ReadExisting());$text=$buffer.ToString()
  if(-not $stopped -and $text -match '(?m)^U-Boot \d{4}\.\d+' -and $text -match 'Hit any key to stop autoboot:\s*[1-9][0-9]*\s*$'){$port.Write(' ');$stopped=$true}
  if($stopped -and $text -match '(?m)^(?:ZynqMP>|=>)\s*$'){break}
  if($text -match '(?m)^kria login:\s*$'){break}
  Start-Sleep -Milliseconds 30
 }
}finally{if($port){if($port.IsOpen){$port.Close()};$port.Dispose()};[ordered]@{utc=[DateTime]::UtcNow.ToString('o');raw=$buffer.ToString();stopped_fresh_countdown=$stopped;reboot_commands=0}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $PSScriptRoot 'shutdown-capture.json') -Encoding utf8}
Write-Output $buffer.ToString()
