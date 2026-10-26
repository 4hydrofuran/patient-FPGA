param([Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
$port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.DtrEnable=$false;$port.RtsEnable=$false;$port.Handshake='None'
$buffer=[Text.StringBuilder]::new();$confirmed=$false
try {
 $port.Open();$timer=[Diagnostics.Stopwatch]::StartNew()
 while($timer.Elapsed.TotalSeconds -lt 55){
  [void]$buffer.Append($port.ReadExisting())
  if($buffer.ToString() -match '(?m)^.*reboot: Power down\s*$'){$confirmed=$true;break}
  Start-Sleep -Milliseconds 50
 }
} finally {if($port.IsOpen){$port.Close()};$port.Dispose()}
$r=@{utc=[DateTime]::UtcNow.ToString('o');passive_only=$true;commands_sent=0;power_down_confirmed=$confirmed;output=$buffer.ToString()}
$r|ConvertTo-Json|Set-Content -LiteralPath $OutputPath -Encoding utf8
if($confirmed){Write-Output 'NORMAL_POWER_DOWN_CONFIRMED'}else{Write-Output 'STILL_WAITING_NO_COMMAND_REPLAY'}
