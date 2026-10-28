$ErrorActionPreference='Stop'
$scriptPath=Join-Path $PSScriptRoot 'collect_readonly_uart.ps1'
$parseErrors=$null
$tokens=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($scriptPath,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw 'Parser errors' }
$checked=0
foreach ($phase in @('initial','sensors_dt','package_metadata','binding','dt_snapshot','driver_preflight','recovery_readback','network_confirm','irq2_preboot_diagnose','lease_identity','peer_inventory','peer_artifacts','peer_archive_index','peer_confirm','peer_run_location','peer_results','peer_executor_source','isolated_preflight','isolated_assets')) {
    $plan = & $scriptPath -ValidateOnly -Phase $phase -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[Guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
    if ($plan.board_contact -ne $false) { throw 'Dry run attempted board contact' }
    foreach ($job in $plan.jobs) {
        if ($phase -in @('driver_preflight','isolated_assets') -and $job.name -eq 'sudo_noninteractive_probe' -and $job.command -eq 'sudo -n true') { $checked++; continue }
        $commandToCheck = $job.command -replace 'command -v insmod; command -v rmmod;', ''
        if ($phase -eq 'peer_artifacts' -and $job.name -eq 'peer_step5_names') {
            if (-not $job.command.StartsWith('sudo -n -- find /home/ubuntu/a10-irq2-step5-20261022 -mindepth 1 -maxdepth 2 -type f -printf ')) { throw 'Privileged directory listing changed scope' }
            $commandToCheck = $job.command.Substring('sudo -n -- '.Length)
        }
        if ($phase -eq 'peer_confirm' -and $job.name -eq 'peer_root_project_names') {
            if ($job.command -ne 'sudo -n -- find /root -mindepth 1 -maxdepth 1 -name "a10-*" -printf "%y %p\n"') { throw 'Privileged root listing changed scope' }
            $commandToCheck = $job.command.Substring('sudo -n -- '.Length)
        }
        if ($phase -eq 'peer_results' -and $job.command.StartsWith('sudo ')) {
            $allowedReads = @(
                'sudo -n -- find /var/lib/kv260-a10/a10-refcount-step5-20261022-v1 -mindepth 1 -maxdepth 1 -type f -printf "%f %s bytes\n"',
                'sudo -n -- sha256sum /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/actual_output.json /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/golden.json /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/zocl.refcount.ko',
                'sudo -n -- cat /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/actual_output.json',
                'sudo -n -- cat /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/golden.json'
            )
            if ($job.command -notin $allowedReads) { throw 'Privileged evidence read changed scope' }
            $commandToCheck = $job.command.Substring('sudo -n -- '.Length)
        }
        if ($commandToCheck -match '\b(sudo|modprobe|insmod|rmmod|reboot|shutdown|reset|dd|mkfs|mount|make|apt-get|tee)\b|\bapt\s+(install|update)|(?<![<])>(?![>])') { throw "Mutation found in $($job.name)" }
        $checked++
    }
}
if ($checked -ne 55) { throw "Unexpected command group count: $checked" }
$text=Get-Content -LiteralPath $scriptPath -Raw
if ($text -notmatch 'finally' -or $text -notmatch '\$serial.Close\(\)' -or $text -notmatch '\$serial.DtrEnable = \$false') { throw 'Serial cleanup/control guard missing' }
$pattern='(?:thermal_zone\d+/temp|hwmon\d+/temp\d+_input):\s*(\d+)'
foreach ($sensor in @('thermal_zone0/temp: 60000','hwmon0/temp1_input: 60000')) {
    $m=[regex]::Match($sensor,$pattern)
    if (-not $m.Success -or [int]$m.Groups[1].Value -lt 60000) { throw 'Temperature stop pattern failed' }
}
[ordered]@{status='PASS_PC_PLAN_CHECK_NOT_BOARD';command_groups=$checked;syntax='PASS';dry_run_phases=19;temperature_patterns=2;board_contact=$false} | ConvertTo-Json
