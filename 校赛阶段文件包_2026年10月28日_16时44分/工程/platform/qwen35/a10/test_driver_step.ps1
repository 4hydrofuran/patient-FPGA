$ErrorActionPreference='Stop'
$path=Join-Path $PSScriptRoot 'driver_board_step.ps1'
$errors=$null;$tokens=$null
[void][System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Syntax error'}
foreach($step in @('temporary_nm_connection','boot_network_readonly','temporary_ip_resume','boot_recovery_readonly','temporary_ip_add','network_and_dates','linkage_once','xrt_date_proof','xrt_section_hashes','resume_preflight','fru_kernel_readonly','userspace_origin_followup','boot_fit_and_xrt_origin','userspace_dependencies','privileged_preflight','kernel_baseline','firmware_inventory','kernel_integrity','bootfw_readonly','unbound_preflight','transfer_diagnostics','closed_check','stage','load','post','unload')){
    $plan=& $path -Step $step -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
    if($plan.board_contact -ne $false){throw 'Unexpected board contact'}
    if($plan.command -match '\b(reboot|shutdown|modprobe|dkms|mkfs|flashcp)\b|rmmod\s+-f|--force|/dev/mem'){throw 'Forbidden mutation in plan'}
    if($step -eq 'load'){
        foreach($required in @('sha256sum','modules_disabled','lockdown','60000','sudo -n /usr/sbin/insmod','test ! -d /sys/module/zocl')){
            if(-not $plan.command.Contains($required)){throw "Missing load guard: $required"}
        }
    }
    if($step -eq 'stage' -and (-not $plan.command.Contains('mkdir /home/ubuntu/a10-driver-check-20261018-v2') -or $plan.command.Contains('mkdir -p'))){throw 'Stage must use a new directory'}
    if($step -eq 'unload' -and (-not $plan.command.Contains('/sys/module/zocl/refcnt') -or -not $plan.command.Contains('assert not nodes'))){throw 'Missing unload guards'}
    if($step -eq 'bootfw_readonly' -and (-not $plan.command.Contains('/usr/bin/image_update -p;') -or $plan.command -match 'bootfw_update|image_update\s+-[iv]')){throw 'Firmware operation must be print-only'}
    if($step -in @('unbound_preflight','load','unload')){
        foreach($required in @('xlnx,mpsoc_ocm','xlnx,rpu-channel','binding_candidates','driver_override','assert not bad')){
            if(-not $plan.command.Contains($required)){throw "Missing no-bind guard: $required"}
        }
    }
    if($plan.command.Length -gt 3500){throw 'Exceeds conservative terminal line budget'}
    if($step -eq 'temporary_nm_connection'){
        foreach($required in @('save no','connection.autoconnect no','ipv4.never-default yes','ipv4.ignore-auto-dns yes','ipv6.never-default yes','31582feb-665b-49ad-a289-1cfe8e2ee4f1','7423b8d4-31b0-4f1f-ae1b-4c265047a101','192.168.2.2/24','DEFAULT_ROUTE_BEFORE','DEFAULT_ROUTE_AFTER')){
            if(-not $plan.command.Contains($required)){throw "Missing temporary NM guard: $required"}
        }
        if($plan.command -match 'connection (modify|delete)|save yes|route add|addr flush|netplan|ufw|iptables|tee |write_text'){throw 'NM action exceeds temporary new connection'}
    }
    if($step -eq 'boot_network_readonly' -and $plan.command -match 'sudo |systemctl (start|stop|restart)|ip .*\b(add|del|flush)\b|nmcli|netplan|write_text|tee '){throw 'Network diagnosis must be read-only'}
    if($step -eq 'boot_recovery_readonly'){
        foreach($required in @('31582feb-665b-49ad-a289-1cfe8e2ee4f1','test ! -d /sys/module/zocl','timeout 5','st_size<=16384','BOOT_SCRIPT_BACKUP','findmnt')){
            if(-not $plan.command.Contains($required)){throw "Missing boot-read guard: $required"}
        }
        if($plan.command -match 'sudo |write_bytes|write_text|open\(.wb|\bdd\b|saveenv|image_update|loadapp|insmod|rmmod|chmod|mkdir|tee |\bcp\b'){throw 'Boot backup step must be read-only'}
    }
    if($step -in @('temporary_ip_add','temporary_ip_resume')){
        foreach($required in @('00:0a:35:0f:2d:70','192.168.2.2/24 dev eth0','test -z','DEFAULT_ROUTE_BEFORE','DEFAULT_ROUTE_AFTER')){
            if(-not $plan.command.Contains($required)){throw "Missing temporary-IP guard: $required"}
        }
        if($plan.command -match 'route add|route del|addr flush|netplan|ufw|iptables|sysctl -w|tee '){throw 'Network scope exceeded'}
        if($step -eq 'temporary_ip_resume' -and (-not $plan.command.Contains('31582feb-665b-49ad-a289-1cfe8e2ee4f1') -or $plan.command.Contains('d07af077-84c9-4910-8529-95757a09106d'))){throw 'Wrong resume boot'}
    }
    if($step -eq 'linkage_once'){
        foreach($required in @('timeout=3','--check-linkage','LD_BIND_NOW','test ! -d /sys/module/zocl','d25040172f0bb67b04e2e85233a2ae4a27e85cc6314de4beb9994b60d4f0243d','d07af077-84c9-4910-8529-95757a09106d')){
            if(-not $plan.command.Contains($required)){throw "Missing linkage guard: $required"}
        }
        if($plan.command -match '--execute-authorized-short|sudo |insmod|loadapp'){throw 'Linkage action must not call a device'}
    }
    if($step -eq 'fru_kernel_readonly'){
        foreach($required in @("open('rb').read(1024)",'/usr/bin/timeout 5','sudo -n true','1-0050/eeprom','1-0051/eeprom')){
            if(-not $plan.command.Contains($required)){throw "Missing bounded read guard: $required"}
        }
        if($plan.command -match 'i2cset|write_bytes|write_text|open\(.wb|\bdd\b'){throw 'FRU action must be read-only'}
    }
}
$newPlan=& $path -Step boot_resume_readonly_20261020 -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
if($newPlan.board_contact -ne $false -or $newPlan.command.Length -gt 3500){throw 'Invalid resume plan'}
foreach($required in @('0b6e8bb1-2219-4f67-b4f2-0a3e9718eaa1','ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec','timeout 5 sha256sum','test ! -d /sys/module/zocl','60000','findmnt')){
    if(-not $newPlan.command.Contains($required)){throw "Missing resume guard: $required"}
}
if($newPlan.command -match 'sudo (?!-n true)|connection (add|up|modify)|\b(reboot|shutdown|saveenv|insmod|rmmod|loadapp|flashcp|dd|chmod|mkdir)\b'){throw 'Resume read-only scope exceeded'}
$toolsPlan=& $path -Step resume_tools_readonly_20261020 -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
if($toolsPlan.board_contact -ne $false -or $toolsPlan.command.Length -gt 3500){throw 'Invalid tools plan'}
foreach($required in @('0b6e8bb1-2219-4f67-b4f2-0a3e9718eaa1','test ! -d /sys/module/zocl','timeout 5 journalctl','60000')){
    if(-not $toolsPlan.command.Contains($required)){throw "Missing tools guard: $required"}
}
if($toolsPlan.command -match 'nmcli|sudo (?!-n true)|\b(reboot|shutdown|saveenv|insmod|rmmod|loadapp|flashcp|dd|chmod|mkdir)\b'){throw 'Tools read-only scope exceeded'}
$inventory=& $path -Step candidate_inventory_readonly_20261020 -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
if($inventory.board_contact -ne $false -or $inventory.command.Length -gt 3500){throw 'Invalid inventory plan'}
foreach($required in @('eb429b2f-66aa-4959-8610-bfcfabcf0202','60000','test ! -d /sys/module/zocl','test ! -e /usr/lib/modules/6.8.12-a10irq1','busctl --timeout=3 get-property')){
    if(-not $inventory.command.Contains($required)){throw "Missing inventory guard: $required"}
}
if($inventory.command -match 'sudo |nmcli|\b(reboot|shutdown|saveenv|insmod|rmmod|loadapp|flashcp|dd|chmod|mkdir)\b'){throw 'Inventory read-only scope exceeded'}
$network=& $path -Step temporary_candidate_nm -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
foreach($required in @('eb429b2f-66aa-4959-8610-bfcfabcf0202','save no','connection.autoconnect no','ipv4.never-default yes','ipv4.ignore-auto-dns yes','192.168.2.2/24','DEFAULT_ROUTE_BEFORE','DEFAULT_ROUTE_AFTER')){
    if(-not $network.command.Contains($required)){throw "Missing candidate temporary network guard: $required"}
}
if($network.command -match 'connection (modify|delete)|save yes|route add|addr flush|netplan|ufw|iptables|tee |write_text'){throw 'Candidate network scope exceeded'}
foreach($step in @('candidate_network_readonly','previous_candidate_log')){
    $readPlan=& $path -Step $step -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
    if($readPlan.board_contact -ne $false -or $readPlan.command.Length -gt 3500){throw 'Invalid new read-only plan'}
    if($readPlan.command -match 'sudo |nmcli|\b(reboot|shutdown|saveenv|insmod|rmmod|loadapp|flashcp|dd|chmod|mkdir)\b'){throw 'Read-only plan mutation'}
    if($step -eq 'previous_candidate_log' -and
       (-not $readPlan.command.Contains('41cd1765c29c4e748b3fe7e5178fb3f6') -or
        -not $readPlan.command.Contains('1048576'))){throw 'Archived log must bind boot and byte limit'}
}
$fixtureBoot='12345678-1234-4234-8234-123456789abc'
foreach($step in @('candidate_idle_network','candidate_idle_network_readonly','candidate_idle_raw_kernel')){
    $readPlan=& $path -Step $step -CandidateBootId $fixtureBoot -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) | ConvertFrom-Json
    if($readPlan.board_contact -ne $false -or $readPlan.command.Length -gt 3500){throw 'Invalid candidate idle plan'}
    foreach($required in @($fixtureBoot,'6.8.12-a10irq1','ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec','test ! -d /sys/module/zocl')){
        if(-not $readPlan.command.Contains($required)){throw "Candidate identity missing: $required"}
    }
    if($readPlan.command -match '\b(reboot|shutdown|saveenv|insmod|rmmod|loadapp|flashcp|dd|chmod|mkdir)\b'){throw 'Candidate idle setup exceeded scope'}
    if($step -eq 'candidate_idle_network'){
        foreach($required in @('save no','connection.autoconnect no','ipv4.never-default yes','ipv4.ignore-auto-dns yes','55000')){
            if(-not $readPlan.command.Contains($required)){throw "Missing candidate network limit: $required"}
        }
        if($readPlan.command -match 'connection (modify|delete)|save yes|route add|addr flush|netplan|ufw|iptables|write_text'){throw 'Persistent network mutation'}
    }elseif($readPlan.command -match 'nmcli|write_text|write_bytes|dmesg (-c|--clear)|ip .* (add|del|flush) '){throw 'Read-only candidate check mutated state'}
    if($step -eq 'candidate_idle_raw_kernel' -and (-not $readPlan.command.Contains('dmesg --raw |') -or $readPlan.command.Contains('--color') -or -not $readPlan.command.Contains('1048576'))){throw 'Raw log format/bound invalid or mutually exclusive color option'}
}
$badRejected=$false
try { & $path -Step candidate_idle_raw_kernel -ValidateOnly -OutputPath ([IO.Path]::Combine([IO.Path]::GetTempPath(),[guid]::NewGuid().ToString()+'.json')) }
catch { $badRejected=$true }
if(-not $badRejected){throw 'Missing fresh candidate boot was accepted'}
[ordered]@{status='PASS_PC_PLAN_ONLY';steps=35;board_contact=$false}|ConvertTo-Json
