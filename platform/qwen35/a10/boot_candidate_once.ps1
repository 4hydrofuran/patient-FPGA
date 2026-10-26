param(
    [string]$OutputPath,
    [switch]$AuthorizedOnce,
    [switch]$DefinitionsOnly,
    [switch]$ValidateOnly,
    [ValidateSet('irq1','irq2')][string]$Candidate='irq1',
    [ValidatePattern('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
    [string]$ExpectedBootId='eb429b2f-66aa-4959-8610-bfcfabcf0202'
)
$ErrorActionPreference='Stop'
# A new authorized maintenance window must pass the boot ID from its fresh
# read-only receipt. The historical default remains pinned, not auto-detected.
if([Guid]$ExpectedBootId -eq [Guid]::Empty){throw 'Empty boot UUID prohibited'}
$expectedBoot=$ExpectedBootId
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
$preflight=$preflight.Replace('60000','55000')+'; test -d /usr/lib/modules/6.8.12-a10irq1; test "$(sha256sum /boot/firmware/image.fit | cut -d '' '' -f1)" = b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9; test "$(sha256sum /boot/firmware/boot.scr.uimg | cut -d '' '' -f1)" = 690fe1225a017a63796df1517b8b203fe9b7500597b2c5a61a0f524875ea2efc; test "$(sha256sum /boot/firmware/a10-candidate-20261020.fit | cut -d '' '' -f1)" = a393f397a673a2f3636c8b9f85d8a59f7257c24d33c34d28a67b11c410a11b81; python3 -c "import json; from pathlib import Path; r=[json.loads(s) for s in Path(''/home/ubuntu/a10-kernel-trial-20261020-v1/stage-result.jsonl'').read_text().splitlines()]; assert r[-1][''event'']==''STAGED_ONLY_NOT_BOOTED''"'
$preflight+='; test ! -e /var/lock/kv260-a1/active; test ! -L /var/lock/kv260-a1/active; test "$(sha256sum /usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko | cut -d '' '' -f1)" = 2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc'
$loadCommand='fatload mmc 1:1 0x10000000 a10-candidate-20261020.fit'
$infoCommand='iminfo 0x10000000'
$bootargsCommand='setenv bootargs ''root=LABEL=writable rootwait earlycon console=ttyPS1,115200 console=tty1 clk_ignore_unused uio_pdrv_genirq.of_id=generic-uio xilinx_tsn_ep.st_pcp=4 cma=800M'''
$bootCommand='bootm 0x10000000#conf-smk-k26-revA-sck-kv-g-revB'
$candidateBytes=65552664
$componentPins=@('1bbdfbe4b8ee040ca9131eab9c28d7d79ca8723efab66182932442d1f2e939d0','82e851dd2c3e294133311e6aadb368445c3bd7cddffbfecdceee51d93e7a9d7c','32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3')
if($Candidate -eq 'irq2'){
    if(-not $PSBoundParameters.ContainsKey('ExpectedBootId')){throw 'irq2 requires explicit fresh source boot ID'}
    $preflight=$preflight.Replace('6.8.12-a10irq1','6.8.12-a10irq2').Replace('a10-candidate-20261020.fit','a10-candidate-irq2-20261021.fit').Replace('a393f397a673a2f3636c8b9f85d8a59f7257c24d33c34d28a67b11c410a11b81','e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b').Replace('/home/ubuntu/a10-kernel-trial-20261020-v1/','/home/ubuntu/a10-irq2-stage-20261021-v1/').Replace('2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc','38992846680c0ddbdad7a05f6506b66488473a96c52975fa35a126b8401344f8')
    $loadCommand='fatload mmc 1:1 0x10000000 a10-candidate-irq2-20261021.fit'
    $candidateBytes=65555004
    $componentPins=@('0a132d4ac3905ec9815c8b4874bc34e825beff2f3fd2aa9bb96e82c364598e44','ac4dd7766229ba57edb884909b5a32dfce1faa7f31d520d0908d9c317612f3c5','32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3')
}
function Test-CandidateInfo([string]$Text){
    $t=Normalize-Terminal $Text
    if(-not(Test-QueryResult $t)){return $false}
    foreach($pin in ($componentPins+@('conf-smk-k26-revA-sck-kv-g-revB'))){
        if(-not $t.Contains($pin)){return $false}
    }
    $oldFormat=$t -match '## Checking hash\(es\) for FIT Image at 10000000'
    foreach($item in @('0 \(kernel\)','1 \(ramdisk\)','2 \(fdt\)')){
        $oldFormat=$oldFormat -and ($t -match ('(?m)^\s*Hash\(es\) for Image '+$item+': sha256\+\s*$'))
    }
    $newFormat=$t -match '(?is)Verifying Hash Integrity.*sha256\+.*OK'
    return (($oldFormat -or $newFormat) -and
            [regex]::Matches($t,'sha256\+').Count -eq 3 -and
            $t -notmatch '(?i)bad hash|unsupported|failed')
}
if($DefinitionsOnly){return}
if($ValidateOnly){[ordered]@{candidate=$Candidate;candidate_bytes=$candidateBytes;component_sha256=$componentPins;preflight=$preflight;load=$loadCommand;inspect=$infoCommand;temporary_bootargs=$bootargsCommand;boot=$bootCommand;board_contact=$false}|ConvertTo-Json;exit 0}
if($Candidate -eq 'irq1'){throw 'irq1 REJECTED: historical definitions/fixtures only; live boot prohibited'}
if(-not $AuthorizedOnce -or -not $OutputPath){throw 'Explicit one-reboot authority and new evidence path required'}
# Exclusive evidence reservation prevents accidental reruns to the same receipt.
$receipt=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_ONE_CANDIDATE_BOOT_V1';candidate=$Candidate;utc=[DateTime]::UtcNow.ToString('o');source_boot_id=$expectedBoot;status='NOT_STARTED';events=@();reboot_commands_sent=0;autoboot_stop_bytes_sent=0;candidate_load='NOT_PERFORMED';candidate_boot_commands_sent=0;persistent_boot_changes='NOT_PERFORMED';board_compute='NOT_TESTED';closed=$false;error=$null}
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
    $result=Receive-Until ('(?m)^'+$tag+':\d+\r?\nubuntu@kria:[^\r\n]*\$\s*$') 12
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
    foreach($command in @('version','help bootm','help iminfo','printenv bootcmd')) {
        Add-Event 'readonly_uboot_command' $command
        $serial.Write($command+"`r")
        $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 5
        Add-Event 'readonly_uboot_result' $result
        # Unset requested env variables may report Error: ... not defined.
        # Keep that evidence and stop; never guess an alternative boot command.
        if(-not (Test-QueryResult $result)){throw 'Unsupported/error query; stopped at U-Boot, no boot action guessed'}
        if($command -eq 'version' -and $result -notmatch 'U-Boot 2020\.01'){throw 'Unexpected bootloader version'}
        if($command -eq 'printenv bootcmd' -and $result -notmatch '(?m)^bootcmd=run som\r?$'){throw 'Unexpected original bootcmd'}
    }
    Add-Event 'candidate_ram_load' $loadCommand
    $serial.Write($loadCommand+"`r")
    $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 20
    Add-Event 'candidate_ram_load_result' $result
    if(-not(Test-QueryResult $result) -or $result -notmatch ('(?m)^'+$candidateBytes+' bytes read\b')){throw 'Candidate RAM load not verified'}
    $report.candidate_load='RAM_ONLY'
    $serial.Write($infoCommand+"`r")
    $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 15
    Add-Event 'candidate_integrity_result' $result
    if(-not(Test-CandidateInfo $result)){throw 'Old U-Boot candidate integrity/capability not verified; no boot sent'}
    $serial.Write($bootargsCommand+"`r")
    $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Add-Event 'temporary_bootargs_result' $result
    if(-not(Test-QueryResult $result)){throw 'Temporary bootargs command failed'}
    $serial.Write("printenv bootargs`r")
    $result=Receive-Until '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Add-Event 'temporary_bootargs_readback' $result
    $expectedArgs=$bootargsCommand.Substring('setenv bootargs '.Length).Trim("'")
    if(-not(Test-QueryResult $result) -or -not $result.Contains('bootargs='+$expectedArgs)){throw 'Temporary bootargs readback mismatch'}
    Add-Event 'single_candidate_boot_command' $bootCommand
    $report.candidate_boot_commands_sent=1
    $serial.Write($bootCommand+"`r")
    Write-Host 'Single candidate boot sent; passive log capture only.'
    $buf=[Text.StringBuilder]::new();$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 100){
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 524288){throw 'Candidate boot log cap'}
            $t=Normalize-Terminal $buf.ToString()
            if($t -match '(?m)^kria login:\s*$|Kernel panic|(?m)^(?:ZynqMP>|=>)\s*$'){break}
        }
        Start-Sleep -Milliseconds 25
    }
    Add-Event 'candidate_boot_capture' $buf.ToString()
    $report.status='CANDIDATE_BOOT_SENT_CAPTURED_REVIEW_REQUIRED'
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
