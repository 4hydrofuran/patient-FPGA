param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
# PC-only evidence audit; never contacts the board. Hashtable preserves Linux case.
$root = 'C:/Patientqwen'
$ev = "$root/evidence/board_platform/A10_20261018_intake"
$source = "$root/platform/local/a10-irq2-transfer-20261021-v1/board-result"
if (Test-Path -LiteralPath $OutputPath) { throw 'Refusing to overwrite evidence' }
$pins = @{
    'stage-result.jsonl'='f36284453651d1f951f9951d7702c42b73b0b7eb556754fab0e783e498048d32'
    'staged-module-hashes.json'='d8a2457e01a720830351d1340f0a276a1262f03750b609a7273924d9c676dd5e'
}
foreach ($name in $pins.Keys) {
    if ((Get-FileHash -LiteralPath "$source/$name" -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pins[$name]) { throw "Evidence hash mismatch: $name" }
}
$rows = @(Get-Content -LiteralPath "$source/stage-result.jsonl" | ForEach-Object { ConvertFrom-Json -AsHashtable $_ })
$actual = Get-Content -LiteralPath "$source/staged-module-hashes.json" -Raw | ConvertFrom-Json -AsHashtable
$expected = Get-Content -LiteralPath "$ev/irq2_pc_package_20261021_v1/module-stage-audit-v2.json" -Raw | ConvertFrom-Json -AsHashtable
if ($actual.files -ne 6231 -or $actual.modules -ne 6218 -or $actual.bytes -ne 390087697) { throw 'Counts differ' }
if ($actual.readback_sha256.Count -ne 6231 -or $expected.files.Count -ne 6218) { throw 'Manifest incomplete' }
foreach ($file in $expected.files) {
    if ($actual.readback_sha256[$file.path] -cne $file.sha256) { throw "Module bytes differ: $($file.path)" }
}
if ($rows[-1].event -ne 'STAGED_ONLY_NOT_BOOTED' -or !$rows[-1].original_boot_unchanged) { throw 'Stage incomplete' }
if (@($rows | Where-Object { $_.event -like 'FAILED*' }).Count) { throw 'Failure retained; stage not accepted' }
$health = @($rows | Where-Object { $_.event -eq 'HEALTH' })
$temp = ($health.temperatures_mC | Measure-Object -Maximum).Maximum
$mem = ($health.MemAvailable_KiB | Measure-Object -Minimum).Minimum
if (!$health.Count -or $temp -ge 55000 -or $mem -le 1048576) { throw 'Health guard not met' }
$post = Get-Content -LiteralPath "$ev/irq2_poststage_readonly_20261021_01.json" -Raw | ConvertFrom-Json -AsHashtable
if (!$post.closed -or $post.status -ne 'COLLECTED_REVIEW_REQUIRED') { throw 'Poststage readback incomplete' }
foreach ($record in $post.records) { if (!$record.completion_marker -or $record.exit_code -ne 0) { throw 'Readback command failed' } }
if ($post.records[0].raw -notmatch 'bf3796f0-9785-4afd-a617-3ad578a24d10' -or $post.records[0].raw -notmatch '6\.8\.0-1015-xilinx') { throw 'Boot changed' }
if ($post.records[2].raw -notmatch 'k26-starter-kits_image_1') { throw 'Default configuration absent' }
$result = [ordered]@{
    status='PASS_ADDITIVE_STAGE_ONLY_NOT_BOOT_ACCEPTANCE'; board_contact=$false
    module_hashes_compared=$expected.files.Count; staged_files=$actual.files
    staged_bytes=$actual.bytes; health_samples=$health.Count
    max_temperature_mC=$temp; min_MemAvailable_KiB=$mem
    logged_stage_elapsed_s=($rows[-1].monotonic_s-$rows[0].monotonic_s)
    original_boot_unchanged=$true; current_kernel='6.8.0-1015-xilinx'
    receipt_sha256=$pins; board_boot_tested=$false; board_compute_tested=$false
    A10='NOT_PASSED'; numerical_regression='CANCELLED_BY_USER'
}
$result | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $OutputPath -Encoding utf8
$result | ConvertTo-Json -Depth 6
