param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$')][string]$BoardHost,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-z_][a-z0-9_-]{0,31}$')][string]$BoardUser,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$')][string]$BoardLabel,
    [switch]$Cpu
)
$ErrorActionPreference = 'Stop'
# No password/key storage, network discovery, automatic reboot or XRT invocation.
Get-Command ssh, scp -ErrorAction Stop | Out-Null
if ((Read-Host 'Actual KV260 checked, power/cooling normal, no other board tests? Type YES') -cne 'YES') {
    throw 'Not confirmed; no connection made.'
}
$manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SHA256.json') -Raw | ConvertFrom-Json
foreach ($name in @('quick_check.py', 'cpu_smoke_a53')) {
    $digest = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $PSScriptRoot $name)).Hash.ToLowerInvariant()
    if ($digest -ne $manifest.$name) { throw "Local hash mismatch: $name" }
}
$tag = 'kv260-check-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [guid]::NewGuid().ToString('N').Substring(0,8)
$target = $BoardUser + '@' + $BoardHost
$localReport = Join-Path $PSScriptRoot ('results-' + $tag)
# Ask on first SSH host key; verify against the technician's fingerprint. Never bypass host-key checks.
$sshOptions = @('-o','ConnectTimeout=8','-o','ServerAliveInterval=5','-o','ServerAliveCountMax=2','-o','StrictHostKeyChecking=ask')
& ssh @sshOptions $target "mkdir -m 700 -- $tag"
if ($LASTEXITCODE -ne 0) { throw 'Connection/directory creation failed. Do not retry in a loop.' }
$files = @('quick_check.py','cpu_smoke_a53','SHA256.json') | ForEach-Object { Join-Path $PSScriptRoot $_ }
& scp @sshOptions @files "${target}:$tag/"
if ($LASTEXITCODE -ne 0) { throw 'Upload failed.' }
$cpuOption = if ($Cpu) { ' --cpu' } else { '' }
& ssh @sshOptions $target "python3 $tag/quick_check.py --output $tag/report --board-label $BoardLabel --confirm-kv260$cpuOption"
$checkExit = $LASTEXITCODE
# Retrieve failed checks too. Never call reset/reboot, never launch another test automatically.
& scp @sshOptions -r "${target}:$tag/report" $localReport
$copyExit = $LASTEXITCODE
Write-Host "Check exit=$checkExit; report copy exit=$copyExit; local reports=$localReport"
Write-Host 'FPGA and full model/voice remain NOT_TESTED. Send report.json and logs for review.'
if ($checkExit -ne 0 -or $copyExit -ne 0) { exit 2 }
