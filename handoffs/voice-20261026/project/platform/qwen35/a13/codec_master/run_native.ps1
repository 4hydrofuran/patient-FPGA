param([Parameter(Mandatory=$true)][string]$WorkDir, [ValidateSet('sim','build','postcheck')][string]$Mode)
$ErrorActionPreference = 'Stop'
$a13MasterWork = (Resolve-Path -LiteralPath $WorkDir).Path.Replace('\','/')
if ($a13MasterWork -notmatch '^C:/Patientqwen/local/a13c_[sbp][0-9][0-9]$') { throw 'Unexpected work path' }
Set-Location -LiteralPath $a13MasterWork
if (Test-Path -LiteralPath './native.log') { throw 'Attempt already used' }
$a13HostHandle = [System.IO.File]::Open((Join-Path $a13MasterWork 'WINDOWS_HOST.json'), [System.IO.FileMode]::CreateNew)
try {
    $a13HostWriter = [System.IO.StreamWriter]::new($a13HostHandle)
    $a13HostWriter.WriteLine((@{pid=$PID; started_utc=[DateTime]::UtcNow.ToString('o'); scope='OFFLINE_ONLY'; mode=$Mode} | ConvertTo-Json))
    $a13HostWriter.Flush()
} finally { $a13HostHandle.Dispose() }
& 'D:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat' -mode batch -nojournal -notrace -source "./inputs/$Mode.tcl" -log './native.log'
exit $LASTEXITCODE
