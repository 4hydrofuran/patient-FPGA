# B3 构建与验证入口：显式执行 native、CSim、C 综合、Cosim 或 XO 打包。
# 兼容环境仅作用于本次进程，结束后恢复；不会更改 Vitis 安装目录。
[CmdletBinding()]
param(
    [ValidateSet('native','baseline','csim','synth','cosim','package','all')]
    [string]$Target = 'all',
    [string]$VitisRoot = 'D:\2026.1\2026.1\Vitis',
    [string]$MingwRoot = 'D:\mingw64\bin',
    [string]$WorkDir = 'build\hls'
)

# 所有相对路径均以脚本所在的 B3 目录为基准。
$ErrorActionPreference = 'Stop'
$b3Root = $PSScriptRoot
$vitisRun = Join-Path $VitisRoot 'bin\vitis-run.bat'
$vitisCompile = Join-Path $VitisRoot 'bin\v++.bat'
$gcc = Join-Path $MingwRoot 'g++.exe'
$busybox = Join-Path $MingwRoot 'busybox.exe'
$installRoot = Split-Path $VitisRoot -Parent
$environmentNames = @('XILINX_LOCAL_USER_DATA','XILINX_TCLSTORE_USERAREA','CPATH','MAKEFLAGS','RDI_PREPEND_PATH','PATH')
$savedEnvironment = @{}
foreach ($environmentName in $environmentNames) {
    $savedEnvironment[$environmentName] = [Environment]::GetEnvironmentVariable($environmentName, 'Process')
}

