param([string]$OutputPath,[switch]$AuthorizedOnce,[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
$receiptPath=$OutputPath
$authorized=$AuthorizedOnce
$dry=$ValidateOnly
. "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly
$prior=Get-Content -Raw "$PSScriptRoot/../../../evidence/board_platform/A10_20261018_intake/candidate_boot_once_01.json"|ConvertFrom-Json
if($prior.reboot_commands_sent -ne 1 -or $prior.candidate_boot_commands_sent -ne 0 -or $prior.candidate_load -ne 'RAM_ONLY'){throw 'Not the reviewed interrupted preboot state'}
$info=($prior.events|Where-Object {$_.kind -eq 'candidate_integrity_result'}).text
if(-not(Test-CandidateInfo $info)){throw 'Original captured iminfo not verified'}
if($dry){[ordered]@{handshake='CR repeats reviewed read-only iminfo';temporary_bootargs=$bootargsCommand;boot=$bootCommand;reboot=$false;board_contact=$false}|ConvertTo-Json;exit 0}
if(-not $authorized -or -not $receiptPath){throw 'Exact single-boot authority required'}
$file=[IO.File]::Open($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_CONTINUE_ALREADY_LOADED_CANDIDATE_V1';events=@();boot_commands_sent=0;reboot_commands_sent=0;status='NOT_STARTED';error=$null;closed=$false}
$serial=$null
function Event([string]$kind,[string]$text){$report.events+=@{utc=[DateTime]::UtcNow.ToString('o');kind=$kind;text=$text}}
function Receive([string]$pattern,[int]$seconds){
    $b=[Text.StringBuilder]::new();$w=[Diagnostics.Stopwatch]::StartNew()
    while($w.Elapsed.TotalSeconds -lt $seconds){
        if($serial.BytesToRead -gt 0){
            [void]$b.Append($serial.ReadExisting())
            if($b.Length -gt 1048576){Event 'cap_partial' $b.ToString();throw 'Capture cap'}
            if((Normalize-Terminal $b.ToString()) -match $pattern){return $b.ToString()}
        }
        Start-Sleep -Milliseconds 25
    }
    Event 'timeout_partial' $b.ToString();throw 'Deadline; no automatic retry or reset'
}
try{
    $p=Get-PnpDevice -Class Ports -PresentOnly|Where-Object{$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $p){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    $serial.Open();$serial.Write("`r")
    $r=Receive '(?m)^(?:ZynqMP>|=>)\s*$' 8
    Event 'handshake_repeated_iminfo' $r
    if(-not(Test-CandidateInfo $r)){throw 'Fresh repeated iminfo not verified; no boot'}
    $serial.Write("printenv bootcmd`r");$r=Receive '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Event 'original_bootcmd' $r
    if(-not(Test-QueryResult $r) -or $r -notmatch '(?m)^bootcmd=run som\r?$'){throw 'Original bootcmd mismatch'}
    $serial.Write($bootargsCommand+"`r");$r=Receive '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Event 'temporary_bootargs' $r
    if(-not(Test-QueryResult $r)){throw 'Temporary parameter command failed'}
    $serial.Write("printenv bootargs`r");$r=Receive '(?m)^(?:ZynqMP>|=>)\s*$' 3
    Event 'temporary_bootargs_readback' $r
    if(-not(Test-QueryResult $r) -or -not $r.Contains('bootargs='+$bootargsCommand.Substring('setenv bootargs '.Length).Trim("'"))){throw 'Parameter readback mismatch'}
    Event 'single_candidate_boot' $bootCommand
    $report.boot_commands_sent=1;$serial.Write($bootCommand+"`r")
    Write-Host 'Single candidate boot command sent. Receiving only; no compute.'
    $r=Receive '(?m)^kria login:\s*$|Kernel panic|^(?:ZynqMP>|=>)\s*$' 100
    Event 'boot_capture' $r
    $report.status='CANDIDATE_BOOT_CAPTURED_REVIEW_REQUIRED'
}catch{$report.error=$_.Exception.Message;$report.status='STOPPED_REVIEW_REQUIRED'}
finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;$bytes=[Text.Encoding]::UTF8.GetBytes(($report|ConvertTo-Json -Depth 7))
    $file.Write($bytes,0,$bytes.Length);$file.Dispose()
}
Write-Host ($report.status+'; COM5 released; '+$receiptPath)
if($report.error){Write-Host $report.error;exit 2}
