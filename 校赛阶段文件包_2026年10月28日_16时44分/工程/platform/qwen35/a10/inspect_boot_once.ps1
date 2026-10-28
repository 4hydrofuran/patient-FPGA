param(
    [string]$OutputPath,
    [switch]$AuthorizedOnce,
    [switch]$DefinitionsOnly
)
$ErrorActionPreference='Stop'
$expectedBoot='0b6e8bb1-2219-4f67-b4f2-0a3e9718eaa1'
$preflight='set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = '+$expectedBoot+'; test "$(uname -r)" = 6.8.0-1015-xilinx; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; test "$(id -u)" = 1000; test ! -d /sys/module/zocl; test -d /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1; python3 -c "from pathlib import Path; t=[int(p.read_text()) for p in Path(''/sys/class/hwmon'').glob(''hwmon*/temp*_input'')]; print(''temperatures_mC'',t); assert t and all(0<x<60000 for x in t)"; cat /proc/loadavg; cat /proc/sys/kernel/random/boot_id'
function Normalize-Terminal([string]$Text) {
    return ([regex]::Replace($Text,'\x1b\[[0-?]*[ -/]*[@-~]','')).Replace("`r",'')
}
function Test-LinuxPrompt([string]$Text) {
    $Text=Normalize-Terminal $Text
    return ($Text -match '(?m)^ubuntu@kria:[^\r\n]*\$\s*$' -and $Text -notmatch '(?i)password:|kria login:|ZynqMP>')
}
function Test-BootPrompt([string]$Text) {
    $Text=Normalize-Terminal $Text
    return ($Text -match '(?m)^(?:ZynqMP>|=>)\s*$')
}
function Test-AutobootCountdown([string]$Text) {
    $Text=Normalize-Terminal $Text
    return ($Text -match '(?m)^U-Boot \d{4}\.\d+' -and
            $Text -match 'Hit any key to stop autoboot:\s*[1-9][0-9]*\s*$' -and
            $Text -notmatch 'Starting kernel|Linux version')
}
function Test-AuthPrompt([string]$Text) {
    $Text=Normalize-Terminal $Text
    return ($Text -match '(?m)^__A10_SUDO_AUTH__:\s*$')
}
function Test-QueryResult([string]$Text) {
    return ((Test-BootPrompt $Text) -and $Text -notmatch '(?i)unknown command|error|not found')
}
if($DefinitionsOnly){return}
if(-not $AuthorizedOnce -or -not $OutputPath){throw 'Explicit one-reboot authority and new evidence path required'}
# Exclusive evidence reservation prevents accidental reruns to the same receipt.
$receipt=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_ONE_NORMAL_REBOOT_INSPECTION_V1';utc=[DateTime]::UtcNow.ToString('o');status='NOT_STARTED';events=@();reboot_commands_sent=0;autoboot_stop_bytes_sent=0;candidate_load='NOT_PERFORMED';persistent_boot_changes='NOT_PERFORMED';board_compute='NOT_TESTED';closed=$false;error=$null}
$serial=$null
$secret=$null
function Add-Event([string]$Kind,[string]$Text) {
    if($secret){$Text=$Text.Replace($secret,'[REDACTED]')}
    $report.events+=@{utc=[DateTime]::UtcNow.ToString('o');kind=$Kind;text=$Text}
}
function Receive-Until([string]$Pattern,[int]$Seconds) {
    $buf=[Text.StringBuilder]::new()
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt $Seconds) {
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 524288){throw 'Serial capture cap'}
            if((Normalize-Terminal $buf.ToString()) -match $Pattern){return $buf.ToString()}
        }
        Start-Sleep -Milliseconds 25
    }
    Add-Event 'timeout_partial' $buf.ToString()
    throw 'Receive deadline; no retry, reset or interrupt'
}
try {
    $device=Get-PnpDevice -Class Ports -PresentOnly | Where-Object {
        $_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and
        $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'
    }
    if(-not $device){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false; $serial.RtsEnable=$false
    $serial.Handshake=[IO.Ports.Handshake]::None; $serial.WriteTimeout=1000
    $serial.Open(); $serial.Write("`r")
    $hello=Receive-Until '(?m)^ubuntu@kria:[^\r\n]*\$\s*$|login:|password:|ZynqMP>' 3
    Add-Event 'linux_handshake' $hello
    if(-not (Test-LinuxPrompt $hello)){throw 'No fresh authenticated Linux shell'}
    $tag='A10_'+[Guid]::NewGuid().ToString('N')
    $wire='( '+$preflight+' ); a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'
    Add-Event 'preflight_command' $wire
    $serial.Write($wire+"`r")
    $result=Receive-Until ('(?m)^'+$tag+':\d+\r?\nubuntu@kria:[^\r\n]*\$\s*$') 8
    Add-Event 'preflight_result' $result
    if($result -notmatch ('(?m)^'+$tag+':0\r?$')){throw 'Preflight failed; reboot not sent'}
    $authTag='AUTH_'+[Guid]::NewGuid().ToString('N')
    $wire='sudo -p ''__A10_SUDO_AUTH__:'' -v; a10_auth_rc=$?; printf ''\n'+$authTag+':%s\n'' "$a10_auth_rc"'
    $serial.Write($wire+"`r")
    $result=Receive-Until ('(?m)^__A10_SUDO_AUTH__:\s*$|^'+$authTag+':\d+\r?$') 5
    Add-Event 'auth_challenge_or_cached_result' $result
    if(Test-AuthPrompt $result) {
        Write-Host 'Verified sudo challenge from board. Enter credential at hidden local prompt.'
        $secure=Read-Host 'Transient board sudo credential (not logged)' -AsSecureString
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}
        finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}
        if(-not $secret -or $secret.Contains("`r") -or $secret.Contains("`n")){throw 'Invalid credential input'}
        $serial.Write($secret+"`r")
        $result=Receive-Until ('(?m)^'+$authTag+':\d+\r?$|^__A10_SUDO_AUTH__:\s*$') 5
        Add-Event 'auth_result' $result
    }
    if($result -notmatch ('(?m)^'+$authTag+':0\r?$')){throw 'Authentication not confirmed; no reboot sent'}
    # No command retry. Recheck the pinned boot and thermal guards immediately
    # before the only systemctl invocation. sudo -n cannot prompt after this point.
    $wire='( '+$preflight+' ) && sudo -n /usr/bin/systemctl reboot'
    Add-Event 'authorized_reboot_command' $wire
    $report.reboot_commands_sent=1
    $serial.Write($wire+"`r")
    $report.status='REBOOT_SENT_OUTCOME_PENDING'
    Write-Host 'One normal reboot command sent. Capturing startup; no reset or retry.'
    $buf=[Text.StringBuilder]::new()
    $timer=[Diagnostics.Stopwatch]::StartNew()
    $stopped=$false
    while($timer.Elapsed.TotalSeconds -lt 100) {
        if($serial.BytesToRead -gt 0) {
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 524288){throw 'Boot capture cap'}
            $text=$buf.ToString()
            if(-not $stopped -and (Test-AutobootCountdown $text)){
                $serial.Write(' ')
                $report.autoboot_stop_bytes_sent=1
                $stopped=$true
                Write-Host 'Fresh U-Boot countdown recognized; sent one space.'
            }
            if($stopped -and (Test-BootPrompt $text)){break}
            if($text -match '(?m)^kria login:\s*$'){break}
        }
        Start-Sleep -Milliseconds 25
    }
    Add-Event 'boot_capture' $buf.ToString()
    if(-not $stopped -or -not (Test-BootPrompt $buf.ToString())){
        $report.status='BOOT_CAPTURED_NOT_AT_VERIFIED_BOOTLOADER'
        throw 'No verified stopped U-Boot prompt; no retry/reboot/candidate action'
    }
    $report.status='AT_UBOOT_READONLY_INSPECTION'
    foreach($command in @('version','help','printenv bootcmd boot_targets bootdelay modeboot bootmode bootcount bootlimit altbootcmd')) {
        Add-Event 'readonly_uboot_command' $command
        $serial.Write($command+"`r")
        $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 5
        Add-Event 'readonly_uboot_result' $result
        # Unset requested env variables may report Error: ... not defined.
        # Keep that evidence and stop; never guess an alternative boot command.
        if(-not (Test-QueryResult $result)){throw 'Unsupported/error query; stopped at U-Boot, no boot action guessed'}
    }
    $report.status='INSPECTION_CAPTURED_AT_UBOOT_PENDING_REVIEW'
} catch {
    $report.error=$_.Exception.Message
    if($secret){$report.error=$report.error.Replace($secret,'[REDACTED]')}
    if($report.status -eq 'NOT_STARTED'){$report.status='STOPPED_BEFORE_REBOOT'}
    Write-Host ('Stopped: '+$report.error)
} finally {
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true
    $json=$report|ConvertTo-Json -Depth 8
    if($secret){$json=$json.Replace($secret,'[REDACTED]')}
    $bytes=[Text.Encoding]::UTF8.GetBytes($json)
    $receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose()
    $secret=$null
}
Write-Host ('Status: '+$report.status+'; COM5 released; receipt: '+$OutputPath)
if($report.error){exit 2}
