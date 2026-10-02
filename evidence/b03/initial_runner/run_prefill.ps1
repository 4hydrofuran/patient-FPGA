# B03独立构建与分域验证；每次尝试保存源码指纹和日志，失败记录不覆盖。
[CmdletBinding()]
param(
    [ValidateSet('baseline','reuse','double')][string]$Variant='double',
    [ValidateSet('native','csim','synth','cosim','all')][string]$Target='native',
    [string]$VitisRoot='D:\2026.1\2026.1\Vitis',
    [string]$MingwRoot='D:\mingw64\bin'
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$savedLocation=Get-Location
$environmentNames=@('PATH','CPATH','MAKEFLAGS','XILINX_LOCAL_USER_DATA','XILINX_TCLSTORE_USERAREA','RDI_PREPEND_PATH')
$saved=@{}
foreach($name in $environmentNames) { $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')
$receiptDirectory="reports/b03/$Variant/$stamp"
$logDirectory="logs/b03/$Variant/$stamp"
$buildDirectory="build/b03_$Variant"
$vectorDirectory="vectors/b03_$Variant"
$realDirectory="vectors/b03_${Variant}_real"
$config="hls_prefill_$Variant.cfg"
$source=if($Variant -eq 'baseline'){'baseline/b02/src/w4a8_linear_v1.cpp'}else{'src/w4a8_prefill_v1.cpp'}
$defines=@('-DB02_CACHE_X','-DB02_AXI_X128','-DB03_TEST')
if($Variant -ne 'baseline') { $defines+='-DB03_REUSE' }
if($Variant -eq 'double') { $defines+='-DB03_DOUBLE_BUFFER' }
function Invoke-Step {
    param([string]$Name,[string]$Executable,[string[]]$Arguments)
    $fingerprints=[ordered]@{}
    foreach($path in @($source,'src/w4a8_linear_v1.hpp','baseline/b02/src/w4a8_linear_v1.hpp',
        'tb/tb_prefill_v1.cpp','tb/golden_w4a8.hpp','host/linear_validation.hpp',
        'reference/quantization.hpp','tests/support/quantization_checks.hpp',
        'tests/numerical/prefill_tensor_replay.cpp',$config,'run_prefill.ps1')) {
        $fingerprints[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
    $code=-1
    $watch=[Diagnostics.Stopwatch]::StartNew()
    $log="$logDirectory/$Name.log"
    Write-Host "B03 $Variant $Name started; log: $log"
    try {
        $previous=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        & $Executable @Arguments *> $log
        $code=$LASTEXITCODE
        $ErrorActionPreference=$previous
    } finally {
        $watch.Stop()
        [ordered]@{stage='B03';variant=$Variant;step=$Name;executable=$Executable;
            arguments=$Arguments;exit_code=$code;elapsed_seconds=$watch.Elapsed.TotalSeconds;
            log=$log;input_sha256=$fingerprints;finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "$receiptDirectory/$Name.receipt.json" -Encoding utf8
    }
    Write-Host "B03 $Variant $Name exited $code after $([math]::Round($watch.Elapsed.TotalSeconds,1))s"
    if($code -ne 0) { Get-Content -LiteralPath $log -Tail 25 | Out-Host; throw "$Name failed: $code" }
    if($Name -in @('native_test','real_test')) {
        Get-Content -LiteralPath $log | Select-String 'PASS suite=|real-tensor PASS' | ForEach-Object { Write-Host $_.Line }
    }
}
Set-Location -LiteralPath $root
try {
    foreach($path in @($receiptDirectory,$logDirectory,$buildDirectory,$vectorDirectory,$realDirectory)) {
        New-Item -ItemType Directory -Force -Path $path | Out-Null
    }
    $frozen=(Get-Content -LiteralPath 'baseline/b02/source_manifest.json' -Raw | ConvertFrom-Json).files_sha256
    foreach($entry in $frozen.PSObject.Properties) {
        if((Get-FileHash -LiteralPath $entry.Name).Hash -ne $entry.Value) { throw "B02 preservation failed: $($entry.Name)" }
    }
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
        Invoke-Step 'native_compile' $gpp (@('-std=c++17','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unknown-pragmas')+$defines+@($source,'tb/tb_prefill_v1.cpp','-o',"$buildDirectory/numerical_test.exe"))
        Invoke-Step 'native_test' (Join-Path $root "$buildDirectory/numerical_test.exe") @('--suite','full','--dump',$vectorDirectory)
        Invoke-Step 'real_compile' $gpp (@('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas')+$defines+@($source,'tests/numerical/prefill_tensor_replay.cpp','-o',"$buildDirectory/model_tensor_replay.exe"))
        Invoke-Step 'real_test' (Join-Path $root "$buildDirectory/model_tensor_replay.exe") @($realDirectory)
    }
    $run=Join-Path $VitisRoot 'bin/vitis-run.bat'
    if($Target -in @('csim','all')) { Invoke-Step 'csim' $run @('--mode','hls','--csim','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
    if($Target -in @('synth','all')) { Invoke-Step 'synth' (Join-Path $VitisRoot 'bin/v++.bat') @('--compile','--mode','hls','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
    if($Target -in @('cosim','all')) { Invoke-Step 'cosim' $run @('--mode','hls','--cosim','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
} finally {
    foreach($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
    Set-Location -LiteralPath $savedLocation.Path
}
