param([string]$Port='COM5',[ValidateSet('scene','postboot','network','network_nm','network_irq2')][string]$Action='scene')
$ErrorActionPreference='Stop'
$repo=[System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$expected='FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$found=@(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -eq $expected -and $_.FriendlyName -eq ('USB Serial Port ('+$Port+')') -and $_.Status -eq 'OK' })
if($found.Count -ne 1){throw 'Exact connected UART channel differs'}
$sourceName=switch($Action){'scene' {'tt10_01_uart_root_scene.py'} 'postboot' {'tt10_01_uart_postboot.py'} 'network_nm' {'tt10_01_uart_network_nm.py'} 'network_irq2' {'tt10_01_uart_network_irq2.py'} 'network' {'tt10_01_uart_network.py'}}
$scope=if($Action -like 'network*'){'PINNED_UART_TEMPORARY_NETWORK_RECOVERY'}else{'PINNED_UART_ROOT_READ_ONLY_SCENE'}
$bytes=[System.IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $sourceName))
$pin=[Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
$data=[Convert]::ToBase64String($bytes)
$chunks=@([regex]::Matches($data,'.{1,1600}') | ForEach-Object {$_.Value})
$ready='__TT10_UART_ROOT_CODE_READY__'
$bootstrap="import sys,base64,hashlib; print('$ready',flush=True); s=''.join(sys.stdin.readline().strip() for _ in range($($chunks.Count))); b=base64.b64decode(s,validate=True); assert hashlib.sha256(b).hexdigest()=='$pin'; exec(compile(b,'tt10_readonly_root_scene','exec'))"
$line='sudo -p __TT10_UART_SUDO_AUTH__: /usr/bin/python3 -B -I -c "'+$bootstrap+'"'
$serial=[IO.Ports.SerialPort]::new($Port,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.Handshake=[IO.Ports.Handshake]::None;$serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.NewLine="`r";$serial.WriteTimeout=3000
function Read-Until([string]$pattern,[int]$seconds){
    $buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        [void]$buffer.Append($serial.ReadExisting())
        if($buffer.Length -gt 1048576){throw 'UART observation budget exceeded'}
        if($buffer.ToString() -match $pattern){return $buffer.ToString()}
        Start-Sleep -Milliseconds 50
    }
    throw 'Expected UART root scene marker timed out; no retry or mutation'
}
$password=$null;$phase='OPEN_UART'
try{
    $serial.Open();$serial.Write("`r");$phase='VERIFY_EXISTING_SHELL'
    $null=Read-Until 'ubuntu@kria:[^\r\n]*\$\s*$' 5
    $serial.WriteLine($line);$phase='WAIT_SUDO_OR_READY'
    $reply=Read-Until '(__TT10_UART_SUDO_AUTH__:\s*$|[\r\n]__TT10_UART_ROOT_CODE_READY__[\r\n])' 8
    if($reply -match '__TT10_UART_SUDO_AUTH__:\s*$'){
        $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName=Join-Path $repo 'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe';$info.Arguments='Verified KV260 UART sudo'
        $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
        $child=[Diagnostics.Process]::Start($info);$password=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
        if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($password) -or $password.Contains("`n") -or $password.Contains("`r")){throw 'User authentication cancelled; no retry'}
        # sudo reads its TTY with echo disabled. No secret is put in argv/logs.
        $serial.WriteLine($password);$password=$null;$phase='WAIT_PRIVILEGED_READY'
        $null=Read-Until '[\r\n]__TT10_UART_ROOT_CODE_READY__[\r\n]' 10
    }
    $phase='SEND_PINNED_CODE_'+$Action.ToUpperInvariant()
    foreach($chunk in $chunks){$serial.WriteLine($chunk);Start-Sleep -Milliseconds 20}
    $phase='READ_SCENE'
    $reply=Read-Until '__TT10_UART_ROOT_SCENE_END__' 45
    $match=[regex]::Match($reply,'(?s)__TT10_UART_ROOT_SCENE_BEGIN__\s*(\{[^\r\n]+\})\s*__TT10_UART_ROOT_SCENE_END__')
    if(-not $match.Success){throw 'Structured root scene missing'}
    $value=$match.Groups[1].Value | ConvertFrom-Json
    if($value.machine_sha256 -ne 'ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec'){throw 'Registered board identity differs'}
    [pscustomobject]@{Scope=$scope;Port=$Port;SourceSHA256=$pin;CredentialsLogged=$false;Scene=$value} | ConvertTo-Json -Depth 16
    if($value.status -eq 'FAILED_PRESERVE_PARTIAL_STATE'){exit 2}
}catch{
    [pscustomobject]@{Scope='UART_OPERATION_STOPPED_NO_RETRY';Action=$Action;Phase=$phase;SourceSHA256=$pin;CredentialsLogged=$false;PartialMutationPossible=($Action -like 'network*' -and $phase -eq 'READ_SCENE')} | ConvertTo-Json
    throw
}finally{
    $password=$null
    if($serial.IsOpen){$serial.Close()}
    $serial.Dispose()
}
