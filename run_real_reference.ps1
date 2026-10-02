# B01两个真实权重张量的电脑验证，不执行下载或硬件任务。
[CmdletBinding()]
param([string]$MingwRoot='D:\mingw64\bin')
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$savedPath=$env:PATH
$savedLocation=Get-Location
$env:PATH="$MingwRoot;$env:PATH"
Set-Location -LiteralPath $root
try {
    New-Item -ItemType Directory -Force -Path 'vectors/b01_real','logs/b01','reports/b01','build/b01_native' | Out-Null
    $steps=@()
    $inputs=[ordered]@{}
    foreach($p in @('src/w4a8_linear_v1.cpp','src/w4a8_linear_v1.hpp','tb/golden_w4a8.hpp','reference/quantization.hpp','host/linear_validation.hpp','tests/numerical/model_tensor_replay.cpp','vectors/model_source/source_manifest.json','vectors/model_source/gate_proj.fp32.bin','vectors/model_source/down_proj.fp32.bin','run_real_reference.ps1')) {
        $inputs[$p]=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash
    }
    & (Join-Path $MingwRoot 'g++.exe') -std=c++17 -O2 -ffp-contract=off -Wno-unknown-pragmas src/w4a8_linear_v1.cpp tests/numerical/model_tensor_replay.cpp -o build/b01_native/model_tensor_replay.exe 2>&1 |
        Tee-Object -FilePath 'logs/b01/real_compile.log' | Out-Host
    $code=$LASTEXITCODE
    $steps += [ordered]@{step='compile';exit_code=$code}
    if($code -ne 0) { throw 'Real tensor compilation failed' }
    & (Join-Path $root 'build/b01_native/model_tensor_replay.exe') 2>&1 | Tee-Object -FilePath 'logs/b01/real_test.log' | Out-Host
    $code=$LASTEXITCODE
    $steps += [ordered]@{step='test';exit_code=$code}
    if($code -ne 0) { throw 'Real tensor numerical test failed' }
    $hashes=[ordered]@{}
    foreach($p in Get-ChildItem -LiteralPath 'vectors/b01_real' -File | Where-Object Name -ne 'manifest.json' | Sort-Object Name) { $hashes[$p.Name]=(Get-FileHash -LiteralPath $p.FullName -Algorithm SHA256).Hash }
    [ordered]@{weight_source='pinned_real_Qwen3.5_layer0_gate_and_down';activation_source='synthetic';files_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content 'vectors/b01_real/manifest.json' -Encoding utf8
} finally {
    [ordered]@{stage='B01';execution_kind='PC_NATIVE';steps=$steps;input_sha256=$inputs;finished_at_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 6 |
        Set-Content -LiteralPath 'reports/b01/real_tensors.receipt.json' -Encoding utf8
    $env:PATH=$savedPath
    Set-Location -LiteralPath $savedLocation.Path
}
