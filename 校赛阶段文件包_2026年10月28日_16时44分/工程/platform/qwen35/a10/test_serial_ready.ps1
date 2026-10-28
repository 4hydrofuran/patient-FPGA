$ErrorActionPreference='Stop'
$fixture=[char]27+'[?2004l'+"`rA10DRV_READY`r`n"
if($fixture -match '(?m)^A10DRV_READY\r?$'){throw 'Old failure no longer reproduced'}
if($fixture -notmatch '(?m)(?:^|\r)A10DRV_READY\r?$'){throw 'CR prompt boundary not handled'}
if("A10DRV_READY`r`n" -notmatch '(?m)(?:^|\r)A10DRV_READY\r?$'){throw 'Ordinary line failed'}
if('X_A10DRV_READY' -match '(?m)(?:^|\r)A10DRV_READY\r?$'){throw 'Partial token admitted'}
$errors=$null;$tokens=$null
[void][System.Management.Automation.Language.Parser]::ParseFile("$PSScriptRoot/transfer_driver_uart.ps1",[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Parse failed'}
'PASS_PC_CR_BOUNDARY_REPRO_AND_3_REGEX_CHECKS_PARSE_ONLY'
