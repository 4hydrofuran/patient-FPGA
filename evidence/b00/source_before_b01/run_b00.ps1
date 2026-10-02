# B00 独立电脑检查；不执行 Vitis、平台链接或实板任务。
[CmdletBinding()]
param([string]$MingwRoot = 'D:\mingw64\bin')
$ErrorActionPreference = 'Stop'
# Codex 可能传入 PowerShell 7 的模块搜索路径；Windows PowerShell 显式加载自己的工具模块。
if ($PSVersionTable.PSEdition -eq 'Desktop') {
    Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -Force -ErrorAction Stop
}
$savedPath = $env:PATH
$savedLocation = Get-Location
$env:PATH = "$MingwRoot;$env:PATH"
Set-Location -LiteralPath $PSScriptRoot
New-Item -ItemType Directory -Force -Path 'logs','reports','build\native' | Out-Null
$steps = @()
function Invoke-Check {
    param([string]$Name, [string]$Exe, [string[]]$Arguments)
    & $Exe @Arguments 2>&1 | Tee-Object -FilePath "logs\b00_$Name.log" | Out-Host
    $code = $LASTEXITCODE
    $script:steps += [ordered]@{name=$Name; executable=$Exe; arguments=$Arguments; exit_code=$code}
    if ($code -ne 0) { throw "$Name failed: $code" }
}
try {
    # 声明检查只检查语法和类型，不将其写作共享库链接通过。
    Invoke-Check 'public_header_c11' (Join-Path $MingwRoot 'gcc.exe') @('-std=c11','-Wall','-Wextra','-Werror','-pedantic','-fsyntax-only','tests/interface/header_probe.c')
    Invoke-Check 'public_header_cpp17' (Join-Path $MingwRoot 'g++.exe') @('-std=c++17','-Wall','-Wextra','-Werror','-pedantic','-fsyntax-only','tests/interface/header_probe.cpp')
    # 公共字节样例和错误语义回放明确标为 PC。
    Invoke-Check 'fixture_compile' (Join-Path $MingwRoot 'g++.exe') @('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas','src/w4a8_linear_v1.cpp','tests/numerical/fixture_replay.cpp','-o','build/native/fixture_replay.exe')
    Invoke-Check 'fixture_replay' (Join-Path $PSScriptRoot 'build/native/fixture_replay.exe') @()
    # 在新副本运行继承回归，原 B3 报告和向量保持不变。
    & (Join-Path $PSScriptRoot 'run_b3.ps1') -Target native -MingwRoot $MingwRoot
    $steps += [ordered]@{name='inherited_native'; executable='run_b3.ps1'; arguments=@('-Target','native'); exit_code=0}
    & (Join-Path $PSScriptRoot 'run_b3.ps1') -Target baseline -MingwRoot $MingwRoot
    $steps += [ordered]@{name='inherited_b2_comparison'; executable='run_b3.ps1'; arguments=@('-Target','baseline'); exit_code=0}
} finally {
    # 成败均保存已执行步骤；源码与参考输入指纹绑定本次检查。
    $inputs = [ordered]@{}
    foreach($p in @('src/w4a8_linear_v1.cpp','src/w4a8_linear_v1.hpp','tb/tb_w4a8_linear_v1.cpp','tb/golden_w4a8.hpp','contracts/sp_linear_v1.h','tests/interface/header_probe.c','tests/interface/header_probe.cpp','tests/numerical/fixture_replay.cpp','run_b00.ps1')) {
        $inputs[$p] = (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
    }
    [ordered]@{stage='B00';execution_kind='PC_NATIVE';steps=$steps;input_sha256=$inputs;finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath 'reports/b00_checks.receipt.json' -Encoding utf8
    $env:PATH = $savedPath
    Set-Location -LiteralPath $savedLocation.Path
}