# 命令日志和输入哈希绑定该轮源码，不仅依赖后来可能过期的报告。
function Invoke-B3Step {
    param([string]$Step, [string]$Executable, [string[]]$Arguments)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        throw "Tool not found: $Executable"
    }
    $logFile = Join-Path $b3Root "logs\$Step.console.log"
    Write-Host "B3 $Step : $Executable $($Arguments -join ' ')"
    & $Executable @Arguments 2>&1 | Tee-Object -FilePath $logFile
    $resultCode = $LASTEXITCODE
    if ($resultCode -ne 0) { throw "$Step failed with exit code $resultCode; see $logFile" }
    $inputs = @{}
    foreach ($relative in @('src\w4a8_linear_v1.cpp','src\w4a8_linear_v1.hpp','tb\tb_w4a8_linear_v1.cpp','tb\golden_w4a8.hpp','hls_config.cfg')) {
        $inputs[$relative.Replace('\','/')] = (Get-FileHash -LiteralPath (Join-Path $b3Root $relative) -Algorithm SHA256).Hash
    }
    if ($Step.StartsWith('baseline')) {
        foreach ($relative in @('baseline\b2\src\w4a8_linear_v1.cpp','baseline\b2\src\w4a8_linear_v1.hpp','tb\compare_b2.cpp')) {
            $inputs[$relative.Replace('\','/')] = (Get-FileHash -LiteralPath (Join-Path $b3Root $relative) -Algorithm SHA256).Hash
        }
    }
    # 这是工具运行产生的机械验证记录，手写状态说明仍保存在 reports 文档。
    [ordered]@{stage=$Step;exit_code=$resultCode;finished_at_utc=[DateTime]::UtcNow.ToString('o');tool=$Executable;arguments=$Arguments;input_sha256=$inputs} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $b3Root "reports\$Step.receipt.json") -Encoding utf8
}

# 任何目标开始前先准备本项目的输出目录，原 B2 不参与写入。
New-Item -ItemType Directory -Force -Path (Join-Path $b3Root 'logs'),(Join-Path $b3Root 'reports'),(Join-Path $b3Root 'build\native'),(Join-Path $b3Root 'vectors\generated') | Out-Null
Push-Location $b3Root
try {
    # 继续使用已验证的英文 Vivado 用户目录与 MSYS 兼容工具。
    $driveRoot = [System.IO.Path]::GetPathRoot($b3Root)
    $userData = Join-Path $driveRoot 'codex-vivado-userdata'
    $tclStore = Join-Path $driveRoot 'codex-vivado-tclstore'
    $shimRoot = Join-Path $driveRoot 'codex-vitis-shims'
    New-Item -ItemType Directory -Force -Path $userData,$tclStore,$shimRoot | Out-Null
    $env:XILINX_LOCAL_USER_DATA = $userData.Replace('\','/')
    $env:XILINX_TCLSTORE_USERAREA = $tclStore.Replace('\','/')
    $env:CPATH = (Join-Path $installRoot 'win64\tools\auto_cc\include').Replace('\','/')
    if ($Target -ne 'native' -and $Target -ne 'baseline') {
        if (-not (Test-Path -LiteralPath $busybox)) { throw "BusyBox not found: $busybox" }
        foreach ($toolName in @('mkdir','rm','cp','mv','grep','head','uname')) {
            $shimPath = Join-Path $shimRoot "$toolName.exe"
            if (-not (Test-Path -LiteralPath $shimPath)) { Copy-Item -LiteralPath $busybox -Destination $shimPath }
        }
    }
    $posixShim = "/cygdrive/$($driveRoot.Substring(0,1).ToLowerInvariant())/codex-vitis-shims"
    $env:MAKEFLAGS = "MKDIR=$posixShim/mkdir.exe RM=$posixShim/rm.exe CP=$posixShim/cp.exe MV=$posixShim/mv.exe RUNNING_LINUX=Windows_NT"
    $env:RDI_PREPEND_PATH = "$shimRoot;$MingwRoot"
    $env:PATH = "$shimRoot;$MingwRoot;$env:PATH"

    # 本地编译只检查普通 C++ 与 golden；日志明确区分该步骤和 Vitis Csim。
    if ($Target -eq 'native' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'native_compile' -Executable $gcc -Arguments @('-std=c++14','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unknown-pragmas','src\w4a8_linear_v1.cpp','tb\tb_w4a8_linear_v1.cpp','-o','build\native\b3_test.exe')
        Invoke-B3Step -Step 'native_test' -Executable (Join-Path $b3Root 'build\native\b3_test.exe') -Arguments @('--suite','full','--dump','vectors/generated')
        $vectorHashes = @{}
        Get-ChildItem -LiteralPath (Join-Path $b3Root 'vectors\generated') -File | Where-Object { $_.Name -ne 'manifest.json' } | ForEach-Object {
            $vectorHashes[$_.Name] = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        }
        # 输入文件 hash 是向量生成后的机械产物，不靠随机 seed 单独替代真实字节。
        [ordered]@{source='synthetic';generator='tb/tb_w4a8_linear_v1.cpp';endianness='little';files_sha256=$vectorHashes} |
            ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $b3Root 'vectors\generated\manifest.json') -Encoding utf8
    }

    # 同一批实际向量在原 B2 上复跑，只验证数值兼容性，不把 native 时间称为硬件性能。
    if ($Target -eq 'baseline' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'baseline_compile' -Executable $gcc -Arguments @('-std=c++14','-O2','-ffp-contract=off','-Wno-unknown-pragmas','baseline\b2\src\w4a8_linear_v1.cpp','tb\compare_b2.cpp','-o','build\native\b2_compat.exe')
        Invoke-B3Step -Step 'baseline_test' -Executable (Join-Path $b3Root 'build\native\b2_compat.exe') -Arguments @()
    }

    # Vitis C 仿真运行 full，含四种真实 MLP 尺寸的合成输入。
    if ($Target -eq 'csim' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'csim' -Executable $vitisRun -Arguments @('--mode','hls','--csim','--config','hls_config.cfg','--work_dir',$WorkDir)
    }

    # 本机 --help 确认 C 综合入口为 v++ --compile --mode hls。
    if ($Target -eq 'synth' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'synth' -Executable $vitisCompile -Arguments @('--compile','--mode','hls','--config','hls_config.cfg','--work_dir',$WorkDir)
    }

    # 联合仿真和打包必须复用上述同一个 component 的综合结果。
    if ($Target -eq 'cosim' -or $Target -eq 'package' -or $Target -eq 'all') {
        if (-not (Test-Path -LiteralPath (Join-Path $b3Root "$WorkDir\hls\syn"))) {
            throw 'Synthesis cache is missing; run -Target synth first.'
        }
    }
    if ($Target -eq 'cosim' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'cosim' -Executable $vitisRun -Arguments @('--mode','hls','--cosim','--config','hls_config.cfg','--work_dir',$WorkDir)
    }
    if ($Target -eq 'package' -or $Target -eq 'all') {
        Invoke-B3Step -Step 'package' -Executable $vitisRun -Arguments @('--mode','hls','--package','--config','hls_config.cfg','--work_dir',$WorkDir)
    }
} finally {
    # 即使工具失败，也恢复调用者进程的原环境和当前目录。
    Pop-Location
    foreach ($environmentName in $environmentNames) {
        [Environment]::SetEnvironmentVariable($environmentName, $savedEnvironment[$environmentName], 'Process')
    }
}
