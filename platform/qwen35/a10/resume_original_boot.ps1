param([string]$OutputPath,[switch]$AuthorizedResumeOriginal,[switch]$ValidateOnly,[switch]$LoginOnly,[switch]$AuthorizedCandidateReadback,[switch]$AuthorizedReconnectReadOnly)
$ErrorActionPreference='Stop'
$receiptPath=$OutputPath
. "$PSScriptRoot/inspect_boot_once.ps1" -DefinitionsOnly
$postcheck='set -e; test "$(uname -r)" = 6.8.0-1015-xilinx; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; uname -a; cat /proc/sys/kernel/random/boot_id; cat /proc/cmdline; cat /proc/sys/kernel/tainted; test ! -d /sys/module/zocl; ls -l /sys/kernel/config/device-tree/overlays; cat /sys/class/fpga_manager/fpga0/state; grep -E "MemTotal|MemAvailable|CmaTotal|CmaFree" /proc/meminfo; python3 -c "from pathlib import Path; t=[int(p.read_text()) for p in Path(''/sys/class/hwmon'').glob(''hwmon*/temp*_input'')]; print(''temperatures_mC'',t); assert t and all(0<v<60000 for v in t)"; ip -br addr; /usr/bin/timeout 6 sha256sum /boot/firmware/image.fit /boot/firmware/boot.scr.uimg'
if($AuthorizedCandidateReadback){
    if(-not $LoginOnly -or $AuthorizedResumeOriginal){throw 'Candidate readback is login-only, not original-boot continuation'}
    $postcheck=$postcheck.Replace('6.8.0-1015-xilinx','6.8.12-a10irq1').Replace('60000','55000')+'; /usr/bin/timeout 4 modinfo -F vermagic zocl; /usr/bin/timeout 4 modinfo -F signer zocl; printf "KERNEL_LOG\n"; /usr/bin/timeout 5 journalctl -k -b --no-pager -o short-monotonic'
}
if($AuthorizedReconnectReadOnly){
    if(-not $LoginOnly -or $AuthorizedResumeOriginal -or $AuthorizedCandidateReadback){throw 'Reconnect is login/read-only, mutually exclusive'}
    $postcheck=$postcheck.Replace('test "$(uname -r)" = 6.8.0-1015-xilinx;', 'case "$(uname -r)" in 6.8.0-1015-xilinx|6.8.12-a10irq1) ;; *) exit 22;; esac;').Replace('60000','55000')
    $postcheck='set -o pipefail; '+$postcheck+'; printf "CANDIDATE_PRESERVATION\n"; /usr/bin/timeout 6 sha256sum /boot/firmware/a10-candidate-20261020.fit /usr/lib/modules/6.8.12-a10irq1/extra/zocl.ko; printf "KERNEL_LOG_COMPRESSED\n"; /usr/bin/timeout 8 journalctl -q -k -b --no-pager -o cat | python3 -c "import sys,zlib,base64,hashlib,json; b=sys.stdin.buffer.read(1048577); assert len(b)<=1048576; print(json.dumps(dict(bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),zlib_base64=base64.b64encode(zlib.compress(b)).decode())))"'
}
if($ValidateOnly){[ordered]@{readback=if($LoginOnly){'linux_login_prompt'}else{'printenv bootcmd som cc_boot'};resume=if($LoginOnly){$null}else{'run bootcmd'};postcheck=$postcheck}|ConvertTo-Json;exit 0}
if((-not $AuthorizedResumeOriginal -and -not $AuthorizedCandidateReadback -and -not $AuthorizedReconnectReadOnly) -or -not $receiptPath){throw 'Specific boot continuation or readback authority required'}
$receipt=[IO.File]::Open($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_RESUME_UNCHANGED_ORIGINAL_BOOT_V1';utc=[DateTime]::UtcNow.ToString('o');events=@();status='NOT_STARTED';resume_commands_sent=0;postcheck_exit=$null;error=$null;closed=$false;candidate_load='NOT_PERFORMED'}
if($AuthorizedCandidateReadback){$report.schema='A10_CANDIDATE_LINUX_LOGIN_READONLY_V1'}
if($AuthorizedReconnectReadOnly){$report.schema='A10_POWER_RESUME_LOGIN_READONLY_V1'}
$serial=$null;$secret=$null
function Add-ResumeEvent([string]$Kind,[string]$Text){
    if($secret){$Text=$Text.Replace($secret,'[REDACTED]')}
    $report.events+=@{utc=[DateTime]::UtcNow.ToString('o');kind=$Kind;text=$Text}
}
function Receive-Resume([string]$Pattern,[int]$Seconds){
    $buf=[Text.StringBuilder]::new();$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt $Seconds){
        if($serial.BytesToRead -gt 0){
            [void]$buf.Append($serial.ReadExisting())
            if($buf.Length -gt 1048576){throw 'Capture cap'}
            if((Normalize-Terminal $buf.ToString()) -match $Pattern){return $buf.ToString()}
        }
        Start-Sleep -Milliseconds 25
    }
    Add-ResumeEvent 'timeout_partial' $buf.ToString()
    throw 'Deadline; no retry or reset'
}
try {
    $device=Get-PnpDevice -Class Ports -PresentOnly | Where-Object {$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $device){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    # Last reviewed command was read-only fatls. Empty CR may repeat it in U-Boot.
    $serial.Open();$serial.Write("`r")
    if(-not $LoginOnly){
    $result=Receive-Resume '(?m)^ZynqMP>\s*$' 5
    Add-ResumeEvent 'uboot_handshake' $result
    $serial.Write("printenv bootcmd som cc_boot`r")
    $result=Receive-Resume '(?m)^ZynqMP>\s*$' 5
    Add-ResumeEvent 'original_boot_environment_recheck' $result
    $clean=Normalize-Terminal $result
    foreach($expected in @('bootcmd=run som','som=if test ${board_name} = ${starter} ; then run cc_boot; else bootmenu; fi','cc_boot=setenv boot_targets mmc1 && run distro_bootcmd')){
        if($clean.Split("`n") -notcontains $expected){throw 'Original boot environment changed'}
    }
    if(-not(Test-QueryResult $result)){throw 'Environment query failed'}
    $report.resume_commands_sent=1
    $report.status='ORIGINAL_BOOT_COMMAND_SENT'
    Add-ResumeEvent 'resume_command' 'run bootcmd'
    $serial.Write("run bootcmd`r")
    Write-Host 'Continuing reviewed original SD boot once; no additional reboot.'
    $result=Receive-Resume '(?m)^kria login:\s*$|^ZynqMP>\s*$' 100
    Add-ResumeEvent 'original_boot_capture' $result
    if((Normalize-Terminal $result) -notmatch '(?m)^kria login:\s*$'){throw 'Original boot returned to U-Boot; no retry'}
    } else {
        $result=Receive-Resume '(?m)^kria login:\s*$|^ubuntu@kria:[^\n]*\$\s*$|^ZynqMP>\s*$|^Password:\s*$' 5
        Add-ResumeEvent 'login_only_handshake' $result
        if((Normalize-Terminal $result) -notmatch '(?m)^kria login:\s*$|^ubuntu@kria:[^\n]*\$\s*$'){throw 'Not a verified Linux login/shell; no credentials or command sent'}
    }
    $report.status=if($AuthorizedReconnectReadOnly){'RECONNECTED_KERNEL_CHECK_PENDING'}elseif($AuthorizedCandidateReadback){'CANDIDATE_LOGIN_REACHED_KERNEL_NOT_YET_VERIFIED'}else{'ORIGINAL_LINUX_LOGIN_REACHED'}
    if(-not (Test-LinuxPrompt $result)){
    $serial.Write("ubuntu`r")
    $result=Receive-Resume '(?m)^Password:\s*$|^ubuntu@kria:[^\n]*\$\s*$|Login incorrect' 5
    Add-ResumeEvent 'login_challenge' $result
    if((Normalize-Terminal $result) -match '(?m)^Password:\s*$'){
        Write-Host 'Verified Linux login password challenge. Hidden transient credential input required.'
        $secure=Read-Host 'Transient board login credential (not logged)' -AsSecureString
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}
        finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}
        if(-not $secret -or $secret.Contains("`r") -or $secret.Contains("`n")){throw 'Invalid credential input'}
        $serial.Write($secret+"`r")
        $result=Receive-Resume '(?m)^ubuntu@kria:[^\n]*\$\s*$|Login incorrect|current.*password' 15
        Add-ResumeEvent 'login_result' $result
    }
    if(-not(Test-LinuxPrompt $result)){throw 'No verified Linux shell after login; no commands sent'}
    }
    $tag='POST_'+[Guid]::NewGuid().ToString('N')
    $wire='( '+$postcheck+' ); a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'
    Add-ResumeEvent 'postcheck_command' $wire
    $serial.Write($wire+"`r")
    $result=Receive-Resume ('(?m)^'+$tag+':\d+\r?\nubuntu@kria:[^\n]*\$\s*$') 20
    Add-ResumeEvent 'postcheck_result' $result
    $m=[regex]::Match((Normalize-Terminal $result),'(?m)^'+$tag+':(\d+)$')
    if(-not $m.Success){throw 'Missing postcheck exit'}
    $report.postcheck_exit=[int]$m.Groups[1].Value
    if($report.postcheck_exit -ne 0){throw 'Postcheck failed; stop'}
    $report.status=if($AuthorizedReconnectReadOnly){'POWER_RESUME_READBACK_COMPLETE_LOG_REVIEW_PENDING'}elseif($AuthorizedCandidateReadback){'CANDIDATE_LINUX_READBACK_COMPLETE_LOG_REVIEW_PENDING'}else{'ORIGINAL_LINUX_RESTORED_READBACK_COMPLETE'}
}catch{
    $report.error=$_.Exception.Message
    if($secret){$report.error=$report.error.Replace($secret,'[REDACTED]')}
    Write-Host ('Stopped: '+$report.error)
}finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;$json=$report|ConvertTo-Json -Depth 8
    if($secret){$json=$json.Replace($secret,'[REDACTED]')}
    $bytes=[Text.Encoding]::UTF8.GetBytes($json);$receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose();$secret=$null
}
Write-Host ('Status: '+$report.status+'; COM5 released; receipt: '+$receiptPath)
if($report.error){exit 2}
