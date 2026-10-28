param([ValidateSet('inventory','connect','stage','run')][string]$Action='inventory',[ValidateSet('stage-package','stage-package-v2')][string]$StagePackage='stage-package',[string]$RunPayload)
$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$devices=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -eq 'USB Serial Port (COM5)' -and $_.Status -eq 'OK'})
if($devices.Count -ne 1){throw 'Fixed KV260 FTDI channel differs'}
$sourceName=if($Action -eq 'connect'){'frontend_board_connect.py'}else{'frontend_board_inventory.py'}
$source=if($Action -eq 'stage'){Join-Path $repo ('evidence/frontend_board_A/20261027-latest-b-preboard-v1/'+$StagePackage+'/receiver.py')}else{Join-Path $PSScriptRoot $sourceName}
if($Action -eq 'run'){
    $source=[IO.Path]::GetFullPath($RunPayload)
    $allowed=[IO.Path]::GetFullPath((Join-Path $repo 'evidence/frontend_board_A/20261027-b601e69ca-board-run-v1'))
    if([IO.Path]::GetDirectoryName($source) -ne $allowed -or [IO.Path]::GetExtension($source) -ne '.py'){throw 'Task-local reviewed payload required'}
}
$bytes=[IO.File]::ReadAllBytes($source)
$hasher=[Security.Cryptography.SHA256]::Create()
try{$pin=[BitConverter]::ToString($hasher.ComputeHash($bytes)).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose()}
$data=[Convert]::ToBase64String($bytes)
$chunks=@([regex]::Matches($data,'.{1,1600}') | ForEach-Object {$_.Value})
$ready='__A_FRONTEND_CODE_READY__'
$bootstrap="import sys,base64,hashlib; print('$ready',flush=True); s=''.join(sys.stdin.readline().strip() for _ in range($($chunks.Count))); b=base64.b64decode(s,validate=True); assert hashlib.sha256(b).hexdigest()=='$pin'; exec(compile(b,'a_frontend_readonly_inventory','exec'))"
$line='sudo -p __A_FRONTEND_SUDO_AUTH__: /usr/bin/python3 -B -I -c "'+$bootstrap+'"'
$port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake=[IO.Ports.Handshake]::None;$port.DtrEnable=$false;$port.RtsEnable=$false;$port.NewLine="`r";$port.WriteTimeout=3000
function Receive([string]$pattern,[int]$seconds,[string]$initial=''){
    $buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    [void]$buffer.Append($initial)
    if($buffer.ToString() -match $pattern){return $buffer.ToString()}
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        [void]$buffer.Append($port.ReadExisting())
        if($buffer.Length -gt 131072){throw 'UART output exceeded inventory budget'}
        if($buffer.ToString() -match $pattern){return $buffer.ToString()}
        Start-Sleep -Milliseconds 50
    }
    throw 'UART inventory marker timeout; no retry'
}
$password=$null
try{
    $port.Open();$port.Write("`r");$null=Receive 'ubuntu@kria:[^\r\n]*\$\s*$' 5
    $port.WriteLine($line)
    $reply=Receive '(__A_FRONTEND_SUDO_AUTH__:\s*$|[\r\n]__A_FRONTEND_CODE_READY__[\r\n])' 8
    if($reply -match '__A_FRONTEND_SUDO_AUTH__:\s*$'){
        $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName=Join-Path $repo 'evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe';$info.Arguments='KV260 read-only preparation inventory'
        $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
        $child=[Diagnostics.Process]::Start($info);$password=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
        if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($password) -or $password.Contains("`n") -or $password.Contains("`r")){throw 'Authentication cancelled'}
        $port.WriteLine($password);$password=$null;$null=Receive '[\r\n]__A_FRONTEND_CODE_READY__[\r\n]' 10
    }
    $transferEcho=[Text.StringBuilder]::new()
    foreach($chunk in $chunks){
        $port.WriteLine($chunk);Start-Sleep -Milliseconds 20
        [void]$transferEcho.Append($port.ReadExisting())
        if($transferEcho.Length -gt 131072){throw 'UART payload echo exceeded budget'}
    }
    $deadline=if($Action -eq 'stage'){90}elseif($Action -eq 'run'){60}else{30}
    $reply=Receive '__TT10_UART_ROOT_SCENE_END__' $deadline $transferEcho.ToString()
    $match=[regex]::Match($reply,'(?s)__TT10_UART_ROOT_SCENE_BEGIN__\s*(\{[^\r\n]+\})\s*__TT10_UART_ROOT_SCENE_END__')
    if(-not $match.Success){throw 'Structured board inventory missing'}
    $value=$match.Groups[1].Value|ConvertFrom-Json
    [pscustomobject]@{scope=('PINNED_KV260_PREBOARD_'+$Action.ToUpperInvariant());utc=[DateTime]::UtcNow.ToString('o');source_sha256=$pin;credentials_logged=$false;inventory=$value} | ConvertTo-Json -Depth 14
    if($value.status -eq 'FAILED_PRESERVE_PARTIAL_STATE'){exit 2}
}finally{
    $password=$null
    if($port.IsOpen){$port.Close()};$port.Dispose()
}
