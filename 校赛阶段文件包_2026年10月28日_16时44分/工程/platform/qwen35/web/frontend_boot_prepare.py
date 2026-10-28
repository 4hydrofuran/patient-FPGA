"""Derive the recorded irq2 cold-boot procedure for this authorized single normal reboot."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
source=(ROOT/'platform/qwen35/a10/cold_boot_irq2_once.ps1').read_text(encoding='utf-8')
before="""    $report.status='ARMED_PASSIVE_WAIT_FOR_USER_POWER'
    Event 'armed' 'No input sent. Awaiting fresh U-Boot countdown.'
    Write-Host 'ARMED: COM5 passive capture ready. No power/reset command sent.'"""
after=r'''    $serial.Write("`r")
    $hello=Receive-Cold '(?m)^ubuntu@kria:[^\r\n]*\$\s*$|login:|password:|ZynqMP>' 5
    Event 'authenticated_shell' $hello
    if((Normalize-Cold $hello) -notmatch '(?m)^ubuntu@kria:[^\r\n]*\$\s*$'){throw 'Existing authenticated shell required; reboot not sent'}
    $guard='set -e; test "$(cat /proc/sys/kernel/random/boot_id)" = 624d896f-3a30-4c85-990c-1970373d2d28; test "$(uname -r)" = 6.8.0-1036-xilinx; test "$(sha256sum /etc/machine-id | cut -d '' '' -f1)" = ea4ea714200e50181c4375b385b1e3c4a0f6d199ccb60182d62f86bcf47b64ec; test ! -e /var/lock/kv260-a1/active; test ! -d /sys/module/zocl; test "$(cat /sys/kernel/config/device-tree/overlays/k26-starter-kits_image_1/status)" = applied; test "$(sha256sum /boot/firmware/a10-candidate-irq2-20261021.fit | cut -d '' '' -f1)" = e60d7f49033ef8efbd2396fafbe94a3bc684a478d5f5e31676626d1bc5f6ae2b'
    $tag='PREBOOT_'+[Guid]::NewGuid().ToString('N')
    $serial.Write('( '+$guard+' ); rc=$?; printf ''\n'+$tag+':%s\n'' "$rc"'+"`r")
    $reply=Receive-Cold ('(?m)^'+$tag+':\d+\s*$') 15
    Event 'preboot_identity_result' $reply
    if((Normalize-Cold $reply) -notmatch ('(?m)^'+$tag+':0\s*$')){throw 'Current boot/package guard failed; no reboot'}
    $auth='AUTH_'+[Guid]::NewGuid().ToString('N')
    $serial.Write('sudo -p __A_IRQ2_SUDO_AUTH__: -v; rc=$?; printf ''\n'+$auth+':%s\n'' "$rc"'+"`r")
    $reply=Receive-Cold ('(?m)^__A_IRQ2_SUDO_AUTH__:\s*$|^'+$auth+':\d+\s*$') 8
    if((Normalize-Cold $reply) -match '(?m)^__A_IRQ2_SUDO_AUTH__:\s*$'){
        $info=[Diagnostics.ProcessStartInfo]::new()
        $info.FileName=Join-Path $PSScriptRoot '../../../evidence/model_pl_A/20261024-ttft10-01-v1/tt10_01_askpass.exe'
        $info.Arguments='KV260 authorized one-time irq2 reboot'
        $info.UseShellExecute=$false;$info.CreateNoWindow=$true;$info.RedirectStandardOutput=$true
        $child=[Diagnostics.Process]::Start($info)
        $secret=$child.StandardOutput.ReadToEnd().TrimEnd("`r","`n");$child.WaitForExit()
        if($child.ExitCode -ne 0 -or [string]::IsNullOrEmpty($secret) -or $secret.Contains("`n") -or $secret.Contains("`r")){throw 'User authentication cancelled; no reboot'}
        $serial.Write($secret+"`r");$secret=$null
        $reply=Receive-Cold ('(?m)^'+$auth+':\d+\s*$|^__A_IRQ2_SUDO_AUTH__:\s*$') 10
    }
    Event 'sudo_result_no_credentials' $reply
    if((Normalize-Cold $reply) -notmatch ('(?m)^'+$auth+':0\s*$')){throw 'Sudo not confirmed; no reboot'}
    $wire='( '+$guard+' ) && sudo -n /usr/bin/systemctl reboot'
    $report.reboot_commands_sent=1;Event 'authorized_single_normal_reboot' $wire
    $serial.Write($wire+"`r")
    $report.status='ONE_NORMAL_REBOOT_SENT'
    Write-Host 'One normal reboot sent; capturing the fresh U-Boot countdown.'
'''
assert source.count(before)==1
source=source.replace(before,after)
source=source.replace("schema='A10_ONE_MANUAL_COLD_IRQ2_BOOT_V1'","schema='A12_B_LATEST_AUTHORIZED_NORMAL_IRQ2_BOOT_V1'")
source=source.replace('$watch.Elapsed.TotalSeconds -lt 300','$watch.Elapsed.TotalSeconds -lt 100')
source=source.replace("$serial=$null\nfunction Event", "$serial=$null\n$secret=$null\nfunction Event")
source=source.replace("    $report.closed=$true;Event 'serial_closed'", "    $secret=$null\n    $report.closed=$true;Event 'serial_closed'")
destination=Path(__file__).with_name('frontend_boot_once.ps1')
destination.write_text(source,encoding='utf-8')
print(destination)
