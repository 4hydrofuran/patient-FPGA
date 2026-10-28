$ErrorActionPreference='Stop'
$entry=Join-Path $PSScriptRoot 'isolated_prepare_uart.ps1'
$tokens=$null;$errors=$null
[void][Management.Automation.Language.Parser]::ParseFile($entry,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Parser errors'}
$count=0
foreach($kernel in @('6.8.0-1036-xilinx','6.8.12-a10irq2')){
    foreach($step in @('network','network_readback')){
        $plan=& $entry -Step $step -ExpectedBoot '12345678-1234-4321-8765-123456789abc' -ExpectedKernel $kernel -ValidateOnly|ConvertFrom-Json
        if($plan.board_contact -or $plan.pl_or_compute -or $plan.boot_changes){throw 'Unsafe plan'}
        if(-not $plan.command.Contains($kernel) -or -not $plan.command.Contains('12345678-1234-4321-8765-123456789abc')){throw 'Identity not pinned'}
        if($plan.command -match '\b(reboot|reset|poweroff|modprobe|insmod|rmmod|saveenv|apt-get|dd)\b'){throw 'Unsafe operation'}
        if($step -eq 'network'){
            foreach($required in @('save no','ipv4.never-default yes','ipv4.ignore-auto-dns yes','connection.autoconnect no')){if(-not $plan.command.Contains($required)){throw 'Persistent/network default risk'}}
        }elseif($plan.command -match 'connection add|connection up|sudo') {throw 'Readback modifies network'}
        $count++
    }
}
$stage=& $entry -Step root_stage -ExpectedBoot '12345678-1234-4321-8765-123456789abc' -ExpectedKernel '6.8.12-a10irq2' -ValidateOnly|ConvertFrom-Json
if($stage.board_contact -or -not $stage.command.Contains('sudo -n /usr/bin/python3 -B -I -c') -or -not $stage.command.Contains('hashlib.sha256')){throw 'Stage pin/isolated interpreter missing'}
$count++
$off=& $entry -Step normal_poweroff -ExpectedBoot '12345678-1234-4321-8765-123456789abc' -ValidateOnly|ConvertFrom-Json
if($off.board_contact -or -not $off.command.EndsWith('sudo -n /usr/bin/systemctl poweroff') -or $off.command -match '--force|reboot|reset|saveenv'){throw 'Unsafe shutdown plan'}
if(-not $off.command.Contains('23a0ad7516d6f67f248f952653324c18a9c7d1db31fdf27a003f021adf0ca61e')){throw 'Missing recovery pin'}
$count++
$ro=& $entry -Step candidate_readonly -ExpectedBoot '12345678-1234-4321-8765-123456789abc' -ExpectedKernel '6.8.12-a10irq2' -ValidateOnly|ConvertFrom-Json
if($ro.board_contact -or -not $ro.command.Contains('reviewed_isolated_candidate_readonly.py') -or -not $ro.command.Contains('hashlib.sha256')){throw 'Read-only helper pin missing'}
$count++
[void](& $entry -Step execute_idle -ExpectedBoot 'c5baeabe-273d-447e-b323-ff07dd7af201' -ExpectedKernel '6.8.12-a10irq2' -ValidateOnly|ConvertFrom-Json|ForEach-Object {
    if($_.board_contact -or -not $_.pl_or_compute -or $_.compute -or -not $_.command.Contains('reviewed_launch_isolated_idle_once.py')){throw 'Idle plan scope is wrong'}
})
$count++
[ordered]@{status='PASS_PC_PLAN';plans=$count;board_contact=$false}|ConvertTo-Json
