param([Parameter(Mandatory=$true)][string]$Plan,
      [Parameter(Mandatory=$true)][string]$Receipt)
# Explicit reviewed jobs only. Authentication is accepted only at the actual
# sudo prompt and is never included in commands, the receipt or console output.
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $Receipt) { throw 'Receipt already reserved' }
$jobs=Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
$identity='FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$device=@(Get-PnpDevice -Class Ports -PresentOnly | Where-Object { $_.InstanceId -eq $identity -and $_.FriendlyName -match '\(COM5\)$' -and $_.Status -eq 'OK' })
if ($device.Count -ne 1) { throw 'COM5 identity differs' }
$port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake=[IO.Ports.Handshake]::None; $port.DtrEnable=$false; $port.RtsEnable=$false
$port.ReadTimeout=200; $port.WriteTimeout=1500
$report=[ordered]@{utc=[DateTime]::UtcNow.ToString('o');plan_sha256=(Get-FileHash -LiteralPath $Plan -Algorithm SHA256).Hash;port='COM5';records=@();status='RESERVED';closed=$false}
$reservation=[IO.File]::Open($Receipt,[IO.FileMode]::CreateNew); $reservation.Dispose()
function Receive([string]$Pattern,[int]$Seconds) {
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $Seconds) {
        if($port.BytesToRead -gt 0) {
            [void]$buf.Append($port.ReadExisting())
            if($buf.Length -gt 2097152) { throw 'UART receive cap' }
            if($buf.ToString() -match $Pattern) { return $buf.ToString() }
        }
        Start-Sleep -Milliseconds 30
    }
    return $buf.ToString()
}
try {
    $port.Open();$port.Write("`r")
    $hello=Receive 'ubuntu@kria:[^\r\n]*\$\s*$' 3
    if($hello -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$' -or $hello -match 'Password:|login:|ZynqMP>') { throw 'Authenticated Linux shell not confirmed' }
    foreach($job in $jobs) {
        if($job.command.Length -gt 3400 -or $job.command -match "[`r`n]") { throw 'Command framing/length' }
        $tag='A11D_'+[Guid]::NewGuid().ToString('N')
        $wire='printf ''\n'+$tag+'_BEGIN\n''; ( '+$job.command+' ); a11d_rc=$?; printf ''\n'+$tag+'_END:%s\n'' "$a11d_rc"'
        $port.Write($wire+"`r")
        $pattern='(?m)^'+$tag+'_END:(\d+)\r?$'
        $raw=Receive ($pattern+'|\[sudo\] password for ubuntu:\s*$') ([int]$job.seconds)
        if($raw -match '\[sudo\] password for ubuntu:\s*$') {
            if($job.name -ne 'sudo_auth' -or $job.command -ne 'sudo -v') { throw 'Unexpected authentication prompt' }
            $secure=Read-Host 'Verified board sudo prompt; hidden credential' -AsSecureString
            $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try { $secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr);$port.Write($secret+"`r");$secret=$null }
            finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose() }
            $raw+='[CREDENTIAL_INPUT_NOT_RECORDED]'+(Receive $pattern 6)
        }
        $match=[regex]::Match($raw,$pattern)
        $report.records+=@{name=$job.name;command=$job.command;raw=$raw;completed=$match.Success;exit_code=$(if($match.Success){[int]$match.Groups[1].Value}else{$null})}
        if(-not $match.Success) { throw 'Remote completion unknown; no interrupt/retry sent' }
        if([int]$match.Groups[1].Value -ne 0) { throw ('Remote command failed: '+$job.name) }
        Write-Output ('Completed '+$job.name)
    }
    $report.status='COMPLETED'
} catch { $report.status='STOPPED';$report.error=$_.Exception.Message;Write-Output $report.error }
finally {
    if($port.IsOpen){$port.Close()};$port.Dispose();$report.closed=$true
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Receipt -Encoding utf8
}
if($report.status -ne 'COMPLETED'){exit 2}
