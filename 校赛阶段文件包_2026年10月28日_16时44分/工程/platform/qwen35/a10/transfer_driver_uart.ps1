param([Parameter(Mandatory=$true)][string]$OutputPath,[switch]$ValidateOnly,
      [ValidateSet('driver','linkage')][string]$PayloadKind='driver')
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $OutputPath){throw 'Evidence already exists'}
if($PayloadKind -eq 'linkage'){
    $plan=& 'C:\Patientqwen\platform\local\a1\venv\Scripts\python.exe' "$PSScriptRoot\linkage_serial_payload.py" --prepare 'C:\Patientqwen\platform\build\a10-vadd-short-20261018-v3\a10-vadd-short' | ConvertFrom-Json
}else{
    $plan=& 'C:\Patientqwen\platform\local\a1\venv\Scripts\python.exe' "$PSScriptRoot\driver_serial_payload.py" --prepare 'C:\Patientqwen\platform\local\a10-xrt-2.18-audit\zocl-2.18-stripped-PC_ONLY.ko' | ConvertFrom-Json
}
if($LASTEXITCODE -ne 0){throw 'Payload preparation failed'}
if($ValidateOnly){$plan | Select-Object sha256,bytes,compressed_bytes,receiver_sha256,@{Name='chunks';Expression={$_.chunks.Count}} | ConvertTo-Json;exit 0}
$identity='FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$device=Get-PnpDevice -Class Ports -PresentOnly | Where-Object {$_.InstanceId -eq $identity -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
if(-not $device){throw 'COM5 identity mismatch'}
$serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1500
$report=[ordered]@{domain='BOARD_FILE_TRANSFER_ONLY';utc=[DateTime]::UtcNow.ToString('o');sha256=$plan.sha256;bytes=$plan.bytes;compressed_bytes=$plan.compressed_bytes;receiver_sha256=$plan.receiver_sha256;chunks=$plan.chunks.Count;acks=@();raw='';status='NOT_STARTED';closed=$false;driver_load='NOT_PERFORMED'}
$report.payload_kind=$PayloadKind
if($PayloadKind -eq 'linkage'){$report.target=$plan.target;$report.boot_id=$plan.boot_id;$report.base_receiver_sha256=$plan.base_receiver_sha256}
function Read-Uart([string]$pattern,[int]$seconds,[string]$initial=''){
    $buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    [void]$buffer.Append($initial)
    if($buffer.ToString() -match $pattern){return $buffer.ToString()}
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        if($serial.BytesToRead -gt 0){[void]$buffer.Append($serial.ReadExisting());if($buffer.Length -gt 65536){throw 'UART receive cap'};if($buffer.ToString() -match $pattern){return $buffer.ToString()}}
        Start-Sleep -Milliseconds 10
    }
    $report.raw += $buffer.ToString()
    throw 'UART timeout; no reset, interrupt, retry or cleanup sent'
}
try{
    $serial.Open();$serial.Write("`r")
    $hello=Read-Uart 'ubuntu@kria:[^\r\n]*\$\s*$' 3
    if($hello -match '(?i)password|login:|ZynqMP>'){throw 'Not a confirmed shell'}
    $tag='A10_TRANSFER_'+[Guid]::NewGuid().ToString('N')
    $wire='printf ''\n''; '+$plan.command+'; a10_rc=$?; printf ''\n'+$tag+'_END:%s\n'' "$a10_rc"'
    $serial.Write($wire+"`r")
    $report.raw=Read-Uart '(?m)(?:^|\r)A10DRV_READY\r?$' 4
    $timer=[Diagnostics.Stopwatch]::StartNew()
    $last=''
    foreach($chunk in $plan.chunks){
        $maxSeconds=if($PayloadKind -eq 'linkage'){27}else{85}
        if($timer.Elapsed.TotalSeconds -gt $maxSeconds){throw 'Host transfer deadline'}
        $serial.Write($chunk.line+"`n")
        $received=Read-Uart ('(?m)^'+[regex]::Escape($chunk.ack)+'\r?$') 4
        $report.acks += $chunk.ack
        $last=$received
    }
    $endPattern='(?m)^'+$tag+'_END:(\d+)\r?$'
    $report.raw += Read-Uart $endPattern 5 $last
    $match=[regex]::Match($report.raw,$endPattern)
    $report.exit_code=[int]$match.Groups[1].Value
    if($report.exit_code -ne 0 -or -not $report.raw.Contains('A10DRV_DONE:'+$plan.sha256)){throw 'Transfer not verified'}
    $report.elapsed_s=$timer.Elapsed.TotalSeconds
    $report.status='PASS_HASH_VERIFIED_NO_EXECUTION'
}catch{$report.status='FAILED_OR_UNKNOWN_STOPPED';$report.error=$_.Exception.Message}
finally{if($serial.IsOpen){$serial.Close()};$serial.Dispose();$report.closed=$true;$report|ConvertTo-Json -Depth 6|Set-Content -LiteralPath $OutputPath -Encoding utf8}
[pscustomobject]$report | Select-Object status,bytes,compressed_bytes,chunks,elapsed_s,exit_code,error,closed | ConvertTo-Json
if($report.status -ne 'PASS_HASH_VERIFIED_NO_EXECUTION'){exit 2}
