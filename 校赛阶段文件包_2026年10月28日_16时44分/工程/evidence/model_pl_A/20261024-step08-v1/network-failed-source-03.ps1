param([string]$OutputPath,[switch]$AuthorizedTemporaryNetwork)
$ErrorActionPreference='Stop'
if(-not $AuthorizedTemporaryNetwork -or -not $OutputPath){throw 'Existing volatile network authority and exclusive receipt required'}
$receiptPath=$OutputPath
. "$PSScriptRoot/../a10/inspect_boot_once.ps1" -DefinitionsOnly
$AuthorizedCandidateStage=$false;$deadline=30
$plan=@{command='sudo -n /usr/bin/python3 -B -I -c "import base64,hashlib,sys; b=base64.b64decode(''IiIiUmVzdG9yZSBvbmx5IHRoZSBhdXRob3JpemVkIHZvbGF0aWxlIGRpcmVjdCBhZGRyZXNzIGFmdGVyIGV4YWN0IGJvb3QgaWRlbnRpdHkuIiIiCmltcG9ydCBmY250bAppbXBvcnQgaGFzaGxpYgppbXBvcnQganNvbgppbXBvcnQgb3MKZnJvbSBwYXRobGliIGltcG9ydCBQYXRoCmltcG9ydCBzdGF0CmltcG9ydCBzdWJwcm9jZXNzCmltcG9ydCBzeXMKCmRlZiBtYWluKGJvb3QpOgogICAgYXNzZXJ0IG9zLmdldGV1aWQoKT09MCBhbmQgb3MudW5hbWUoKS5yZWxlYXNlPT0nNi44LjEyLWExMGlycTInCiAgICBhc3NlcnQgUGF0aCgnL3Byb2Mvc3lzL2tlcm5lbC9yYW5kb20vYm9vdF9pZCcpLnJlYWRfdGV4dCgpLnN0cmlwKCk9PWJvb3QKICAgIGFzc2VydCBoYXNobGliLnNoYTI1NihQYXRoKCcvZXRjL21hY2hpbmUtaWQnKS5yZWFkX2J5dGVzKCkpLmhleGRpZ2VzdCgpPT0nZWE0ZWE3MTQyMDBlNTAxODFjNDM3NWIzODViMWUzYzRhMGY2ZDE5OWNjYjYwMTgyZDYyZjg2YmNmNDdiNjRlYycKICAgIGFzc2VydCBub3QgUGF0aCgnL3N5cy9tb2R1bGUvem9jbCcpLmV4aXN0cygpIGFuZCBub3QgUGF0aCgnL3Zhci9sb2NrL2t2MjYwLWExL2FjdGl2ZScpLmV4aXN0cygpCiAgICBhc3NlcnQgUGF0aCgnL3N5cy9rZXJuZWwvY29uZmlnL2RldmljZS10cmVlL292ZXJsYXlzL2syNi1zdGFydGVyLWtpdHNfaW1hZ2VfMS9zdGF0dXMnKS5yZWFkX3RleHQoKS5zdHJpcCgpPT0nYXBwbGllZCcKICAgIGFzc2VydCBQYXRoKCcvc3lzL2NsYXNzL25ldC9ldGgwL2NhcnJpZXInKS5yZWFkX3RleHQoKS5zdHJpcCgpPT0nMScKICAgIGRlc2NyaXB0b3JzPVtdCiAgICBmb3IgbmFtZSBpbiAoJy92YXIvbG9jay9rdjI2MC1hMS9kZXBsb3ltZW50LmxvY2snLCcvcnVuL2xvY2svcGF0aWVudC1xd2VuLWxpbmVhci5sb2NrJyk6CiAgICAgICAgZmQ9b3Mub3BlbihuYW1lLG9zLk9fUkRXUnxvcy5PX0NSRUFUfG9zLk9fTk9GT0xMT1csMG82MDApCiAgICAgICAgcz1vcy5mc3RhdChmZCk7YXNzZXJ0IHMuc3RfdWlkPT0wIGFuZCBzdGF0LlNfSVNSRUcocy5zdF9tb2RlKQogICAgICAgIGZjbnRsLmZsb2NrKGZkLGZjbnRsLkxPQ0tfRVh8ZmNudGwuTE9DS19OQik7ZGVzY3JpcHRvcnMuYXBwZW5kKGZkKQogICAgZGVmIGFkZHJlc3NlcygpOgogICAgICAgIGxpbmtzPWpzb24ubG9hZHMoc3VicHJvY2Vzcy5jaGVja19vdXRwdXQoWydpcCcsJy1qJywnYWRkcicsJ3Nob3cnLCdkZXYnLCdldGgwJ10pKQogICAgICAgIGFzc2VydCBsZW4obGlua3MpPT0xIGFuZCBsaW5rc1swXVsnaWZuYW1lJ109PSdldGgwJwogICAgICAgIHJldHVybiBbeCBmb3IgeCBpbiBsaW5rc1swXVsnYWRkcl9pbmZvJ10gaWYgeFsnZmFtaWx5J109PSdpbmV0J10KICAgIGJlZm9yZT1hZGRyZXNzZXMoKTt3YW50ZWQ9W3ggZm9yIHggaW4gYmVmb3JlIGlmIHhbJ2xvY2FsJ109PScxOTIuMTY4LjIuMicgYW5kIHhbJ3ByZWZpeGxlbiddPT0yNF0KICAgIGFzc2VydCBub3QgYmVmb3JlIG9yIGxlbihiZWZvcmUpPT1sZW4od2FudGVkKT09MSwnVW5leHBlY3RlZCBJUHY0OiBubyBkZWxldGlvbiBvciByZXBsYWNlbWVudCcKICAgIGlmIG5vdCBiZWZvcmU6c3VicHJvY2Vzcy5ydW4oWydpcCcsJ2FkZHInLCdhZGQnLCcxOTIuMTY4LjIuMi8yNCcsJ2RldicsJ2V0aDAnXSxjaGVjaz1UcnVlLHRpbWVvdXQ9NSkKICAgIGFmdGVyPWFkZHJlc3NlcygpO2Fzc2VydCBsZW4oYWZ0ZXIpPT0xIGFuZCBhZnRlclswXVsnbG9jYWwnXT09JzE5Mi4xNjguMi4yJyBhbmQgYWZ0ZXJbMF1bJ3ByZWZpeGxlbiddPT0yNAogICAgcHJpbnQoanNvbi5kdW1wcyhkaWN0KHN0YXR1cz0nVk9MQVRJTEVfRElSRUNUX0FERFJFU1NfVkVSSUZJRUQnLGJvb3RfaWQ9Ym9vdCxiZWZvcmU9YmVmb3JlLGFmdGVyPWFmdGVyLAogICAgICAgIHBlcnNpc3RlbnRfbmV0d29ya19jaGFuZ2VkPUZhbHNlLHJlYm9vdF9jb21tYW5kcz0wLFBMX2NoYW5nZXM9MCxtb2RlbF9zdWJtaXNzaW9ucz0wKSksZmx1c2g9VHJ1ZSkKICAgIGZvciBmZCBpbiBkZXNjcmlwdG9yczpvcy5jbG9zZShmZCkKCmlmIF9fbmFtZV9fPT0nX19tYWluX18nOm1haW4oc3lzLmFyZ3ZbMV0pCg==''); assert hashlib.sha256(b).hexdigest()==''2918d3ccba90c56ec6a33cda80cb3f62818eaf09d8ff6a6288a11645d6001e20''; sys.argv=[''network_guard'',''86e4938b-0f65-4166-9237-c547b67e1451'']; exec(compile(b,''step08_network_guard'',''exec''))"'}
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
