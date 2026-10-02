# B01按域执行，失败也保存退出码和输入指纹；不执行上板或平台链接。
[CmdletBinding()]
param([ValidateSet('native','reference','baseline','csim','baseline_csim','synth','cosim','all')][string]$Target='native',
      [string]$VitisRoot='D:\2026.1\2026.1\Vitis',[string]$MingwRoot='D:\mingw64\bin')
$ErrorActionPreference='Stop'
if($PSVersionTable.PSEdition -eq 'Desktop') { Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility') -Force }
$root=$PSScriptRoot
$savedLocation=Get-Location
$environmentNames=@('PATH','CPATH','MAKEFLAGS','XILINX_LOCAL_USER_DATA','XILINX_TCLSTORE_USERAREA','RDI_PREPEND_PATH')
$saved=@{}
foreach($name in $environmentNames) { $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
function Invoke-Step {
    param([string]$Name,[string]$Executable,[string[]]$Arguments)
    $inputs=[ordered]@{}
    foreach($p in @('src/w4a8_linear_v1.cpp','src/w4a8_linear_v1.hpp','baseline/b2/src/w4a8_linear_v1.cpp','baseline/b2/src/w4a8_linear_v1.hpp',
        'tb/tb_w4a8_linear_v1.cpp','tb/golden_w4a8.hpp','tb/compare_b2.cpp','host/linear_validation.hpp','reference/quantization.hpp',
        'tests/support/quantization_checks.hpp','hls_b01.cfg','hls_b01_baseline.cfg','run_b01.ps1')) {
        $inputs[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
    }
    $code=-1
    try {
        Write-Host "B01 $Name : $Executable $($Arguments -join ' ')"
        # 原生程序stderr日志保留；以实际退出码判定，不让PowerShell警告流提前中断记录。
        $previous=$ErrorActionPreference;$ErrorActionPreference='Continue'
        & $Executable @Arguments 2>&1 | Tee-Object -FilePath "logs/b01/$Name.log" | Out-Host
        $code=$LASTEXITCODE;$ErrorActionPreference=$previous
    } finally {
        [ordered]@{stage='B01';name=$Name;executable=$Executable;arguments=$Arguments;exit_code=$code;input_sha256=$inputs;finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "reports/b01/$Name.receipt.json" -Encoding utf8
    }
    if($code -ne 0) { throw "$Name failed: $code" }
}
Set-Location -LiteralPath $root
try {
    New-Item -ItemType Directory -Force -Path 'build/b01_native','logs/b01','reports/b01','vectors/b01' | Out-Null
    $drive=[IO.Path]::GetPathRoot($root)
    $shim=Join-Path $drive 'codex-vitis-shims'
    $env:PATH="$shim;$MingwRoot;$env:PATH"
    $env:CPATH=(Join-Path (Split-Path $VitisRoot -Parent) 'win64/tools/auto_cc/include').Replace('\','/')
    $env:XILINX_LOCAL_USER_DATA=(Join-Path $drive 'codex-vivado-userdata').Replace('\','/')
    $env:XILINX_TCLSTORE_USERAREA=(Join-Path $drive 'codex-vivado-tclstore').Replace('\','/')
    $posix="/cygdrive/$($drive.Substring(0,1).ToLowerInvariant())/codex-vitis-shims"
    $env:MAKEFLAGS="MKDIR=$posix/mkdir.exe RM=$posix/rm.exe CP=$posix/cp.exe MV=$posix/mv.exe RUNNING_LINUX=Windows_NT"
    $env:RDI_PREPEND_PATH="$shim;$MingwRoot"
    $gpp=Join-Path $MingwRoot 'g++.exe'
    if($Target -in @('native','all')) {
        Invoke-Step 'native_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unknown-pragmas','src/w4a8_linear_v1.cpp','tb/tb_w4a8_linear_v1.cpp','-o','build/b01_native/numerical_test.exe')
        Invoke-Step 'native_test' (Join-Path $root 'build/b01_native/numerical_test.exe') @('--suite','full','--dump','vectors/b01')
        $files=[ordered]@{}
        foreach($p in Get-ChildItem -LiteralPath 'vectors/b01' -File | Where-Object Name -ne 'manifest.json' | Sort-Object Name) { $files[$p.Name]=(Get-FileHash -LiteralPath $p.FullName -Algorithm SHA256).Hash }
        [ordered]@{stage='B01';source='synthetic';seed_rule='0x20261002 + shape_index*256 + T';files_sha256=$files} | ConvertTo-Json -Depth 5 | Set-Content 'vectors/b01/manifest.json' -Encoding utf8
    }
    if($Target -in @('reference','all')) {
        Invoke-Step 'reference_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','tests/numerical/quantization_reference.cpp','-o','build/b01_native/quantization_reference.exe')
        Invoke-Step 'reference_test' (Join-Path $root 'build/b01_native/quantization_reference.exe') @()
    }
    if($Target -in @('baseline','all')) {
        Invoke-Step 'baseline_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas','baseline/b2/src/w4a8_linear_v1.cpp','tb/compare_b2.cpp','-o','build/b01_native/baseline_test.exe')
        Invoke-Step 'baseline_test' (Join-Path $root 'build/b01_native/baseline_test.exe') @()
    }
    $run=Join-Path $VitisRoot 'bin/vitis-run.bat'
    if($Target -in @('csim','all')) { Invoke-Step 'csim' $run @('--mode','hls','--csim','--config','hls_b01.cfg','--work_dir','build/b01_hls') }
    if($Target -in @('baseline_csim','all')) { Invoke-Step 'baseline_csim' $run @('--mode','hls','--csim','--config','hls_b01_baseline.cfg','--work_dir','build/b01_baseline_hls') }
    if($Target -in @('synth','all')) { Invoke-Step 'synth' (Join-Path $VitisRoot 'bin/v++.bat') @('--compile','--mode','hls','--config','hls_b01.cfg','--work_dir','build/b01_hls') }
    if($Target -in @('cosim','all')) { Invoke-Step 'cosim' $run @('--mode','hls','--cosim','--config','hls_b01.cfg','--work_dir','build/b01_hls') }
} finally {
    foreach($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
    Set-Location -LiteralPath $savedLocation.Path
}
