param([string]$Port = 'COM5',[switch]$WakePrompt)
$ErrorActionPreference = 'Stop'
$expected = 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$device = @(Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -eq $expected -and $_.FriendlyName -eq ('USB Serial Port (' + $Port + ')') })
if ($device.Count -ne 1 -or $device[0].Status -ne 'OK') { throw 'Exact user-connected FTDI UART channel B differs' }
$serial = [System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 500
$serial.WriteTimeout = 2000
$text = [System.Text.StringBuilder]::new()
try {
    $serial.Open()
    $watch = [Diagnostics.Stopwatch]::StartNew()
    while ($watch.Elapsed.TotalSeconds -lt 5) {
        [void]$text.Append($serial.ReadExisting())
        if ($text.Length -gt 262144) { throw 'Console observation byte budget exceeded' }
        Start-Sleep -Milliseconds 100
    }
    if ($WakePrompt -and $text.Length -eq 0) {
        $serial.Write("`r")
        $watch.Restart()
        while ($watch.Elapsed.TotalSeconds -lt 5) {
            [void]$text.Append($serial.ReadExisting())
            if ($text.Length -gt 262144) { throw 'Console observation byte budget exceeded' }
            Start-Sleep -Milliseconds 100
        }
    }
    [pscustomobject]@{
        Scope = $(if ($WakePrompt) { 'UART_PROMPT_SINGLE_CR_NO_RESET_NO_LOGIN' } else { 'PASSIVE_UART_READ_ONLY_NO_INPUT_NO_RESET_NO_LOGIN' })
        Port = $Port
        Device = $expected
        Settings = '115200 8N1 no-flow DTR=false RTS=false'
        ReceivedText = $text.ToString()
        TransmittedBytes = $(if ($WakePrompt) { 1 } else { 0 })
    } | ConvertTo-Json -Depth 3
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
}
