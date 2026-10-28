# Manual user login bridge only. No automatic commands, password storage or logging.
# Ctrl+] or Ctrl+C closes the PC terminal WITHOUT sending a control byte to the board.
$ErrorActionPreference = 'Stop'
$expected = 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$device = Get-PnpDevice -Class Ports -PresentOnly | Where-Object { $_.InstanceId -eq $expected -and $_.FriendlyName -match '\(COM5\)$' }
if (@($device).Count -ne 1) { throw 'COM5 device identity changed. Stop and recheck.' }
$port = [IO.Ports.SerialPort]::new('COM5',115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$port.Handshake = [IO.Ports.Handshake]::None
$port.DtrEnable = $false
$port.RtsEnable = $false
$port.ReadTimeout = 200
$port.WriteTimeout = 500
$oldControl = [Console]::TreatControlCAsInput
try {
    [Console]::TreatControlCAsInput = $true
    $port.Open()
    Write-Host 'KV260 COM5 manual terminal. No recording. DTR/RTS false.'
    Write-Host 'Press Enter to display login. Enter ubuntu and YOUR password yourself.'
    Write-Host 'After a shell prompt appears, press Ctrl+] to close this PC terminal.'
    Write-Host 'Do NOT type reboot, reset, shutdown, update or test commands.'
    Write-Host 'This terminal closes after five minutes; it does not power off the board.'
    $timer = [Diagnostics.Stopwatch]::StartNew()
    while ($timer.Elapsed.TotalSeconds -lt 300) {
        if ($port.BytesToRead -gt 0) { [Console]::Write($port.ReadExisting()) }
        if ([Console]::KeyAvailable) {
            $key = [Console]::ReadKey($true)
            if ([int]$key.KeyChar -in @(3,29)) { break }
            if ($key.Key -eq [ConsoleKey]::Enter) { $port.Write([string][char]13) }
            elseif ($key.Key -eq [ConsoleKey]::Backspace) { $port.Write([string][char]127) }
            elseif ([int]$key.KeyChar -ge 32) { $port.Write([string]$key.KeyChar) }
        }
        Start-Sleep -Milliseconds 50
    }
} finally {
    if ($port.IsOpen) { $port.Close() }
    $port.Dispose()
    [Console]::TreatControlCAsInput = $oldControl
}
