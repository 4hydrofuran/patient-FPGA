param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $OutputPath){throw 'New receipt required'}
$usb='FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$portIdentity=Get-PnpDevice -Class Ports -PresentOnly | Where-Object { $_.InstanceId -eq $usb -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK' }
if(-not $portIdentity){throw 'Fixed COM5 identity differs'}
$serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None
$serial.ReadTimeout=200;$serial.WriteTimeout=1000
$report=[ordered]@{schema='A12_STEP08_UART_IDENTITY_ONLY';utc=[DateTime]::UtcNow.ToString('o');port='COM5';usb=$usb;status='NOT_STARTED';raw='';reboot=$false;configuration_changed=$false;closed=$false}
function Receive([string]$Pattern,[int]$Seconds){
    $text=[Text.StringBuilder]::new();$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt $Seconds){
        if($serial.BytesToRead -gt 0){[void]$text.Append($serial.ReadExisting());if($text.Length -gt 131072){throw 'RX limit'};if($text.ToString() -match $Pattern){break}}
        Start-Sleep -Milliseconds 40
    }
    return $text.ToString()
}
try{
    $serial.Open();$serial.Write("`r")
    $hello=Receive '(?m)(kria login:\s*$|ubuntu@kria:[^\r\n]*\$\s*$)' 4
    $report.raw+=$hello
    if($hello -match 'kria login:\s*$'){
        $serial.Write("ubuntu`r");$challenge=Receive 'Password:\s*$' 4
        $report.raw+=$challenge
        if($challenge -notmatch 'Password:\s*$'){throw 'No verified UART password prompt'}
        $secure=Read-Host 'Verified board UART login; hidden credential' -AsSecureString
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try{$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer);$serial.Write($plain+"`r");$plain=$null}
        finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer);$secure.Dispose()}
        $hello=Receive 'ubuntu@kria:[^\r\n]*\$\s*$' 8
        $report.raw+=$hello
    }
    if($hello -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated Linux shell not proven'}
    $tag='A12_ID_'+[Guid]::NewGuid().ToString('N')
    $command='printf ''\n'+$tag+'_BEGIN\n''; id; uname -r; sha256sum /etc/machine-id; cat /proc/sys/kernel/random/boot_id; ip -br addr show eth0; ip -4 route; cat /sys/class/net/eth0/carrier; systemctl is-active ssh.socket ssh.service; printf ''\n'+$tag+'_END\n'''
    $serial.Write($command+"`r");$raw=Receive ('(?m)^'+$tag+'_END\r?$') 8
    $report.raw+=$raw
    if($raw -notmatch ('(?m)^'+$tag+'_END\r?$')){throw 'Identity completion not proven'}
    $report.status='READONLY_IDENTITY_COLLECTED'
}catch{$report.status='STOPPED';$report.error=$_.Exception.Message}
finally{if($serial.IsOpen){$serial.Close()};$serial.Dispose();$report.closed=$true;$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $OutputPath -Encoding utf8}
Write-Host ($report.status+'; COM5 closed; '+$OutputPath)
if($report.status -eq 'STOPPED'){exit 2}
