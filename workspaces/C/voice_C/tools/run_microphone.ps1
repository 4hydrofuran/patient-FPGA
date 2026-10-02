param(
    [ValidateRange(1, 60)][int]$Seconds = 10,
    [ValidateRange(0, 30)][int]$Countdown = 5,
    [ValidateRange(0, 255)][int]$Device = 0,
    [switch]$ListDevices
)

$voiceRoot = Split-Path -Parent $PSScriptRoot
$micPython = Join-Path $voiceRoot '.venv_mic/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $micPython)) {
    $micPython = Join-Path $voiceRoot '.venv/Scripts/python.exe'
}
if (-not (Test-Path -LiteralPath $micPython)) {
    throw 'Local voice Python runtime is missing. See MICROPHONE_README.md.'
}
$env:PYTHONUTF8 = '1'
$env:PYTHONDONTWRITEBYTECODE = '1'
$micEntry = Join-Path $voiceRoot 'tools/stream_c03_microphone.py'
if ($ListDevices) {
    & $micPython $micEntry --list-devices
    if ($LASTEXITCODE -ne 0) { throw 'Microphone enumeration failed.' }
    return
}
$runName = 'manual_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + ([guid]::NewGuid().ToString('N').Substring(0, 8))
$runOutput = Join-Path $voiceRoot ('evidence/c03_mic/' + $runName)
Write-Host 'Local microphone test: speak after RECORDING appears; raw audio is deleted.'
Write-Host ('Local transcript and trace: ' + $runOutput)
& $micPython $micEntry --record --device $Device --seconds $Seconds --countdown $Countdown --output $runOutput
if ($LASTEXITCODE -ne 0) { throw ('Microphone test failed. Inspect local report: ' + $runOutput) }
