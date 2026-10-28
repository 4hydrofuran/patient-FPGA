param([string]$OutputPath,[switch]$AuthorizedTemporaryNetwork)
$ErrorActionPreference='Stop'
if(-not $AuthorizedTemporaryNetwork -or -not $OutputPath){throw 'Existing volatile network authority and exclusive receipt required'}
$receiptPath=$OutputPath
. "$PSScriptRoot/../a10/inspect_boot_once.ps1" -DefinitionsOnly
$AuthorizedCandidateStage=$false;$deadline=30
$plan=@{command='sudo -n /usr/bin/python3 -B -I -c "import base64,gzip,hashlib,sys; b=gzip.decompress(base64.b64decode(''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'')); assert hashlib.sha256(b).hexdigest()==''6bac475d9a6940adc85bab17c0ac78b111ac97c93a74ca799936aff4b4008d61''; sys.argv=[''network_guard'',''86e4938b-0f65-4166-9237-c547b67e1451'']; exec(compile(b,''step08_network_guard'',''exec''))"'}
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
