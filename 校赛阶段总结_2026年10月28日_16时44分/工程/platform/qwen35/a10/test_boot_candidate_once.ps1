$ErrorActionPreference='Stop'
. "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly
$checks=0
function Assert([bool]$ok,[string]$why){if(-not $ok){throw $why};$script:checks++}
Assert ($expectedBoot -eq 'eb429b2f-66aa-4959-8610-bfcfabcf0202') 'Exact boot'
Assert ($preflight.Contains('55000')) 'Thermal gate'
Assert ($preflight.Contains('STAGED_ONLY_NOT_BOOTED')) 'Stage completion gate'
Assert ($preflight.Contains('b007246e409140c73485a057a0e7ccc1fac7116c14699837e4066e74be7532a9')) 'Original FIT gate'
Assert ($preflight.Contains('a393f397a673a2f3636c8b9f85d8a59f7257c24d33c34d28a67b11c410a11b81')) 'Candidate FIT gate'
Assert ($loadCommand -eq 'fatload mmc 1:1 0x10000000 a10-candidate-20261020.fit') 'Exact load'
Assert ($bootCommand -eq 'bootm 0x10000000#conf-smk-k26-revA-sck-kv-g-revB') 'Exact configuration'
Assert ($bootargsCommand.Substring('setenv bootargs '.Length).Trim("'").StartsWith('root=LABEL=writable rootwait ')) 'Bootargs extraction'
$fixture=@'
Hash value: 1bbdfbe4b8ee040ca9131eab9c28d7d79ca8723efab66182932442d1f2e939d0
Hash value: 82e851dd2c3e294133311e6aadb368445c3bd7cddffbfecdceee51d93e7a9d7c
Hash value: 32dc08a08a87aba2ab0ca68bc5292c735943c20ecd0dc7472690bd152fb7c7a3
Configuration: conf-smk-k26-revA-sck-kv-g-revB
Verifying Hash Integrity ... sha256+ sha256+ sha256+ OK
ZynqMP>
'@
Assert (Test-CandidateInfo $fixture) 'Valid synthetic integrity transcript'
Assert (-not (Test-CandidateInfo $fixture.Replace('sha256+','sha1+'))) 'Wrong algorithm'
Assert (-not (Test-CandidateInfo $fixture.Replace('1bbdfbe4','00000000'))) 'Wrong kernel hash'
Assert (-not (Test-CandidateInfo $fixture.Replace('sha256+ sha256+ sha256+','sha256+'))) 'All images required'
Assert (-not (Test-CandidateInfo ($fixture+"`nBad hash"))) 'Bad hash'
Assert (-not (Test-CandidateInfo $fixture.Replace('ZynqMP>',''))) 'Fresh prompt required'
$actual=Get-Content -Raw "$PSScriptRoot/../../../evidence/board_platform/A10_20261018_intake/candidate_boot_once_01.json"|ConvertFrom-Json
$iminfo=($actual.events|Where-Object {$_.kind -eq 'candidate_integrity_result'}).text
Assert (Test-CandidateInfo $iminfo) 'Real U-Boot 2020.01 iminfo format'
Assert (-not(Test-CandidateInfo $iminfo.Replace('Hash(es) for Image 1 (ramdisk): sha256+','Hash(es) for Image 1 (ramdisk): sha256-'))) 'Real-format RAM disk failure'
$src=Get-Content "$PSScriptRoot/boot_candidate_once.ps1" -Raw
Assert ([regex]::Matches($src,'systemctl reboot').Count -eq 1) 'One software reboot'
Assert (-not ($src -match '\bsaveenv\b|\bfw_setenv\b|\binsmod\b|\brmmod\b|\bflashcp\b')) 'No persistent boot writes or module load'
Assert ($src.Contains('[IO.FileMode]::CreateNew')) 'Exclusive receipt'
Assert ($src.Contains('$serial.DtrEnable=$false; $serial.RtsEnable=$false')) 'Modem signals off'
Assert (Test-AuthPrompt '__A10_SUDO_AUTH__:') 'Auth challenge recognized'
Assert (-not (Test-AuthPrompt "sudo -p '__A10_SUDO_AUTH__:' -v")) 'Echo not challenge'
$errors=$null;$tokens=$null
[void][System.Management.Automation.Language.Parser]::ParseFile("$PSScriptRoot/uart_sudo_prepare_network.ps1",[ref]$tokens,[ref]$errors)
Assert ($errors.Count -eq 0) 'Stage helper syntax'
Assert ($preflight.Contains('test ! -e /var/lock/kv260-a1/active')) 'No active board lease'
Assert ($preflight.Contains('2aa089c3967e8fa72480310fe2cc12aaa7d920135f5322d8596819835ca087cc')) 'Candidate module hash pinned'
. "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly -ExpectedBootId '12345678-1234-4234-8234-123456789abc'
Assert ($expectedBoot -eq '12345678-1234-4234-8234-123456789abc') 'Explicit fixture boot honored'
Assert ($preflight.Contains('test "$(cat /proc/sys/kernel/random/boot_id)" = 12345678-1234-4234-8234-123456789abc')) 'Fresh boot passed to guard'
foreach($bad in @('bad; reboot','00000000-0000-0000-0000-000000000000','$(reboot)')){
    $rejected=$false
    try { & "$PSScriptRoot/boot_candidate_once.ps1" -DefinitionsOnly -ExpectedBootId $bad }
    catch { $rejected=$true }
    Assert $rejected 'Invalid boot rejected before board contact'
}
Write-Output "PASS $checks PC safety checks; synthetic fixtures, no board contact"
