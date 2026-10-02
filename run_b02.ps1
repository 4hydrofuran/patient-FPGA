# B02单项激活复用候选与B01冻结消融；每个执行域均记录真实退出码。
[CmdletBinding()]
param([ValidateSet('native','csim','synth','cosim','all')][string]$Target='native',
      [string]$VitisRoot='D:\2026.1\2026.1\Vitis',[string]$MingwRoot='D:\mingw64\bin')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$savedLocation=Get-Location
$environmentNames=@('PATH','CPATH','MAKEFLAGS','XILINX_LOCAL_USER_DATA','XILINX_TCLSTORE_USERAREA','RDI_PREPEND_PATH')
$saved=@{}
foreach($name in $environmentNames) { $saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process') }
function Invoke-Step {
    param([string]$Name,[string]$Executable,[string[]]$Arguments)
    $fingerprints=[ordered]@{}
    foreach($p in @('src/w4a8_linear_v1.cpp','src/w4a8_linear_v1.hpp',
        'baseline/b01/src/w4a8_linear_v1.cpp','baseline/b01/src/w4a8_linear_v1.hpp',
        'tb/tb_w4a8_linear_v1.cpp','tb/golden_w4a8.hpp',
        'reference/quantization.hpp','host/linear_validation.hpp',
        'tests/support/quantization_checks.hpp','tests/numerical/model_tensor_replay.cpp',
        'hls_b02_cache_x.cfg','hls_b02_baseline.cfg','run_b02.ps1')) {
        $fingerprints[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
    }
    $code=-1
    try {
        Write-Host "B02 $Name : $Executable $($Arguments -join ' ')"
        $previous=$ErrorActionPreference;$ErrorActionPreference='Continue'
        & $Executable @Arguments 2>&1 | Tee-Object -FilePath "logs/b02/$Name.log" | Out-Host
        $code=$LASTEXITCODE;$ErrorActionPreference=$previous
    } finally {
        [ordered]@{stage='B02';variant='CACHE_X';step=$Name;executable=$Executable;
            arguments=$Arguments;exit_code=$code;input_sha256=$fingerprints;
            finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath "reports/b02/$Name.receipt.json" -Encoding utf8
    }
    if($code -ne 0) { throw "$Name failed: $code" }
}
function Assert-VectorIdentity {
    param([string]$Original,[string]$Candidate,[string]$Receipt)
    $reference=(Get-Content -LiteralPath "$Original/manifest.json" -Encoding utf8 | ConvertFrom-Json).files_sha256
    $hashes=[ordered]@{};$mismatches=@()
    foreach($entry in $reference.PSObject.Properties) {
        $p=Join-Path $Candidate $entry.Name
        if(!(Test-Path -LiteralPath $p)) { $mismatches+=$entry.Name;continue }
        $hash=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
        $hashes[$entry.Name]=$hash
        if($hash -ne $entry.Value) { $mismatches+=$entry.Name }
    }
    [ordered]@{stage='B02';check='byte-identical B01 raw inputs, expected and observed';
        original=$Original;candidate=$Candidate;file_count=($reference.PSObject.Properties | Measure-Object).Count;
        mismatches=$mismatches;candidate_sha256=$hashes;
        status=if($mismatches.Count -eq 0){'PASS'}else{'FAIL'}} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "reports/b02/$Receipt.receipt.json" -Encoding utf8
    if($mismatches.Count -ne 0) { throw "B02 vectors differ from B01: $($mismatches -join ', ')" }
}
Set-Location -LiteralPath $root
try {
    New-Item -ItemType Directory -Force -Path 'build/b02_cache_x','logs/b02','reports/b02','vectors/b02_cache_x','vectors/b02_real' | Out-Null
    $b01=(Get-Content -LiteralPath 'reports/b01/synth.receipt.json' -Encoding utf8 | ConvertFrom-Json).input_sha256
    foreach($name in @('w4a8_linear_v1.cpp','w4a8_linear_v1.hpp')) {
        $p="baseline/b01/src/$name"
        if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $b01."src/$name") { throw "B01 frozen source changed: $p" }
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
        Invoke-Step 'baseline_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas','baseline/b01/src/w4a8_linear_v1.cpp','tb/tb_w4a8_linear_v1.cpp','-o','build/b02_cache_x/b01_baseline.exe')
        Invoke-Step 'baseline_test' (Join-Path $root 'build/b02_cache_x/b01_baseline.exe') @('--suite','full')
        Invoke-Step 'native_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','-DB02_CACHE_X','-Wall','-Wextra','-Wno-unknown-pragmas','src/w4a8_linear_v1.cpp','tb/tb_w4a8_linear_v1.cpp','-o','build/b02_cache_x/numerical_test.exe')
        Invoke-Step 'native_test' (Join-Path $root 'build/b02_cache_x/numerical_test.exe') @('--suite','full','--dump','vectors/b02_cache_x')
        Assert-VectorIdentity 'vectors/b01' 'vectors/b02_cache_x' 'synthetic_identity'
        Invoke-Step 'real_compile' $gpp @('-std=c++17','-O2','-ffp-contract=off','-DB02_CACHE_X','-Wno-unknown-pragmas','src/w4a8_linear_v1.cpp','tests/numerical/model_tensor_replay.cpp','-o','build/b02_cache_x/model_tensor_replay.exe')
        Invoke-Step 'real_test' (Join-Path $root 'build/b02_cache_x/model_tensor_replay.exe') @()
        Assert-VectorIdentity 'vectors/b01_real' 'vectors/b02_real' 'real_identity'
    }
    $run=Join-Path $VitisRoot 'bin/vitis-run.bat'
    if($Target -in @('csim','all')) { Invoke-Step 'csim' $run @('--mode','hls','--csim','--config','hls_b02_cache_x.cfg','--work_dir','build/b02_cache_x_hls') }
    if($Target -in @('synth','all')) { Invoke-Step 'synth' (Join-Path $VitisRoot 'bin/v++.bat') @('--compile','--mode','hls','--config','hls_b02_cache_x.cfg','--work_dir','build/b02_cache_x_hls') }
    if($Target -in @('cosim','all')) { Invoke-Step 'cosim' $run @('--mode','hls','--cosim','--config','hls_b02_cache_x.cfg','--work_dir','build/b02_cache_x_hls') }
} finally {
    foreach($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
    Set-Location -LiteralPath $savedLocation.Path
}
