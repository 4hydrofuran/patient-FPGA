$ErrorActionPreference='Stop'
$boot='bf3796f0-9785-4afd-a617-3ad578a24d10'
. "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly -Candidate irq2 -ExpectedBootId $boot
$checks=0
function Assert([bool]$ok,[string]$why){if(-not $ok){throw $why};$script:checks++}
$root=Join-Path $PSScriptRoot '../../..'
$manifest=Get-Content "$root/evidence/board_platform/A10_20261018_intake/irq2_pc_package_20261021_v1/manifest.json" -Raw | ConvertFrom-Json
Assert ($candidateBytes -eq $manifest.artifacts.'candidate.fit'.bytes) 'Exact new FIT length'
Assert ($preflight.Contains($manifest.artifacts.'candidate.fit'.sha256)) 'Exact FIT pin'
Assert ($componentPins[0] -eq $manifest.artifacts.'Image.gz'.sha256) 'Compressed kernel pin'
Assert ($componentPins[1] -eq $manifest.artifacts.'initramfs.cpio.gz'.sha256) 'Initramfs pin'
Assert ($componentPins[2] -eq $manifest.artifacts.'kv260-revB.dtb'.sha256) 'DT pin'
Assert ($preflight.Contains($boot)) 'Fresh boot guard'
Assert ($preflight.Contains('test ! -e /var/lock/kv260-a1/active')) 'Active lease blocks reboot'
Assert ($preflight.Contains('55000')) 'Thermal guard retained'
Assert ($preflight -notmatch 'irq1|a10-candidate-20261020|a10-kernel-trial-20261020') 'No old candidate in plan'
Assert ($preflight.Contains('/home/ubuntu/a10-irq2-stage-20261021-v1/stage-result.jsonl')) 'New stage receipt'
Assert ($loadCommand -eq 'fatload mmc 1:1 0x10000000 a10-candidate-irq2-20261021.fit') 'Exact new load path'
$fixture=($componentPins -join "`n")+"`nconf-smk-k26-revA-sck-kv-g-revB`n## Checking hash(es) for FIT Image at 10000000`nHash(es) for Image 0 (kernel): sha256+`nHash(es) for Image 1 (ramdisk): sha256+`nHash(es) for Image 2 (fdt): sha256+`nZynqMP>"
Assert (Test-CandidateInfo $fixture) 'Synthetic old-U-Boot format accepts new pins'
Assert (-not(Test-CandidateInfo $fixture.Replace($componentPins[1],'wrong'))) 'Changed ramdisk rejected'
Assert (-not(Test-CandidateInfo $fixture.Replace('sha256+','sha256-'))) 'Failed verification rejected'
$old=Get-Content "$root/evidence/board_platform/A10_20261018_intake/candidate_boot_once_01.json" -Raw | ConvertFrom-Json
Assert (-not(Test-CandidateInfo (($old.events|Where-Object kind -eq 'candidate_integrity_result').text))) 'Old real transcript cannot verify irq2'
$missingBootRejected=$false
try { & "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly -Candidate irq2 } catch {$missingBootRejected=$true}
Assert $missingBootRejected 'No inherited historical boot ID for irq2'
$oldLiveRejected=$false
try { & "$PSScriptRoot/boot_candidate_once.ps1" -Candidate irq1 -AuthorizedOnce -OutputPath 'NEVER_CREATED.json' } catch {$oldLiveRejected=$_.Exception.Message -match 'irq1 REJECTED'}
Assert $oldLiveRejected 'Rejected candidate cannot reach COM5'
$noAuthorityRejected=$false
try { & "$PSScriptRoot/boot_candidate_once.ps1" -Candidate irq2 -ExpectedBootId $boot } catch {$noAuthorityRejected=$_.Exception.Message -match 'Explicit one-reboot authority'}
Assert $noAuthorityRejected 'irq2 cannot contact board without explicit execution switch'
Write-Output "PASS $checks PC checks; no board contact, synthetic fixture is not boot evidence"
