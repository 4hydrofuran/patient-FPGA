$ErrorActionPreference='Stop'
. "$PSScriptRoot/cold_boot_irq2_once.ps1" -DefinitionsOnly
$checks=0
function Check([bool]$ok,[string]$message){if(-not $ok){throw $message};$script:checks++}
Check (Test-ColdCountdown "U-Boot 2020.01 (old board)`nHit any key to stop autoboot:  1") 'Fresh countdown missed'
Check (-not(Test-ColdCountdown "Hit any key to stop autoboot:  1")) 'Unidentified boot accepted'
Check (-not(Test-ColdCountdown "U-Boot 2020.01`nHit any key to stop autoboot:  0")) 'Zero countdown accepted'
Check (-not(Test-ColdCountdown "U-Boot 2020.01`nLinux version`nHit any key to stop autoboot:  1")) 'Linux output accepted'
$good="## Checking hash(es) for FIT Image at 10000000`n"+($componentPins -join "`n")+"`nconf-smk-k26-revA-sck-kv-g-revB`nHash(es) for Image 0 (kernel): sha256+`nHash(es) for Image 1 (ramdisk): sha256+`nHash(es) for Image 2 (fdt): sha256+`nZynqMP> "
Check (Test-ColdInfo $good) 'Valid fixture rejected'
Check (-not(Test-ColdInfo $good.Replace($componentPins[0],'wrong'))) 'Bad digest accepted'
Check (-not(Test-ColdInfo ($good+"`nBAD HASH"))) 'Error accepted'
Check (Test-ColdLogin "[1.2] mtdoops: mtd device (mtddev=name/number) must be supplied`r`nkria login: ") 'mtdoops driver name is not an Oops'
foreach($fault in @('Oops: 0000','Internal error: Oops: 96000004','BUG: bad page state','Kernel panic - not syncing')){
    Check (-not(Test-ColdLogin ($fault+"`nkria login: "))) 'Actual fault accepted'
}
$captured=Join-Path $PSScriptRoot '../../../evidence/board_platform/A10_20261023_isolated_idle_v1/cold_boot_irq2_01.json'
if(Test-Path -LiteralPath $captured){
    $raw=(Get-Content -Raw -LiteralPath $captured|ConvertFrom-Json).events|Where-Object kind -eq 'candidate_boot_log'
    Check (Test-ColdLogin $raw.text) 'Actual login transcript rejected'
}
$p=& "$PSScriptRoot/cold_boot_irq2_once.ps1" -ValidateOnly|ConvertFrom-Json
Check (-not $p.board_contact -and $p.reboot_commands -eq 0 -and -not $p.default_boot_changed) 'Unsafe default plan'
Check ($p.bytes -eq 65555004 -and $p.load -eq 'fatload mmc 1:1 0x10000000 a10-candidate-irq2-20261021.fit') 'Wrong pinned candidate'
Check ($p.boot -eq 'bootm 0x10000000#conf-smk-k26-revA-sck-kv-g-revB') 'Wrong board configuration'
$text=Get-Content -Raw "$PSScriptRoot/cold_boot_irq2_once.ps1"
Check ($text -notmatch 'saveenv|systemctl reboot|sf write|sf erase|mmc write') 'Persistent/flash action present'
[ordered]@{status='PASS_PC_COLD_BOOT_PLAN_NOT_BOARD';checks=$checks;board_contact=$false}|ConvertTo-Json
