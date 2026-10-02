# 本机XSIM链接兼容措施；只操作当前工程生成物，不修改Vivado安装目录。
[CmdletBinding()]
param([string]$WorkDir='build/b01_hls',[string]$MingwRoot='D:\mingw64\bin',
      [string]$VivadoRoot='D:\2026.1\2026.1\Vivado')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$sim=Join-Path $root "$WorkDir/hls/sim/verilog"
$objectDir=Join-Path $sim 'xsim.dir/w4a8_linear_v1/obj'
$objects=@(Get-ChildItem -LiteralPath $objectDir -Filter '*.win64.obj' | Sort-Object Name)
$generated=@(Get-ChildItem -LiteralPath $objectDir -Filter 'xsim_*.c')
if($objects.Count -eq 0 -or $generated.Count -eq 0 -or $objects.Count -lt $generated.Count) {
    throw 'Generated C/object set is incomplete. First run generated xelab command with -mt off -v 1 and CPATH unset; preserve its log.'
}
# Xelab可以删除已编译的中间C文件；保留C对应object必须有效，编号仍必须连续。
$indices=@($objects | ForEach-Object {
    if($_.Name -notmatch '^xsim_(\d+)\.win64\.obj$' -or $_.Length -eq 0) { throw "Unexpected object: $($_.Name)" }
    [int]$Matches[1]
} | Sort-Object)
if($indices[0] -ne 0 -or $indices[-1] -ne $objects.Count-1) { throw 'Generated object numbering has gaps.' }
foreach($source in $generated) {
    $object=Join-Path $objectDir ($source.BaseName+'.win64.obj')
    if(!(Test-Path -LiteralPath $object) -or (Get-Item -LiteralPath $object).LastWriteTimeUtc -lt $source.LastWriteTimeUtc) {
        throw "Missing or stale object: $object"
    }
}
$savedPath=$env:PATH
$env:PATH="$MingwRoot;$env:PATH"
try {
    New-Item -ItemType Directory -Force -Path "$root/logs/b01","$root/reports/b01" | Out-Null
    $arguments=@('-Wa,-W','-O','-Wl,--stack,104857600,--image-base,0x400000','-o',
        (Join-Path $sim 'xsim.dir/w4a8_linear_v1/xsimk.exe'))+@($objects.FullName)+@("-L$VivadoRoot/lib/win64.o",'-lxv_simulator_kernel')
    & (Join-Path $MingwRoot 'g++.exe') @arguments 2>&1 |
        Tee-Object -FilePath "$root/logs/b01/xsim_relink.log" | Out-Host
    $code=$LASTEXITCODE
    $hashes=[ordered]@{}
    foreach($p in $objects) { $hashes[$p.Name]=(Get-FileHash -LiteralPath $p.FullName -Algorithm SHA256).Hash }
    [ordered]@{step='XSIM snapshot relink only';exit_code=$code;arguments=$arguments;object_sha256=$hashes;
        script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash;
        note='Successful linking alone is not RTL verification. Run generated XSIM batch, then Vitis cosim.pc.exe to compare actual RTL outputs.'} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$root/reports/b01/xsim_relink.receipt.json" -Encoding utf8
    if($code -ne 0) { throw "XSIM relink failed: $code" }
} finally { $env:PATH=$savedPath }
