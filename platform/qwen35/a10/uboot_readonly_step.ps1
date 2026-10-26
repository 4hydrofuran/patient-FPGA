param(
    [Parameter(Mandatory=$true)][ValidateSet('som','carrier','distro','boot_files')][string]$Step,
    [Parameter(Mandatory=$true)][string]$OutputPath,
    [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$receiptPath=$OutputPath
. "$PSScriptRoot/inspect_boot_once.ps1" -DefinitionsOnly
$commands=@{
    som=@('printenv som','bdinfo','help bootm','help fatload')
    carrier=@('printenv board_name starter cc_boot')
    distro=@('printenv distro_bootcmd bootcmd_mmc1 mmc_boot scan_dev_for_boot_part scan_dev_for_boot scan_dev_for_scripts boot_a_script scan_dev_for_extlinux scan_dev_for_efi boot_prefixes boot_scripts scriptaddr')
    boot_files=@('printenv boot_syslinux_conf card1_name card1_rev','part list mmc 1','fatls mmc 1:1 /')
}
if($ValidateOnly){$commands[$Step];exit 0}
$receipt=[IO.File]::Open($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_UBOOT_READONLY_STEP_V1';step=$Step;utc=[DateTime]::UtcNow.ToString('o');events=@();status='NOT_STARTED';error=$null;closed=$false}
$serial=$null
function Receive-BootPrompt {
    $buf=[Text.StringBuilder]::new();$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 5) {
        if($serial.BytesToRead -gt 0) {
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 131072){throw 'Capture cap'}
            if(Test-BootPrompt $buf.ToString()){return $buf.ToString()}
        }
        Start-Sleep -Milliseconds 25
    }
    $report.events+=@{kind='timeout_partial';text=$buf.ToString()}
    throw 'No verified U-Boot prompt; no retry'
}
try {
    $device=Get-PnpDevice -Class Ports -PresentOnly | Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $device){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    $serial.Open();$serial.Write("`r")
    $hello=Receive-BootPrompt
    $report.events+=@{kind='handshake';text=$hello}
    foreach($command in $commands[$Step]){
        $serial.Write($command+"`r");$result=Receive-BootPrompt
        $report.events+=@{command=$command;text=$result}
        if(-not(Test-QueryResult $result)){throw 'Query returned error; stop for review'}
    }
    $report.status='READONLY_CAPTURED_AT_UBOOT'
} catch {$report.error=$_.Exception.Message;$report.status='STOPPED_REVIEW_REQUIRED'}
finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;$bytes=[Text.Encoding]::UTF8.GetBytes(($report|ConvertTo-Json -Depth 8))
    $receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose()
}
$report|ConvertTo-Json -Depth 8
if($report.error){exit 2}
