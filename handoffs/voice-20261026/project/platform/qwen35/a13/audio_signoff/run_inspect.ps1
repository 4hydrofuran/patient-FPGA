param([Parameter(Mandatory=$true)][string]$WorkDir)
$ErrorActionPreference = 'Stop'
$a13Inspect = (Resolve-Path -LiteralPath $WorkDir).Path.Replace('\','/')
if ($a13Inspect -cnotmatch '^C:/Patientqwen/local/a13s_s0[12]$') { throw 'Unexpected workdir' }
Set-Location -LiteralPath $a13Inspect
if (Test-Path -LiteralPath './native.log') { throw 'Attempt already exists' }
& 'D:/AMDDesignTools/2026.1/Vivado/bin/vivado.bat' -mode batch -nojournal -notrace -source './inspect_routed.tcl' -log './native.log'
exit $LASTEXITCODE
