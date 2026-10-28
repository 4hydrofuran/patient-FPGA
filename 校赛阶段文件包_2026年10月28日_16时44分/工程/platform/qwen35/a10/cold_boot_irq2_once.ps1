param([string]$OutputPath,[switch]$AuthorizedOnce,[switch]$DefinitionsOnly,[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
$candidateBytes=65555004
$componentPins=@('0a132d4ac3905ec9815c8b4874bc34e825beff2f3fd2aa9bb96e82c364598e44','ac4dd7766229ba57edb884909b5a32dfce1faa7f31d520d0908d9c317612f3c5','32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3')
$loadCommand='fatload mmc 1:1 0x10000000 a10-candidate-irq2-20261021.fit'
$argsText='root=LABEL=writable rootwait earlycon console=ttyPS1,115200 console=tty1 clk_ignore_unused uio_pdrv_genirq.of_id=generic-uio xilinx_tsn_ep.st_pcp=4 cma=800M'
$bootCommand='bootm 0x10000000#conf-smk-k26-revA-sck-kv-g-revB'
function Normalize-Cold([string]$text){return ([regex]::Replace($text,'\x1b\[[0-?]*[ -/]*[@-~]','')).Replace("`r",'')}
function Test-ColdPrompt([string]$text){return ((Normalize-Cold $text) -match '(?m)^(?:ZynqMP>|=>)\s*$')}
function Test-ColdCountdown([string]$text){
    $t=Normalize-Cold $text
    return ($t -match '(?m)^U-Boot 2020\.01' -and $t -match 'Hit any key to stop autoboot:\s*[1-9][0-9]*\s*$' -and $t -notmatch 'Starting kernel|Linux version')
}
function Test-ColdQuery([string]$text){return ((Test-ColdPrompt $text) -and $text -notmatch '(?i)unknown command|error|not found|failed')}
function Test-ColdLogin([string]$text){
    $t=Normalize-Cold $text
    return ($t -match '(?m)^kria login:' -and $t -notmatch '\b(?:Kernel panic|Oops:|BUG:)')
}
function Test-ColdInfo([string]$text){
    $t=Normalize-Cold $text
    if(-not(Test-ColdQuery $t)){return $false}
    foreach($pin in ($componentPins+@('conf-smk-k26-revA-sck-kv-g-revB'))){if(-not $t.Contains($pin)){return $false}}
    $oldFormat=$t -match '## Checking hash\(es\) for FIT Image at 10000000'
    foreach($item in @('0 \(kernel\)','1 \(ramdisk\)','2 \(fdt\)')){$oldFormat=$oldFormat -and ($t -match ('(?m)^\s*Hash\(es\) for Image '+$item+': sha256\+\s*$'))}
    $newFormat=$t -match '(?is)Verifying Hash Integrity.*sha256\+.*OK'
    return (($oldFormat -or $newFormat) -and [regex]::Matches($t,'sha256\+').Count -eq 3 -and $t -notmatch '(?i)bad hash|unsupported|failed')
}
if($DefinitionsOnly){return}
if($ValidateOnly){[ordered]@{board_contact=$false;reboot_commands=0;load=$loadCommand;bytes=$candidateBytes;hashes=$componentPins;temporary_bootargs=$argsText;boot=$bootCommand;default_boot_changed=$false}|ConvertTo-Json;exit 0}
if(-not $AuthorizedOnce -or -not $OutputPath){throw 'One authorized cold-start window and exclusive receipt required'}
$receipt=[IO.File]::Open($OutputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_ONE_MANUAL_COLD_IRQ2_BOOT_V1';utc=[DateTime]::UtcNow.ToString('o');status='RESERVED';events=@();autoboot_stop_bytes_sent=0;boot_commands_sent=0;reboot_commands_sent=0;default_boot_changed=$false;pl_loads=0;compute_runs=0;closed=$false;error=$null}
$serial=$null
function Event([string]$kind,[string]$text){
    $report.events+=@{kind=$kind;text=$text;utc=[DateTime]::UtcNow.ToString('o')}
    $bytes=[Text.Encoding]::UTF8.GetBytes(($report|ConvertTo-Json -Depth 8))
    $receipt.Position=0;$receipt.Write($bytes,0,$bytes.Length);$receipt.SetLength($bytes.Length);$receipt.Flush()
}
function Receive-Cold([string]$pattern,[int]$seconds){
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 524288){Event 'capture_cap' $buf.ToString();throw 'Capture cap'}
            if((Normalize-Cold $buf.ToString()) -match $pattern){return $buf.ToString()}
        }
        Start-Sleep -Milliseconds 20
    }
    Event 'timeout_partial' $buf.ToString();throw 'Capture deadline: no retry/reset/interrupt'
}
try{
    $p=Get-PnpDevice -Class Ports -PresentOnly|Where-Object{$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $p){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    $serial.Open()
    $report.status='ARMED_PASSIVE_WAIT_FOR_USER_POWER'
    Event 'armed' 'No input sent. Awaiting fresh U-Boot countdown.'
    Write-Host 'ARMED: COM5 passive capture ready. No power/reset command sent.'
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew();$stopped=$false
    while($watch.Elapsed.TotalSeconds -lt 300){
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting());$text=$buf.ToString()
            if($buf.Length -gt 524288){throw 'Capture cap'}
            if(Test-ColdCountdown $text){$serial.Write(' ');$report.autoboot_stop_bytes_sent=1;$stopped=$true;break}
            if($text -match 'Starting kernel|Linux version|kria login:'){throw 'Missed countdown: no command or automatic reboot'}
        }
        Start-Sleep -Milliseconds 20
    }
    Event 'fresh_boot_capture' $buf.ToString()
    if(-not $stopped){throw 'No fresh countdown: no bytes sent'}
    $result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 5
    Event 'stopped_boot_prompt' $result
    if(-not(Test-ColdPrompt $result)){throw 'No verified U-Boot prompt'}
    foreach($command in @('version','help bootm','help iminfo','printenv bootcmd')){
        $serial.Write($command+"`r");$result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 5
        Event ('query:'+ $command) $result
        if(-not(Test-ColdQuery $result)){throw 'Bootloader query failed'}
        if($command -eq 'version' -and $result -notmatch 'U-Boot 2020\.01'){throw 'Bootloader version differs'}
        if($command -eq 'printenv bootcmd' -and $result -notmatch '(?m)^bootcmd=run som\r?$'){throw 'Default bootcmd differs'}
    }
    $serial.Write($loadCommand+"`r");$result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 20
    Event 'candidate_ram_load' $result
    if(-not(Test-ColdQuery $result) -or $result -notmatch ('(?m)^'+$candidateBytes+' bytes read\b')){throw 'RAM load mismatch'}
    $serial.Write("iminfo 0x10000000`r");$result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 15
    Event 'candidate_integrity' $result
    if(-not(Test-ColdInfo $result)){throw 'Candidate component hash mismatch: boot not sent'}
    $serial.Write("setenv bootargs '$argsText'`r");$result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Event 'temporary_bootargs_set' $result
    if(-not(Test-ColdQuery $result)){throw 'Temporary args failed'}
    $serial.Write("printenv bootargs`r");$result=Receive-Cold '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Event 'temporary_bootargs_readback' $result
    if(-not(Test-ColdQuery $result) -or -not $result.Contains('bootargs='+$argsText)){throw 'Temporary args mismatch'}
    $report.boot_commands_sent=1;Event 'single_candidate_boot_command' $bootCommand
    $serial.Write($bootCommand+"`r")
    Write-Host 'One candidate boot sent. Passive capture only.'
    $result=Receive-Cold '(?m)^kria login:\s*$|Kernel panic|(?m)^(?:ZynqMP>|=>)\s*$' 120
    Event 'candidate_boot_log' $result
    if(-not(Test-ColdLogin $result)){throw 'Candidate login not cleanly observed'}
    $report.status='CANDIDATE_LOGIN_OBSERVED_READONLY_CHECK_REQUIRED'
}catch{$report.error=$_.Exception.Message;$report.status='STOPPED_NO_AUTOMATIC_RECOVERY'}
finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;Event 'serial_closed' 'No PL or compute commands sent.';$receipt.Dispose()
}
Write-Host ($report.status+'; COM5 released; '+$OutputPath)
if($report.error){Write-Host $report.error;exit 2}
