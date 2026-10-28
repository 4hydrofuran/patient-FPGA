param(
    [string[]]$Ports = @('COM4', 'COM3'),
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateRange(1,3600)][int]$DurationSeconds = 1800,
    [ValidateRange(1024,16777216)][int]$MaxBytesPerPort = 8388608
)
# Passive UART capture only: no Write(), boot commands, reset, DTR or RTS assertion.
# Both raw bytes and receive timestamps are retained; host receive time is not
# firmware execution time. Empty capture is NOT_TESTED, never boot PASS.
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Use a new evidence directory; no overwrite.' }
if (($Ports | Select-Object -Unique).Count -ne $Ports.Count) { throw 'Duplicate port.' }
foreach ($name in $Ports) { if ($name -notmatch '^COM[0-9]+$') { throw 'Explicit Windows COM ports required.' } }
[void][IO.Directory]::CreateDirectory($OutputDirectory)
$sessions = @()
$watch = [Diagnostics.Stopwatch]::StartNew()
$events = [IO.StreamWriter]::new((Join-Path $OutputDirectory 'events.jsonl'), $false, [Text.UTF8Encoding]::new($false))
$events.AutoFlush = $true
$result = 'CAPTURE_COMPLETED_NOT_BOOT_VERIFIED'
$failed = $false
try {
    $events.WriteLine((@{event='start';utc=[DateTime]::UtcNow.ToString('o');ports=$Ports;baud=115200;data_bits=8;parity='None';stop_bits=1;flow_control='None';dtr=$false;rts=$false;tx_enabled=$false;duration_seconds=$DurationSeconds;max_bytes_per_port=$MaxBytesPerPort} | ConvertTo-Json -Compress))
    foreach ($name in $Ports) {
        $port = [IO.Ports.SerialPort]::new($name, 115200, [IO.Ports.Parity]::None, 8, [IO.Ports.StopBits]::One)
        $port.Handshake = [IO.Ports.Handshake]::None
        $port.DtrEnable = $false
        $port.RtsEnable = $false
        $port.ReadTimeout = 200
        $raw = [IO.File]::Open((Join-Path $OutputDirectory ($name + '.bin')), [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::Read)
        $entry = @{name=$name;port=$port;raw=$raw;bytes=0}
        $sessions += $entry
        $port.Open()
        $events.WriteLine((@{event='port_open';port=$name;utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Compress))
        Write-Output "READY $name receive-only 115200 8N1; DTR/RTS false"
    }
    $buffer = [byte[]]::new(4096)
    while ($watch.Elapsed.TotalSeconds -lt $DurationSeconds) {
        foreach ($entry in $sessions) {
            $available = $entry.port.BytesToRead
            if ($available -gt 0) {
                $remaining = $MaxBytesPerPort - $entry.bytes
                if ($remaining -le 0) { throw "Capture limit reached on $($entry.name); no board reset performed." }
                $count = [Math]::Min([Math]::Min($available, $buffer.Length), $remaining)
                $count = $entry.port.Read($buffer, 0, $count)
                $offset = $entry.bytes
                $entry.raw.Write($buffer, 0, $count)
                $entry.raw.Flush()
                $entry.bytes += $count
                $events.WriteLine((@{event='rx';port=$entry.name;offset=$offset;count=$count;utc=[DateTime]::UtcNow.ToString('o');host_elapsed_ms=$watch.Elapsed.TotalMilliseconds;text=[Text.Encoding]::UTF8.GetString($buffer,0,$count)} | ConvertTo-Json -Compress))
            }
        }
        Start-Sleep -Milliseconds 50
    }
} catch {
    $failed = $true
    $result = 'CAPTURE_ERROR'
    $events.WriteLine((@{event='error';utc=[DateTime]::UtcNow.ToString('o');error=$_.Exception.Message} | ConvertTo-Json -Compress))
    Write-Output ('ERROR ' + $_.Exception.Message)
} finally {
    foreach ($entry in $sessions) {
        if ($entry.port.IsOpen) { $entry.port.Close() }
        $entry.port.Dispose()
        $entry.raw.Dispose()
        $rawPath = Join-Path $OutputDirectory ($entry.name + '.bin')
        # Windows PowerShell child processes may not expose Get-FileHash.
        # Use the framework directly so finalization does not depend on autoload.
        $hasher = [Security.Cryptography.SHA256]::Create()
        $inputStream = [IO.File]::OpenRead($rawPath)
        try { $digest = [BitConverter]::ToString($hasher.ComputeHash($inputStream)).Replace('-', '').ToLowerInvariant() }
        finally { $inputStream.Dispose(); $hasher.Dispose() }
        $events.WriteLine((@{event='port_close';port=$entry.name;bytes=$entry.bytes;sha256=$digest} | ConvertTo-Json -Compress))
    }
    $events.WriteLine((@{event='end';utc=[DateTime]::UtcNow.ToString('o');status=$result;elapsed_seconds=$watch.Elapsed.TotalSeconds;boot_verified=$false} | ConvertTo-Json -Compress))
    $events.Dispose()
}
if ($failed) { exit 1 }
exit 0
