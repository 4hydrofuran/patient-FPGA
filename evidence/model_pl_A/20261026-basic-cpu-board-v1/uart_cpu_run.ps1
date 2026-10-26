$ErrorActionPreference='Stop'
$folder=$PSScriptRoot
$pin=(Get-FileHash -LiteralPath (Join-Path $folder 'basic_cpu_run_bound.py') -Algorithm SHA256).Hash.ToLowerInvariant()
$bootstrap="import urllib.request,hashlib; b=urllib.request.urlopen('http://192.168.2.1:8765/basic_cpu_run.py',timeout=15).read(32768); assert hashlib.sha256(b).hexdigest()=='$pin'; exec(compile(b,'reviewed_basic_cpu_run','exec'))"
$command='sudo -p __A12_ROOT_AUTH__: /usr/bin/python3 -B -I -c "'+$bootstrap+'"'
$port=$null;$secret=$null;$report=[ordered]@{scope='EXPLICIT_BOARD_CPU_BASIC_RUN';source_sha256=$pin;started_utc=[DateTime]::UtcNow.ToString('o');credentials_logged=$false;output='';error=$null}
try{
    $port=[IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
    $port.DtrEnable=$false;$port.RtsEnable=$false;$port.Handshake=[IO.Ports.Handshake]::None;$port.WriteTimeout=3000
    $port.Open();$port.Write("`r");Start-Sleep -Milliseconds 200
    if($port.ReadExisting() -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Authenticated UART shell absent'}
    $port.Write($command+"`r");$buffer=[Text.StringBuilder]::new();$watch=[Diagnostics.Stopwatch]::StartNew()
    $authenticated=$false;$workerSeen=$false;$readySeen=$false
    while($watch.Elapsed.TotalSeconds -lt 400){
        [void]$buffer.Append($port.ReadExisting());$text=$buffer.ToString()
        if($text.Length -gt 262144){throw 'Unexpected CPU run response size'}
        if(-not $authenticated -and $text -match '__A12_ROOT_AUTH__:\s*$'){
            $info=[Diagnostics.ProcessStartInfo]::new();$info.FileName='C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
            $info.Arguments='KV260 CPU basic run sudo (hidden input)';$info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
            $child=[Diagnostics.Process]::Start($info);$secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
            if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret)){throw 'Authentication cancelled'}
            $port.Write($secret+"`r");$secret=$null;$authenticated=$true
        }
        if(-not $workerSeen -and $text -match 'CPU_WORKER_STARTED'){$workerSeen=$true;Write-Host 'Board CPU worker started'}
        if(-not $readySeen -and $text -match 'CPU_MODEL_READY'){$readySeen=$true;Write-Host 'Board CPU model ready; one synthetic question running'}
        if($text -match '(?m)^__A12_UPLOAD_END__\s*$'){break}
        if($text -match '(?m)^Traceback \(most recent call last\):' -and $text -match 'ubuntu@kria:[^\r\n]*\$\s*$'){throw 'CPU runner failed before completion'}
        Start-Sleep -Milliseconds 100
    }
    $report.output=$buffer.ToString()
    if($report.output -notmatch '(?m)^__A12_UPLOAD_END__\s*$'){throw 'CPU result not confirmed; no automatic replay'}
    Write-Output $report.output
}catch{$report.error=$_.Exception.Message;Write-Host $report.error}
finally{
    $secret=$null
    if($port){if($port.IsOpen){$port.Close()};$port.Dispose()}
    $report.completed_utc=[DateTime]::UtcNow.ToString('o')
    $report|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $folder 'cpu-run-uart.json') -Encoding utf8 -NoNewline
}
if($report.error){exit 1}
