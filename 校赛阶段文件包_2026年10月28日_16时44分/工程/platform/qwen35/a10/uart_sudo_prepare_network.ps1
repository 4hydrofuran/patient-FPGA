param([string]$OutputPath,[switch]$AuthorizedTemporaryNetwork,[switch]$AuthorizedCandidateStage,[switch]$ValidateOnly,
      [ValidateSet('network','stage')][string]$Irq2Action,
      [ValidatePattern('^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')]
      [string]$CandidateIdleBootId)
$ErrorActionPreference='Stop'
$receiptPath=$OutputPath
. "$PSScriptRoot/inspect_boot_once.ps1" -DefinitionsOnly
$plan=& "$PSScriptRoot/driver_board_step.ps1" -Step temporary_candidate_nm -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
if($CandidateIdleBootId){
    if(-not $AuthorizedTemporaryNetwork -or $AuthorizedCandidateStage){throw 'Candidate idle boot applies only to authorized temporary network'}
    $plan=& "$PSScriptRoot/driver_board_step.ps1" -Step candidate_idle_network -CandidateBootId $CandidateIdleBootId -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
}
$deadline=30
if($AuthorizedCandidateStage -and -not $Irq2Action){
    if($AuthorizedTemporaryNetwork){throw 'Select only one authorized action'}
    $upload=Get-Content -Raw "$PSScriptRoot/../../local/a10-candidate-transfer-20261020-v1/upload-readback.json"|ConvertFrom-Json
    if($upload.status -ne 'UPLOADED_HASH_VERIFIED_NOT_INSTALLED'){throw 'Verified upload required'}
    $checks=@()
    foreach($name in @('stage_candidate_board.py','original_module_backup.py','original-backup-proof.json')){
        $hash=$upload.hashes.$name
        if($hash -notmatch '^[a-f0-9]{64}$'){throw 'Invalid source pin'}
        $checks+=('test "$(sha256sum '+$name+' | cut -d '' '' -f1)" = '+$hash)
    }
    $plan.command='set -e; cd /home/ubuntu/a10-kernel-trial-20261020-v1; '+($checks -join '; ')+'; sudo -n /usr/bin/python3 -B stage_candidate_board.py --execute-authorized --backup-proof-sha256 '+$upload.hashes.'original-backup-proof.json'
    $deadline=180
}
if($Irq2Action){
    if($CandidateIdleBootId -or ($AuthorizedTemporaryNetwork -and $AuthorizedCandidateStage)){throw 'Ambiguous irq2 action'}
    if(($Irq2Action -eq 'network' -and -not $AuthorizedTemporaryNetwork) -or ($Irq2Action -eq 'stage' -and -not $AuthorizedCandidateStage)){throw 'Matching explicit irq2 authority required'}
    $plan=& "$PSScriptRoot/irq2_uart_plan.ps1" -Action $Irq2Action | ConvertFrom-Json
    if($Irq2Action -eq 'stage'){$deadline=180}
}
if($ValidateOnly){$plan|ConvertTo-Json;exit 0}
if((-not $AuthorizedTemporaryNetwork -and -not $AuthorizedCandidateStage) -or -not $receiptPath){throw 'Exact action authority and fresh receipt required'}
$receipt=[IO.File]::Open($receiptPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
$report=[ordered]@{schema='A10_UART_TEMP_NETWORK_WITH_PROMPT_AUTH_V1';utc=[DateTime]::UtcNow.ToString('o');events=@();status='NOT_STARTED';exit_code=$null;error=$null;closed=$false}
if($AuthorizedCandidateStage){$report.schema='A10_UART_ADDITIVE_CANDIDATE_STAGE_V1'}
$serial=$null;$secret=$null
function Emit([string]$kind,[string]$text){if($secret){$text=$text.Replace($secret,'[REDACTED]')};$report.events+=@{kind=$kind;text=$text;utc=[DateTime]::UtcNow.ToString('o')}}
function Receive([string]$pattern,[int]$seconds){
    $buf=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    while($watch.Elapsed.TotalSeconds -lt $seconds){
        if($serial.BytesToRead -gt 0){[void]$buf.Append($serial.ReadExisting());if($buf.Length -gt 1048576){Emit 'cap_partial' $buf.ToString();throw 'Receive cap; partial retained'};if((Normalize-Terminal $buf.ToString()) -match $pattern){return $buf.ToString()}}
        Start-Sleep -Milliseconds 25
    }
    Emit 'timeout_partial' $buf.ToString();throw 'Deadline; no automatic retry'
}
try{
    $p=Get-PnpDevice -Class Ports -PresentOnly|Where-Object{$_.InstanceId -eq 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000' -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK'}
    if(-not $p){throw 'COM5 identity mismatch'}
    $serial=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $serial.DtrEnable=$false;$serial.RtsEnable=$false;$serial.Handshake=[IO.Ports.Handshake]::None;$serial.WriteTimeout=1000
    $serial.Open();$serial.Write("`r");$raw=Receive '(?m)^ubuntu@kria:[^\n]*\$\s*$|login:|password:|ZynqMP>' 3
    Emit 'handshake' $raw;if(-not(Test-LinuxPrompt $raw)){throw 'No verified Linux shell'}
    $tag='AUTH_'+[Guid]::NewGuid().ToString('N')
    $serial.Write('sudo -p ''__A10_SUDO_AUTH__:'' -v; a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'+"`r")
    $raw=Receive ('(?m)^__A10_SUDO_AUTH__:\s*$|^'+$tag+':\d+$') 5
    Emit 'auth_challenge_or_cache' $raw
    if(Test-AuthPrompt $raw){
        Write-Host 'Verified board sudo challenge; transient hidden input required.'
        $secure=Read-Host 'Board credential (not logged)' -AsSecureString
        $ptr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        try{$secret=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr);$secure.Dispose()}
        if(-not $secret -or $secret.Contains("`r") -or $secret.Contains("`n")){throw 'Invalid credential input'}
        $serial.Write($secret+"`r");$raw=Receive ('(?m)^'+$tag+':\d+$|^__A10_SUDO_AUTH__:\s*$') 5
        Emit 'auth_result' $raw
    }
    if((Normalize-Terminal $raw) -notmatch ('(?m)^'+$tag+':0$')){throw 'Auth unconfirmed; action not sent'}
    $tag='NETWORK_'+[Guid]::NewGuid().ToString('N')
    $wire='( set -o pipefail; '+$plan.command+' ); a10_rc=$?; printf ''\n'+$tag+':%s\n'' "$a10_rc"'
    Emit 'command' $wire;$serial.Write($wire+"`r")
    $raw=Receive ('(?m)^'+$tag+':\d+$') $deadline;Emit 'result' $raw
    $m=[regex]::Match((Normalize-Terminal $raw),'(?m)^'+$tag+':(\d+)$')
    $report.exit_code=[int]$m.Groups[1].Value
    if($report.exit_code -ne 0){throw 'Action failed; inspect actual state, no retry'}
    $report.status=if($AuthorizedCandidateStage){'CANDIDATE_STAGE_COMMAND_COMPLETE_NOT_BOOTED'}else{'TEMPORARY_NETWORK_COMMAND_COMPLETE'}
}catch{$report.error=$_.Exception.Message;$report.status='STOPPED_REVIEW_REQUIRED'}
finally{
    if($serial){if($serial.IsOpen){$serial.Close()};$serial.Dispose()}
    $report.closed=$true;$json=$report|ConvertTo-Json -Depth 8
    if($secret){$json=$json.Replace($secret,'[REDACTED]')}
    $bytes=[Text.Encoding]::UTF8.GetBytes($json);$receipt.Write($bytes,0,$bytes.Length);$receipt.Dispose();$secret=$null
}
Write-Host ($report.status+'; COM5 released; '+$receiptPath)
if($report.error){Write-Host $report.error;exit 2}
