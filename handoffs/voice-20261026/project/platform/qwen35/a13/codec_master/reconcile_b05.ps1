$ErrorActionPreference = 'Stop'
$a13B05 = 'C:/Patientqwen/local/a13c_b05'
$a13Completion = Get-Content -Raw -LiteralPath "$a13B05/NATIVE_COMPLETION.json" | ConvertFrom-Json
if ($a13Completion.exit_code -ne 1) { throw 'Expected retained b05 postprocess failure' }
foreach ($a13Run in (Get-ChildItem -LiteralPath "$a13B05/project/codec_master.runs" -Directory)) {
    $a13Begin = Join-Path $a13Run.FullName '.vivado.begin.rst'
    if (!(Test-Path -LiteralPath $a13Begin)) { continue }
    if (!(Test-Path -LiteralPath (Join-Path $a13Run.FullName '.vivado.end.rst')) -and !(Test-Path -LiteralPath (Join-Path $a13Run.FullName '.vivado.error.rst'))) { throw "Own run unfinished: $($a13Run.Name)" }
    [xml]$a13ProcessRecord = Get-Content -Raw -LiteralPath $a13Begin
    $a13RecordedPid = [int]$a13ProcessRecord.ProcessHandle.Process.Pid
    if (Get-Process -Id $a13RecordedPid -ErrorAction SilentlyContinue) { throw "Own wrapper still present: $a13RecordedPid" }
    Write-Output "QUIESCENT $($a13Run.Name) PID=$a13RecordedPid"
}
if (Get-Process -Id 7212,78412 -ErrorAction SilentlyContinue) { throw 'Own b05 native parent still present' }
& wsl -d KV260-A-2204 -- python3 -B /mnt/c/Patientqwen/platform/qwen35/a13/codec_master/reconcile_b05.py
exit $LASTEXITCODE
