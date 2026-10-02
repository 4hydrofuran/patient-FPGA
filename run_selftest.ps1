# B01一键电脑数值自测：不下载模型、不调用Vitis、不访问板卡。
[CmdletBinding()]
param([string]$MingwRoot='D:\mingw64\bin')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$savedPath=$env:PATH
$savedLocation=Get-Location
$steps=@()
Set-Location -LiteralPath $root
try {
    $env:PATH="$MingwRoot;$env:PATH"
    New-Item -ItemType Directory -Force -Path 'logs/b01','reports/b01' | Out-Null
    foreach($probe in @(@{name='public_c11';compiler='gcc.exe';standard='c11';file='tests/interface/header_probe.c'},
                       @{name='public_cpp17';compiler='g++.exe';standard='c++17';file='tests/interface/header_probe.cpp'})) {
        & (Join-Path $MingwRoot $probe.compiler) "-std=$($probe.standard)" -Wall -Wextra -pedantic -fsyntax-only $probe.file 2>&1 |
            Tee-Object -FilePath "logs/b01/$($probe.name).log" | Out-Host
        $code=$LASTEXITCODE
        $steps+=@{step=$probe.name;exit_code=$code}
        if($code -ne 0) { throw "$($probe.name) failed: $code" }
    }
    foreach($target in @('reference','native','baseline')) {
        & (Join-Path $root 'run_b01.ps1') -Target $target -MingwRoot $MingwRoot
        $steps+=@{step=$target;exit_code=0}
    }
    & (Join-Path $root 'run_real_reference.ps1') -MingwRoot $MingwRoot
    $steps+=@{step='real_tensors';exit_code=0}
    Write-Host 'B01 SELFTEST PASS: headers, scalar quantization, all synthetic shapes, B2 replay, real-weight PC replay.'
} finally {
    [ordered]@{stage='B01';execution_kind='PC_NATIVE';steps=$steps;
        wrapper_sha256=(Get-FileHash -LiteralPath 'run_selftest.ps1' -Algorithm SHA256).Hash;
        component_receipts='reports/b01/*.receipt.json';finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath 'reports/b01/selftest.receipt.json' -Encoding utf8
    $env:PATH=$savedPath
    Set-Location -LiteralPath $savedLocation.Path
}
