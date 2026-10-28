param([Parameter(Mandatory=$true)][string]$OutputPath,
      [ValidateSet('initial','sensors_dt','package_metadata','binding','dt_snapshot','driver_preflight','recovery_readback','network_confirm','irq2_preboot_diagnose','lease_identity','peer_inventory','peer_artifacts','peer_archive_index','peer_confirm','peer_run_location','peer_results','peer_executor_source','isolated_preflight','isolated_assets')][string]$Phase='initial',
      [switch]$ValidateOnly)
$ErrorActionPreference = 'Stop'
# Fixed read-only command list. Never accepts a caller-provided remote command.
# The user must release COM5 and leave an already authenticated Linux shell.
if (Test-Path -LiteralPath $OutputPath) { throw 'Refusing to overwrite evidence' }
$identity = 'FTDIBUS\VID_0403+PID_6011+XFL1CYYPZ52YB\0000'
$jobs = @(
    @{name='identity'; command='uname -a; cat /etc/os-release; tr "\000" "\n" < /proc/device-tree/model; tr "\000" "\n" < /proc/device-tree/compatible; cat /proc/cmdline; id'},
    @{name='health'; command='cat /proc/uptime; grep -E "MemTotal|MemAvailable|CmaTotal|CmaFree" /proc/meminfo; for p in /sys/class/thermal/thermal_zone*/temp /sys/class/thermal/thermal_zone*/type /sys/class/hwmon/hwmon*/temp*_input /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done; grep -E "Features|CPU part|CPU implementer" /proc/cpuinfo'},
    @{name='driver'; command='dpkg-query -W xrt xrt-dkms linux-headers-6.8.0-1015-xilinx linux-xilinx-headers-6.8.0-1015; modinfo zocl; ls -l /dev/dri; readlink -f /sys/class/drm/card0/device/driver; command -v python3; command -v timeout'},
    @{name='network'; command='ip -br addr; ip route; systemctl is-active ssh; ss -ltn; df -h /'},
    @{name='kernel_build'; command='ls -ld /lib/modules/6.8.0-1015-xilinx/build; sha256sum /boot/config-6.8.0-1015-xilinx /usr/src/linux-headers-6.8.0-1015-xilinx/Module.symvers; grep -E "CONFIG_(MODVERSIONS|MODULE_SIG|DRM_ZOCL|PREEMPT|ARM64_PAGE_SHIFT|LOCALVERSION)" /boot/config-6.8.0-1015-xilinx; ls -l /sys/class/fpga_manager/fpga0; cat /sys/class/fpga_manager/fpga0/state; find /proc/device-tree -iname "*zocl*" -o -iname "*zyxclmm*"'}
)
if ($Phase -eq 'sensors_dt') {
    $jobs = @(
        @{name='sensors'; command='for p in /sys/class/hwmon/hwmon*/name /sys/class/hwmon/hwmon*/temp*_input /sys/class/hwmon/hwmon*/temp*_label /sys/bus/iio/devices/iio:device*/name /sys/bus/iio/devices/iio:device*/in_temp*_raw /sys/bus/iio/devices/iio:device*/in_temp*_scale /sys/bus/iio/devices/iio:device*/in_temp*_offset; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'},
        @{name='dt_memory'; command='for p in /proc/device-tree/memory*/reg /proc/device-tree/reserved-memory/*/reg /proc/device-tree/reserved-memory/*/size /proc/device-tree/reserved-memory/*/compatible; do if test -r "$p"; then printf "%s BASE64=" "$p"; base64 -w0 "$p"; printf "\n"; fi; done; ls -l /sys/firmware/fdt; systemctl is-active ssh.socket; command -v fru-print; command -v xmutil'},
        @{name='header_pkg'; command='dpkg-query -s linux-headers-6.8.0-1015-xilinx linux-xilinx-headers-6.8.0-1015 | grep -E "^(Package|Source|Version|Architecture|Depends):"; ls /usr/src/linux-headers-6.8.0-1015-xilinx/include/generated/utsrelease.h; cat /usr/src/linux-headers-6.8.0-1015-xilinx/include/generated/utsrelease.h'}
    )
}
if ($Phase -eq 'package_metadata') {
    $jobs = @(
        @{name='header_origin'; command='apt-cache show linux-headers-6.8.0-1015-xilinx=6.8.0-1015.16 linux-xilinx-headers-6.8.0-1015=6.8.0-1015.16 | grep -E "^(Package|Version|Filename|SHA256|Size):"'},
        @{name='dt_cells'; command='for p in /proc/device-tree/#address-cells /proc/device-tree/#size-cells /proc/device-tree/reserved-memory/#address-cells /proc/device-tree/reserved-memory/#size-cells; do if test -r "$p"; then printf "%s BASE64=" "$p"; base64 -w0 "$p"; printf "\n"; fi; done'}
    )
}
if ($Phase -eq 'binding') {
    $jobs = @(
        @{name='sensors'; command='for p in /sys/class/hwmon/hwmon*/temp*_input; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'},
        @{name='dt_binding'; command='python3 -c "import pathlib,json,base64; r=pathlib.Path(''/proc/device-tree''); nodes=list(r.rglob(''compatible'')); assert len(nodes)<512; props=(''compatible'',''status'',''reg'',''interrupts'',''interrupt-parent'',''phandle'',''firmware-name''); rows=[dict(path=str(p.parent),properties={k:base64.b64encode((p.parent/k).read_bytes()).decode() for k in props if (p.parent/k).is_file()}) for p in nodes]; print(json.dumps(dict(count=len(rows),nodes=rows)))"'},
        @{name='firmware_inventory'; command='find /lib/firmware/xilinx -maxdepth 3 -type f -printf "%p %s bytes\n"; ls -ld /sys/kernel/config/device-tree/overlays; grep configfs /proc/mounts; ls -l /sys/class/fpga_manager/fpga0; cat /sys/class/fpga_manager/fpga0/state'}
    )
}
if ($Phase -eq 'dt_snapshot') {
    $jobs = @(
        @{name='dt_snapshot'; command='python3 -c "import pathlib,json,base64; r=pathlib.Path(''/proc/device-tree''); files=[p for p in r.rglob(''*'') if p.is_file()]; assert len(files)<4096; rows={str(p.relative_to(r)):base64.b64encode(p.read_bytes()).decode() for p in files}; out=json.dumps(rows); assert len(out)<200000; print(out)"'}
    )
}
if ($Phase -eq 'driver_preflight') {
    $jobs = @(
        @{name='sensors'; command='uname -r; id; cat /proc/sys/kernel/tainted; for p in /sys/class/hwmon/hwmon*/temp*_input /sys/kernel/security/lockdown /proc/sys/kernel/modules_disabled; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done; grep -E "MemAvailable|CmaFree" /proc/meminfo'},
        @{name='driver_preflight'; command='lsmod; test ! -d /sys/module/zocl; printf "zocl_absent_rc=%s\n" "$?"; command -v insmod; command -v rmmod; command -v curl; df -k /home/ubuntu; ip -br addr; dmesg --color=never | tail -n 35'},
        @{name='sudo_noninteractive_probe'; command='sudo -n true'}
    )
}
if ($Phase -eq 'recovery_readback') {
    $jobs = @(
        @{name='recovered_boot'; command='cat /proc/sys/kernel/random/boot_id; uname -r; tr "\000" "\n" < /proc/device-tree/model; cat /proc/sys/kernel/tainted; findmnt -n -o SOURCE,FSTYPE,OPTIONS /; for p in /sys/module/*/taint; do if test -s "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'},
        @{name='kernel_warnings'; command='timeout 4 journalctl -k -b --no-pager -p warning -n 120'},
        @{name='current_configuration'; command='ls -l /sys/kernel/config/device-tree/overlays; cat /sys/class/fpga_manager/fpga0/state; ls -l /dev/dri; ip -br addr'}
    )
}
if ($Phase -eq 'network_confirm') {
    $jobs = @(
        @{name='network_address'; command='cat /proc/sys/kernel/random/boot_id; ip -br addr show eth0; ip -4 route show default; ss -ltn; cat /sys/class/net/eth0/address'},
        @{name='network_unsaved'; command='set -e; a10_path=$(busctl --timeout=3 call org.freedesktop.NetworkManager /org/freedesktop/NetworkManager/Settings org.freedesktop.NetworkManager.Settings GetConnectionByUuid s 7423b8d4-31b0-4f1f-ae1b-4c265047a101 | sed -n ''s/^o "\(\/org\/freedesktop\/NetworkManager\/Settings\/[0-9]\+\)"$/\1/p''); test -n "$a10_path"; printf "CONNECTION_PATH %s\n" "$a10_path"; busctl --timeout=3 get-property org.freedesktop.NetworkManager "$a10_path" org.freedesktop.NetworkManager.Settings.Connection Unsaved'}
    )
}
if ($Phase -eq 'irq2_preboot_diagnose') {
    $jobs = @(
        @{name='candidate_files'; command='cat /proc/sys/kernel/random/boot_id; ls -ld /usr/lib/modules/6.8.12-a10irq2 /var/lock/kv260-a1/active; sha256sum /boot/firmware/image.fit /boot/firmware/boot.scr.uimg /boot/firmware/a10-candidate-irq2-20261021.fit /usr/lib/modules/6.8.12-a10irq2/extra/zocl.ko'},
        @{name='stage_receipt'; command='tail -n 1 /home/ubuntu/a10-irq2-stage-20261021-v1/stage-result.jsonl; ls -ld /var/lock/kv260-a1; readlink /var/lock/kv260-a1/active; ps -eo pid,comm | grep -E "python|a10|dfx"'}
    )
}
if ($Phase -eq 'lease_identity') {
    $jobs = @(
        @{name='lease_identity_redacted'; command='python3 -c "import json,hashlib; from pathlib import Path; p=Path(''/var/lock/kv260-a1/active/lease.json''); b=p.read_bytes(); d=json.loads(b); keys=(''owner'',''scope'',''identity'',''pid'',''issued_unix'',''expires_unix'',''compute_authorized''); o={k:d.get(k) for k in keys}; o[''lease_sha256'']=hashlib.sha256(b).hexdigest(); o[''current_boot'']=Path(''/proc/sys/kernel/random/boot_id'').read_text().strip(); pid=d.get(''pid''); q=Path(''/proc'')/str(pid); o[''pid_exists'']=q.is_dir(); o[''pid_comm'']=(q/''comm'').read_text().strip() if q.is_dir() else None; print(json.dumps(o))"'},
        @{name='visible_process_identity'; command='cat /proc/1445/comm; readlink /proc/1445/exe; cat /proc/1445/cgroup; ls -l /var/lock/kv260-a1/active; test ! -d /sys/module/zocl; printf "zocl_absent_rc=%s\n" "$?"'}
    )
}
if ($Phase -eq 'peer_inventory') {
    # Directory names and current health only. Never execute discovered scripts,
    # inspect credentials, recurse through the whole filesystem or hash big FITs.
    $jobs = @(
        @{name='health'; command='uname -r; cat /proc/sys/kernel/random/boot_id; tr "\000" "\n" < /proc/device-tree/model; id; pwd; cat /proc/uptime /proc/loadavg; grep -E "MemTotal|MemAvailable|CmaTotal|CmaFree" /proc/meminfo; for p in /sys/class/hwmon/hwmon*/temp*_input; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'},
        @{name='peer_home_directories'; command='timeout 4 find /home/ubuntu -mindepth 1 -maxdepth 1 -name "a10-*" -printf "%y %p\n"'},
        @{name='peer_refcount_directories'; command='for p in /home/ubuntu/a10-refcount* /home/ubuntu/a10-irq2*; do if test -d "$p"; then timeout 3 find "$p" -mindepth 1 -maxdepth 1 -printf "%y %p %s bytes\n"; fi; done'}
    )
}
if ($Phase -eq 'peer_artifacts') {
    $jobs = @(
        @{name='peer_archive_hashes'; command='sha256sum /home/ubuntu/a10-refcount-build-20261022-v1/source.tar.gz /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz'},
        @{name='peer_source_names'; command='timeout 3 find /home/ubuntu/a10-refcount-build-20261022-v1/source -maxdepth 2 -type f \( -name "*.ko" -o -name "*.json" -o -name "*.patch" -o -name "Makefile" \) -printf "%p %s bytes\n"'},
        @{name='peer_step5_names'; command='sudo -n -- find /home/ubuntu/a10-irq2-step5-20261022 -mindepth 1 -maxdepth 2 -type f -printf "%p %s bytes\n"'},
        @{name='peer_default_state'; command='cat /proc/sys/kernel/random/boot_id; ls -l /sys/kernel/config/device-tree/overlays /dev/dri; cat /sys/class/fpga_manager/fpga0/state; if test -d /sys/module/zocl; then cat /sys/module/zocl/refcnt; else printf "ZOCL_ABSENT\n"; fi; systemctl is-active gdm'}
    )
}
if ($Phase -eq 'peer_archive_index') {
    $jobs = @(
        @{name='peer_execution_members'; command='timeout 3 tar -tzf /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz'},
        @{name='peer_temp_names'; command='timeout 3 find /var/tmp /tmp -mindepth 1 -maxdepth 1 -name "a10-*" -printf "%y %p\n"'},
        @{name='peer_build_result_keys'; command='python3 -c "import json; from pathlib import Path; p=Path(''/home/ubuntu/a10-refcount-build-20261022-v1/build_result.json''); assert p.stat().st_size<65536; d=json.loads(p.read_text()); print(json.dumps(dict(file=str(p),keys=sorted(d))))"'}
    )
}
if ($Phase -eq 'peer_confirm') {
    $jobs = @(
        @{name='peer_fixed_module_digest'; command='set -o pipefail; timeout 3 tar -xOzf /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz zocl.refcount.ko | sha256sum'},
        @{name='peer_root_project_names'; command='sudo -n -- find /root -mindepth 1 -maxdepth 1 -name "a10-*" -printf "%y %p\n"'},
        @{name='peer_executor_paths'; command='set -o pipefail; timeout 3 tar -xOzf /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz run_refcount_step5.py | grep --color=never -nE "actual_output|/root/|/home/|Path\(|__file__|chdir|cwd"'}
    )
}
if ($Phase -eq 'peer_run_location') {
    $jobs = @(
        @{name='peer_saved_project_paths'; command='python3 -c "import json,re; from pathlib import Path; r=Path(''/home/ubuntu/a10-refcount-build-20261022-v1''); names=(''postcompute_stop.json'',''root_preclose_snapshot.json'',''final_profile.json''); rows=[]; [(rows.append(dict(file=n,paths=sorted(set(re.findall(r''/(?:home|opt|var|root|tmp|run)/[^\s\x22]*refcount[^\s\x22]*'',(r/n).read_text())))))) for n in names if (r/n).stat().st_size<65536]; print(json.dumps(rows))"'},
        @{name='peer_home_directory_names'; command='timeout 3 find /home/ubuntu -mindepth 1 -maxdepth 1 -type d -printf "%f\n"'}
    )
}
if ($Phase -eq 'peer_results') {
    $jobs = @(
        @{name='peer_actual_run_files'; command='sudo -n -- find /var/lib/kv260-a10/a10-refcount-step5-20261022-v1 -mindepth 1 -maxdepth 1 -type f -printf "%f %s bytes\n"'},
        @{name='peer_actual_digests'; command='sudo -n -- sha256sum /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/actual_output.json /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/golden.json /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/zocl.refcount.ko'},
        @{name='peer_actual_output'; command='sudo -n -- cat /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/actual_output.json'},
        @{name='peer_actual_golden'; command='sudo -n -- cat /var/lib/kv260-a10/a10-refcount-step5-20261022-v1/golden.json'},
        @{name='health'; command='cat /proc/sys/kernel/random/boot_id /proc/loadavg; for p in /sys/class/hwmon/hwmon*/temp*_input; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'}
    )
}
if ($Phase -eq 'peer_executor_source') {
    $jobs = @(
        @{name='run_refcount_step5.py'; command='set -e -o pipefail; timeout 3 tar -xOzf /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz run_refcount_step5.py | base64 -w0; printf "\n"'},
        @{name='single_xrt_call.py'; command='set -e -o pipefail; timeout 3 tar -xOzf /home/ubuntu/a10-refcount-build-20261022-v1/execution_bundle.tar.gz single_xrt_call.py | base64 -w0; printf "\n"'}
    )
}
if ($Phase -eq 'isolated_preflight') {
    $jobs = @(
        @{name='health'; command='uname -r; cat /proc/sys/kernel/random/boot_id; sha256sum /etc/machine-id; cat /proc/loadavg; grep -E "MemTotal|MemAvailable|CmaTotal|CmaFree" /proc/meminfo; for p in /sys/class/hwmon/hwmon*/temp*_input; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done'},
        @{name='default_and_network'; command='for p in /sys/kernel/config/device-tree/overlays/*/status; do if test -r "$p"; then printf "%s: " "$p"; cat "$p"; fi; done; cat /sys/class/fpga_manager/fpga0/state; if test -d /sys/module/zocl; then cat /sys/module/zocl/refcnt; else printf "ZOCL_ABSENT\n"; fi; systemctl is-active gdm; ip -br addr show eth0; cat /proc/sys/kernel/tainted'},
        @{name='lease_and_lock_metadata'; command='python3 -c "import os,json,hashlib; from pathlib import Path; p=Path(''/var/lock/kv260-a1/active/lease.json''); d={''active_exists'':os.path.lexists(p.parent),''lease_exists'':p.exists(),''boot_id'':Path(''/proc/sys/kernel/random/boot_id'').read_text().strip()}; raw=p.read_bytes() if p.exists() else None; v=json.loads(raw) if raw else {}; d[''lease_sha256'']=hashlib.sha256(raw).hexdigest() if raw else None; d[''lease_public'']={k:v.get(k) for k in (''scope'',''identity'',''pid'',''window'',''compute_authorized'')}; names=(''/var/lock/kv260-a1/deployment.lock'',''/run/lock/patient-qwen-linear.lock''); locks=Path(''/proc/locks'').read_text().splitlines(); d[''locks'']=[dict(path=n,inode=Path(n).stat().st_ino,matching_rows=[l for l in locks if ('':''+str(Path(n).stat().st_ino)+'' '') in l]) for n in names if Path(n).exists()]; print(json.dumps(d))"'}
    )
}
if ($Phase -eq 'isolated_assets') {
    $jobs = @(
        @{name='normal_boot_hash'; command='set -e; uname -r; cat /proc/sys/kernel/random/boot_id; sha256sum /boot/firmware/image.fit /boot/firmware/boot.scr.uimg; stat -c "%n %s bytes" /boot/firmware/image.fit /boot/firmware/boot.scr.uimg'},
        @{name='irq2_boot_hash'; command='set -e; sha256sum /boot/firmware/a10-candidate-irq2-20261021.fit; stat -c "%n %s bytes" /boot/firmware/a10-candidate-irq2-20261021.fit; ls -ld /usr/lib/modules/6.8.12-a10irq2; cat /proc/cmdline'},
        @{name='restoration_assets'; command='set -e; sha256sum /usr/lib/libxrt_core.so.2.18.0 /usr/lib/libxrt_coreutil.so.2.18.0 /lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.bit.bin /lib/firmware/xilinx/k26-starter-kits/k26_starter_kits.dtbo; cat /etc/dfx-mgrd/default_firmware; cat /etc/ssh/ssh_host_ed25519_key.pub; cat /sys/class/net/eth0/address /sys/class/net/eth0/carrier; ip -4 route show default; df -k /home/ubuntu /var/lib /boot/firmware'},
        @{name='sudo_noninteractive_probe'; command='sudo -n true'}
    )
}
if ($ValidateOnly) {
    [ordered]@{phase=$Phase;board_contact=$false;jobs=$jobs} | ConvertTo-Json -Depth 5
    exit 0
}
$device = Get-PnpDevice -Class Ports -PresentOnly | Where-Object { $_.InstanceId -eq $identity -and $_.FriendlyName -match '\(COM5\)' -and $_.Status -eq 'OK' }
if (-not $device) { throw 'Expected COM5 USB identity not found' }
$serial = New-Object System.IO.Ports.SerialPort('COM5',115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.Handshake = [System.IO.Ports.Handshake]::None
$serial.DtrEnable = $false
$serial.RtsEnable = $false
$serial.ReadTimeout = 200
$serial.WriteTimeout = 1000
$report = [ordered]@{schema='A10_UART_READONLY_V1';utc=[DateTime]::UtcNow.ToString('o');port='COM5';usb_identity=$identity;domain='BOARD_READONLY';handshake='';records=@();status='NOT_STARTED';board_compute='NOT_TESTED';closed=$false}
function Read-Until([string]$pattern,[double]$seconds) {
    $buf = [System.Text.StringBuilder]::new()
    $clock = [System.Diagnostics.Stopwatch]::StartNew()
    while ($clock.Elapsed.TotalSeconds -lt $seconds) {
        if ($serial.BytesToRead -gt 0) {
            [void]$buf.Append($serial.ReadExisting())
            if ($buf.Length -gt 262144) { throw 'Receive cap exceeded' }
            if ($buf.ToString() -match $pattern) { break }
        }
        Start-Sleep -Milliseconds 40
    }
    return $buf.ToString()
}
try {
    $serial.Open()
    # One empty line only; never attempts username/password or boot commands.
    $serial.Write("`r")
    $hello = Read-Until 'ubuntu@kria:[^\r\n]*\$\s*$' 3
    $report.handshake=$hello
    if ($hello -notmatch 'ubuntu@kria:[^\r\n]*\$\s*$' -or $hello -match '(?i)password:|login:|ZynqMP>') { throw 'Expected logged-in Linux shell not confirmed; no diagnostic commands sent' }
    foreach ($job in $jobs) {
        $tag = 'A10_' + [Guid]::NewGuid().ToString('N')
        $wire = 'printf ''\n' + $tag + '_BEGIN\n''; ( ' + $job.command + ' ); a10_rc=$?; printf ''\n' + $tag + '_END:%s\n'' "$a10_rc"'
        $clock = [System.Diagnostics.Stopwatch]::StartNew()
        $serial.Write($wire + "`r")
        $deadline = if ($Phase -eq 'dt_snapshot') { 25 } elseif ($Phase -eq 'isolated_assets') { 12 } else { 6 }
        $raw = Read-Until ('(?m)^'+$tag+'_END:(\d+)\r?$') $deadline
        $m = [regex]::Match($raw,'(?m)^'+$tag+'_END:(\d+)\r?$')
        $report.records += [ordered]@{name=$job.name;command=$job.command;raw=$raw;elapsed_s=$clock.Elapsed.TotalSeconds;completion_marker=$m.Success;exit_code=$(if($m.Success){[int]$m.Groups[1].Value}else{$null});exit_scope='last command in diagnostic subshell; individual failures retained in raw output'}
        if (-not $m.Success) { throw 'Read deadline exceeded; no retry or interrupt sent' }
        # No further operations after a conservative high-temperature reading.
        if ($job.name -in @('health','sensors')) {
            $temps=[regex]::Matches($raw,'(?:thermal_zone\d+/temp|hwmon\d+/temp\d+_input):\s*(\d+)')
            foreach ($t in $temps) { if ([int]$t.Groups[1].Value -ge 60000) { throw 'Conservative 60 C stop threshold reached; no further commands' } }
        }
    }
    $report.status='COLLECTED_REVIEW_REQUIRED'
} catch {
    $report.status='STOPPED'
    $report.error=$_.Exception.Message
} finally {
    if ($serial.IsOpen) { $serial.Close() }
    $serial.Dispose()
    $report.closed=$true
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $OutputPath -Encoding utf8
}
$report | ConvertTo-Json -Depth 8
if ($report.status -eq 'STOPPED') { exit 2 }
