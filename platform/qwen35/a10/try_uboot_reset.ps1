# User-authorized single software reset, conditional on a fresh known prompt.
# No firmware/media write, boot environment change, Linux login or power change.
$ErrorActionPreference = 'Stop'
function Emit($data) {
    $data.utc = [DateTime]::UtcNow.ToString('o')
    [Console]::WriteLine(($data | ConvertTo-Json -Compress))
}
function ReceiveWindow([int]$milliseconds) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $bytes = [Collections.Generic.List[byte]]::new()
    $buffer = [byte[]]::new(4096)
    while ($timer.ElapsedMilliseconds -lt $milliseconds) {
        $count = [Math]::Min($port.BytesToRead, $buffer.Length)
        if ($count -gt 0) {
            $count = $port.Read($buffer, 0, $count)
            for ($i=0; $i -lt $count; $i++) { $bytes.Add($buffer[$i]) }
            if ($bytes.Count -gt 65536) { throw 'Receive limit exceeded; stop without further commands.' }
        }
        Start-Sleep -Milliseconds 50
    }
    $raw = $bytes.ToArray()
    $text = [Text.Encoding]::ASCII.GetString($raw)
    Emit @{event='rx';bytes=$raw.Length;base64=[Convert]::ToBase64String($raw);text=$text}
    return $text
}
$port = [IO.Ports.SerialPort]::new('COM4',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake = [IO.Ports.Handshake]::None
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.ReadTimeout = 200
$port.WriteTimeout = 500
$sentReset = $false
$exitCode = 2
try {
    $port.Open()
    Emit @{event='open';port='COM4';dtr=$false;rts=$false}
    # Record pending output separately: it must not authorize reset.
    $prior = ReceiveWindow 1000
    Emit @{event='tx';purpose='request_fresh_prompt';base64='DQ=='}
    $port.Write("`r")
    $fresh = ReceiveWindow 3000
    if ($fresh -match '(?m)(?:^|[\r\n])ZynqMP>\s*\z') {
        Emit @{event='tx';purpose='user_authorized_uboot_reset';text="reset`r"}
        $port.Write("reset`r")
        $sentReset = $true
        $after = ReceiveWindow 12000
        $exitCode = 0
        Emit @{event='result';status='RESET_SENT_BOOT_NOT_VERIFIED';reset_sent=$true;new_fsbl_banner=($after -match 'Zynq MP First Stage Boot Loader')}
    } else {
        Emit @{event='result';status='NO_FRESH_UBOOT_PROMPT_RESET_NOT_SENT';reset_sent=$false}
    }
} catch {
    $exitCode = 1
    Emit @{event='error';message=$_.Exception.Message;reset_sent=$sentReset}
} finally {
    if ($port.IsOpen) { $port.Close() }
    $port.Dispose()
    Emit @{event='closed';reset_sent=$sentReset}
}
exit $exitCode
