# 仅处理本工程工具准备阶段卡住的Windows/Linux探测，不终止编译或RTL。
$ErrorActionPreference='Stop'
$project=Split-Path $PSScriptRoot -Parent
$all=@(Get-CimInstance Win32_Process)
foreach($probe in $all | Where-Object {$_.Name -eq 'sh.exe' -and $_.CommandLine -match 'uname \| grep -i Linux'}) {
    if(([DateTime]::Now-$probe.CreationDate).TotalSeconds -lt 120){continue}
    $make=$all | Where-Object {$_.ProcessId -eq $probe.ParentProcessId}
    $hls=$all | Where-Object {$_.ProcessId -eq $make.ParentProcessId}
    if(!$make -or !$hls -or $make.Name -ne 'mingw32-make.exe' -or $hls.Name -ne 'vitis_hls.exe' -or
       $hls.CommandLine.Replace('/','\') -notlike "*$project*" -or $make.CommandLine -notmatch 'cosim\.(tv|pc)\.mk'){continue}
    if($hls.CommandLine -notmatch 'hls_prefill_(baseline|reuse|double)_(\w+)\.cfg'){throw 'Owned configuration is ambiguous'}
    $variant=$Matches[1]
    $group=$Matches[2]
    $latest=Get-ChildItem -LiteralPath "$project/logs/b03/$variant" -Directory | Sort-Object Name -Descending | Select-Object -First 1
    $record="$project/reports/b03/$variant/$($latest.Name)/os_probe_interruption.json"
    $events=if(Test-Path -LiteralPath $record){@(Get-Content -LiteralPath $record -Raw | ConvertFrom-Json)}else{@()}
    $events+=,[ordered]@{status='TOOL_OS_PROBE_STALLED';action='Stop only confirmed Windows/Linux probe; no compilation or RTL skipped';
      at=[DateTimeOffset]::Now.ToString('o');pid=$probe.ProcessId;parent_pid=$make.ProcessId;
      command=$probe.CommandLine;config_group=$group;age_seconds=([DateTime]::Now-$probe.CreationDate).TotalSeconds;
      accepted_as_simulation=$false}
    ConvertTo-Json -InputObject $events -Depth 5 | Set-Content -LiteralPath $record -Encoding utf8
    Stop-Process -Id $probe.ProcessId -Force
    Write-Host "Stopped only confirmed stalled B03 OS probe: $variant/$group; record $record"
}

