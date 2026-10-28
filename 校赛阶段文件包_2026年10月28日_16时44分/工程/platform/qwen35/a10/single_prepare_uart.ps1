param(
    [Parameter(Mandatory=$true)][ValidateSet('root_stage','candidate_readonly','execute_single')][string]$Step,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-f-]{36}$')][string]$ExpectedBoot,
    [ValidateSet('6.8.12-a10irq2')][string]$ExpectedKernel='6.8.12-a10irq2',
    [string]$OutputPath,[switch]$AuthorizedOnce,[switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
if($ExpectedBoot -ne 'c5baeabe-273d-447e-b323-ff07dd7af201'){throw 'Exact reviewed boot required'}
$guard='set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = '+$ExpectedBoot+'; test "$(uname -r)" = '+$ExpectedKernel+'; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; test ! -d /sys/module/zocl; test ! -e /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active; test "$(cat /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status)" = applied; test "$(cat /sys/class/net/eth0/address)" = 00:0a:35:0f:2d:70; test "$(cat /sys/class/net/eth0/carrier)" = 1; python3 -c "from pathlib import Path; t=[int(p.read_text()) for p in Path(''/sys/class/hwmon'').glob(''hwmon*/temp*_input'')]; print(t); assert t and all(0<x<55000 for x in t)"; '
$helper=switch($Step){'root_stage' {'stage_isolated_single.py'} 'candidate_readonly' {'single_candidate_readonly.py'} 'execute_single' {'launch_isolated_single_once.py'}}
$code=[IO.File]::ReadAllBytes((Join-Path $PSScriptRoot $helper))
$h=[Security.Cryptography.SHA256]::Create()
try{$pin=[BitConverter]::ToString($h.ComputeHash($code)).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}
$ms=[IO.MemoryStream]::new()
$gz=[IO.Compression.GZipStream]::new($ms,[IO.Compression.CompressionMode]::Compress,$true)
$gz.Write($code,0,$code.Length);$gz.Dispose()
$blob=[Convert]::ToBase64String($ms.ToArray());$ms.Dispose()
$command=$guard+'sudo -n /usr/bin/python3 -B -I -c "import base64,gzip,hashlib; b=gzip.decompress(base64.b64decode('''+$blob+''')); assert hashlib.sha256(b).hexdigest()=='''+$pin+'''; exec(compile(b,''reviewed_'+$helper+''',''exec''))" '+$ExpectedBoot
if($ValidateOnly){[ordered]@{step=$Step;command=$command;board_contact=$false;boot_changes=$false;pl_or_compute=($Step -eq 'execute_single');compute=($Step -eq 'execute_single')}|ConvertTo-Json;exit 0}
if(-not $AuthorizedOnce -or -not $OutputPath){throw 'Explicit authorized step and exclusive receipt required'}
$receipt=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_SINGLE_PREPARATION_UART_V1';step=$Step;utc=[DateTime]::UtcNow.ToString('o');boot_id=$ExpectedBoot;kernel=$ExpectedKernel;command=$command;events=@();status='RESERVED';exit_code=$null;closed=$false;pl_loads=0;compute_runs=0;error=$null}
if($Step -eq 'execute_single'){$report.pl_loads=$null;$report.compute_runs=$null}
$serial=$null
$secret=$null
function Normalize([string]$text){return ([regex]::Replace($text,'\x1b\[[0-?]*[ -/]*[@-~]','')).Replace("`r",'')}
function Emit([string]$kind,[string]$text){
    if($secret){$text=$text.Replace($secret,'[REDACTED]')}
    $report.events+=@{kind=$kind;text=$text;utc=[DateTime]::UtcNow.ToString('o')}
}
function Receive([string]$pattern,[int]$seconds){
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 262144){Emit 'cap_partial' $buf.ToString();throw 'Serial receive cap'}
            if((Normalize $buf.ToString()) -match $pattern){return $buf.ToString()}
        }
        Start-Sleep -Milliseconds 30
    }
    Emit 'timeout_partial' $buf.ToString();throw 'Deadline: no retries or interrupts'
}
try {
    $p=Get-PnpDevice -Class Ports -PresentOnly|Where-Object{$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $p){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    $serial.Open();$serial.Write("`r")
    $hello=Receive '(?m)^ubuntu@kria:[^\n]*\$\s*$|login:|password:|ZynqMP>' 3
    Emit 'handshake' $hello
    if((Normalize $hello) -notmatch '(?m)^ubuntu@kria:[^\n]*\$\s*$' -or $hello -match 'login:|password:|ZynqMP>'){throw 'No authenticated Linux shell'}
    if($Step -in @('network','root_stage','normal_poweroff','candidate_readonly','execute_single')){
        $tag='AUTH_'+[guid]::NewGuid().ToString('N')
        $serial.Write('sudo -p ''__A10_ISOLATED_AUTH__:'' -v; a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'+"`r")
        $raw=Receive ('(?m)^__A10_ISOLATED_AUTH__:\s*$|^'+$tag+':\d+$') 5
        Emit 'auth_challenge_or_cache' $raw
        if((Normalize $raw) -match '(?m)^__A10_ISOLATED_AUTH__:\s*$'){
            Write-Host 'Exact board sudo challenge verified. Hidden transient credential input required.'
            $secure=Read-Host 'Board credential (not logged)' -AsSecureString
            $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}
            if(-not $secret -or $secret.Contains("`r") -or $secret.Contains("`n")){throw 'Invalid credential input'}
            $serial.Write($secret+"`r")
            $raw=Receive ('(?m)^'+$tag+':\d+$|^__A10_ISOLATED_AUTH__:\s*$') 5
            Emit 'auth_result' $raw
        }
        if((Normalize $raw) -notmatch ('(?m)^'+$tag+':0$')){throw 'Authorization unconfirmed: no network command sent'}
    }
    $tag='PREP_'+[guid]::NewGuid().ToString('N')
    $wire='( set -o pipefail; '+$command+' ); a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'+"`r"
    if([Text.Encoding]::UTF8.GetByteCount($wire) -gt 4094){throw 'Canonical TTY line cap: no command sent'}
    $serial.Write($wire)
    if($Step -eq 'normal_poweroff'){
        $raw=Receive ('reboot: Power down|(?m)^'+$tag+':[1-9][0-9]*$') 60
    }elseif($Step -eq 'execute_single'){
        $raw=Receive ('(?m)^'+$tag+':\d+$|"event": "QUARANTINED_MANAGER_AND_LOCKS_RETAINED"') 120
        Emit 'single_execution_output' $raw
        if($raw -match '"event": "QUARANTINED_MANAGER_AND_LOCKS_RETAINED"'){throw 'Manager quarantined; locks retained, no interrupt or cleanup'}
    }else{$raw=Receive ('(?m)^'+$tag+':\d+$') 30}
    Emit 'result' $raw
    if($Step -eq 'normal_poweroff'){
        if($raw -notmatch 'reboot: Power down'){throw 'Normal power down not confirmed; no power-cycle permission inferred'}
        $report.status='LINUX_NORMAL_POWER_DOWN_CONFIRMED'
    }else{
        $m=[regex]::Match((Normalize $raw),'(?m)^'+$tag+':(\d+)$')
        $report.exit_code=[int]$m.Groups[1].Value
        if($report.exit_code -ne 0){throw 'Step failed: inspect state; do not automatically retry'}
        $report.status='PREPARATION_COMPLETE_NOT_DEPLOYED_OR_BOOTED'
        if($Step -eq 'execute_single'){$report.status='SINGLE_COMMAND_EXITED_RECEIPT_REVIEW_REQUIRED'}
    }
}catch{$report.error=$_.Exception.Message;$report.status='STOPPED'}
finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;$json=$report|ConvertTo-Json -Depth 8
    if($secret){$json=$json.Replace($secret,'[REDACTED]')}
    $bytes=[Text.Encoding]::UTF8.GetBytes($json);$receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose();$secret=$null
}
Write-Host ($report.status+'; COM5 released; '+$OutputPath)
if($report.error){Write-Host $report.error;exit 2}
