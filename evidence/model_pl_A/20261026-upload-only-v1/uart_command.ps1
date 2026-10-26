param([Parameter(Mandatory)][string]$PayloadPath,[Parameter(Mandatory)][string]$ReceiptPath)
$ErrorActionPreference='Stop'
$port=$null
$report=[ordered]@{serial='COM5';dtr=$false;rts=$false;utc=[DateTime]::UtcNow.ToString('o');status='STARTED';output='';error=$null}
try {
    $device=@(Get-PnpDevice -Class Ports -PresentOnly|Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.Status -eq 'OK'})
    if($device.Count -ne 1){throw 'Registered serial channel unavailable'}
    $raw=[IO.File]::ReadAllBytes($PayloadPath)
    $encoded=[Convert]::ToBase64String($raw)
    $command='python3 -B -I -c "import base64;exec(compile(base64.b64decode('''+$encoded+'''),''a12_upload_only'',''exec''))"'
    if($command.Length -gt 4000){throw 'Serial command exceeds console line capacity'}
    $port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $port.Handshake=[IO.Ports.Handshake]::None;$port.DtrEnable=$false;$port.RtsEnable=$false;$port.WriteTimeout=5000
    $port.Open();$port.Write("`r")
    $buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt 5){
        [void]$buffer.Append($port.ReadExisting())
        if($buffer.ToString() -match 'ubuntu@kria:[^\r\n]*\$\s*$'){break}
        Start-Sleep -Milliseconds 30
    }
    if($buffer.ToString() -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated shell not available'}
    [void]$buffer.Clear();$port.Write($command+"`r");$watch.Restart()
    while($watch.Elapsed.TotalSeconds -lt 45){
        [void]$buffer.Append($port.ReadExisting())
        if($buffer.Length -gt 131072){throw 'Serial response too large'}
        if($buffer.ToString() -match '(?m)^__A12_UPLOAD_END__\s*$'){break}
        Start-Sleep -Milliseconds 30
    }
    $report.output=$buffer.ToString()
    if($report.output -notmatch '(?m)^__A12_UPLOAD_END__\s*$'){throw 'Command completion not confirmed; no automatic retry'}
    $report.status='COMMAND_COMPLETED'
}catch{$report.status='STOPPED';$report.error=$_.Exception.Message}
finally{
    if($port){if($port.IsOpen){$port.Close()};$port.Dispose()}
    $report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath $ReceiptPath -Encoding utf8 -NoNewline
}
Write-Output $report.output
if($report.error){Write-Output $report.error;exit 1}
