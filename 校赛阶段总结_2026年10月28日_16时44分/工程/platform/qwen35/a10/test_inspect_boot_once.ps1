$ErrorActionPreference='Stop'
. "$PSScriptRoot/inspect_boot_once.ps1" -DefinitionsOnly
$checks=0
function Assert([bool]$Value,[string]$Why){if(-not $Value){throw $Why};$script:checks++}
Assert (Test-LinuxPrompt "ubuntu@kria:~$ ") 'Linux shell'
Assert (Test-LinuxPrompt ("`r`n"+[char]27+"[?2004l`r"+[char]27+"[?2004hubuntu@kria:~$ ")) 'Real bracketed paste prompt regression'
Assert ((Normalize-Terminal ("`r`n"+[char]27+"[?2004hubuntu@kria:~$ ")) -match '(?m)^ubuntu@kria:[^\r\n]*\$\s*$') 'Receiver matching uses normalization'
Assert (-not (Test-LinuxPrompt 'kria login:')) 'Login is not shell'
Assert (-not (Test-LinuxPrompt '[sudo] password:')) 'Password is not shell'
Assert (Test-BootPrompt "U-Boot`r`nZynqMP> ") 'Boot prompt'
Assert (-not (Test-BootPrompt 'echo ZynqMP>')) 'Echo not prompt'
Assert (Test-AutobootCountdown "U-Boot 2022.01 (build)`r`nHit any key to stop autoboot:  2 ") 'Fresh countdown'
Assert (-not (Test-AutobootCountdown 'Hit any key to stop autoboot: 2')) 'Require fresh banner'
Assert (-not (Test-AutobootCountdown "U-Boot 2022.01`nHit any key to stop autoboot: 0")) 'Do not send after zero'
Assert (-not (Test-AutobootCountdown "U-Boot 2022.01`nStarting kernel`nHit any key to stop autoboot: 2")) 'No input after kernel'
Assert (Test-AuthPrompt '__A10_SUDO_AUTH__:') 'Actual auth challenge'
Assert (-not (Test-AuthPrompt "sudo -p '__A10_SUDO_AUTH__:' -v")) 'Echo not auth challenge'
Assert (Test-QueryResult "U-Boot 2022.01`nZynqMP> ") 'Query success'
Assert (-not (Test-QueryResult "Unknown command 'help'`nZynqMP> ")) 'Unknown command stops'
Assert (-not (Test-QueryResult "## Error: variable not defined`nZynqMP> ")) 'Query error stops'
Assert ($preflight.Contains($expectedBoot)) 'Exact boot guard'
Assert ($preflight.Contains('all(0<x<60000')) 'Thermal guard'
Assert ($preflight.Contains('test ! -d /sys/module/zocl')) 'No active zocl'
$source=Get-Content -LiteralPath "$PSScriptRoot/inspect_boot_once.ps1" -Raw
Assert (($source | Select-String -Pattern 'systemctl reboot' -AllMatches).Matches.Count -eq 1) 'Single reboot invocation in source'
Assert (-not ($source -match 'saveenv|fw_setenv|insmod|rmmod|Set-ExecutionPolicy')) 'No persistent mutation/loading'
Assert ($source.Contains('[IO.FileMode]::CreateNew')) 'Evidence exclusive reservation'
Assert ($source.Contains('$serial.DtrEnable=$false; $serial.RtsEnable=$false')) 'No modem-line assertion'
Assert ($source.Contains('.Replace($secret,''[REDACTED]'')')) 'Credential redaction'
foreach($step in @('som','carrier','distro','boot_files')){
    $plan=& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot/uboot_readonly_step.ps1" -Step $step -OutputPath unused-test-path -ValidateOnly
    Assert ($LASTEXITCODE -eq 0) "Read-only plan $step"
    Assert (-not ($plan -match '(^|\s)(saveenv|setenv|reset|run|bootm|bootd|booti)(\s|$)' | Where-Object {$_ -notmatch '^help '})) "Read-only command allowlist $step"
}
$resume=& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot/resume_original_boot.ps1" -OutputPath unused-test-path -ValidateOnly | ConvertFrom-Json
Assert ($LASTEXITCODE -eq 0 -and $resume.resume -eq 'run bootcmd') 'Original boot continuation plan'
Assert ($resume.postcheck.Contains('6.8.0-1015-xilinx')) 'Original kernel readback'
Assert ($resume.postcheck.Contains('test ! -d /sys/module/zocl')) 'No candidate module readback'
$loginPlan=& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot/resume_original_boot.ps1" -OutputPath unused-test-path -ValidateOnly -LoginOnly | ConvertFrom-Json
Assert ($LASTEXITCODE -eq 0 -and $null -eq $loginPlan.resume) 'Login-only never resumes or reboots'
Assert (-not (Test-Path -LiteralPath unused-test-path)) 'Dry runs do not reserve/write evidence'
$powerPlan=& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot/resume_original_boot.ps1" -OutputPath unused-test-path -ValidateOnly -LoginOnly -AuthorizedReconnectReadOnly | ConvertFrom-Json
Assert ($LASTEXITCODE -eq 0 -and $null -eq $powerPlan.resume) 'Power resume cannot boot or reboot'
Assert ($powerPlan.postcheck.Contains('set -o pipefail')) 'Log producer failure retained'
Assert ($powerPlan.postcheck.Contains('1048576')) 'Compressed log decompressed byte budget'
Assert ($powerPlan.postcheck.Contains('6.8.0-1015-xilinx|6.8.12-a10irq1')) 'Reconnect explicitly recognizes either known kernel'
Assert (-not ($powerPlan.postcheck -match '\bsudo\b|\b(insmod|rmmod|saveenv|reboot|loadapp)\b|write_text|write_bytes')) 'Reconnect is read-only'
Write-Output "PASS $checks PC safety checks; no board contact"
