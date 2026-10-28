param([string]$OutputPath)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$devices=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -eq 'USB Serial Port (COM5)' -and $_.Status -eq 'OK'})
if($devices.Count -ne 1){throw 'Fixed KV260 FTDI channel differs'}
$port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake=[IO.Ports.Handshake]::None;$port.DtrEnable=$false;$port.RtsEnable=$false;$port.WriteTimeout=1000
$secret=$null
function Receive([string]$pattern,[int]$seconds){
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        [void]$buf.Append($port.ReadExisting())
        if($buf.Length -gt 131072){throw 'UART login output cap'}
        if($buf.ToString() -match $pattern){return $buf.ToString()}
        Start-Sleep -Milliseconds 50
    }
    throw 'UART login prompt deadline'
}
try{
    $port.Open();$port.Write("`r")
    $state=Receive 'ubuntu@kria:[^\r\n]*\$\s*$|kria login:\s*$' 5
    if($state -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){
        $port.Write("ubuntu`r");$null=Receive '(?i)password:\s*$' 5
        $info=[Diagnostics.ProcessStartInfo]::new()
        $info.FileName=Join-Path $repo 'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
        $info.Arguments='KV260 Ubuntu UART login after authorized reboot'
        $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
        $child=[Diagnostics.Process]::Start($info)
        $secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
        if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret) -or $secret.Contains("`n") -or $secret.Contains("`r")){throw 'User authentication cancelled'}
        $port.Write($secret+"`r");$secret=$null
        $null=Receive 'ubuntu@kria:[^\r\n]*\$\s*$|Login incorrect' 10
        if($matches -and $matches[0] -eq 'Login incorrect'){throw 'Login not accepted'}
    }
    $port.Write("printf '__BOOT_ID__';cat /proc/sys/kernel/random/boot_id;printf '__KERNEL__';uname -r`r")
    $raw=Receive 'ubuntu@kria:[^\r\n]*\$\s*$' 5
    $boot=[regex]::Match($raw,'(?m)^__BOOT_ID__([0-9a-f-]{36})\s*$').Groups[1].Value
    $kernel=[regex]::Match($raw,'(?m)^__KERNEL__([^\r\n]+)').Groups[1].Value
    if(-not $boot -or $kernel -ne '6.8.12-a10irq2'){throw 'New boot identity not confirmed'}
    $result=@{status='UART_LOGIN_NEW_IRQ2_CONFIRMED';boot_id=$boot;kernel=$kernel;credentials_logged=$false}
    $result|ConvertTo-Json|Set-Content -LiteralPath $OutputPath -Encoding UTF8
    $result|ConvertTo-Json
}finally{
    $secret=$null
    if($port.IsOpen){$port.Close()};$port.Dispose()
}
