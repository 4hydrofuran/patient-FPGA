# 补交追溯：在独立构建目录重验冻结基线，旧收据与double候选均不覆盖。
[CmdletBinding()]
param([string]$VitisRoot='D:\2026.1\2026.1\Vitis',[string]$MingwRoot='D:\mingw64\bin')
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$location=Get-Location
$names=@('PATH','CPATH','MAKEFLAGS','XILINX_LOCAL_USER_DATA','XILINX_TCLSTORE_USERAREA','RDI_PREPEND_PATH')
$saved=@{}
foreach($name in $names){$saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$lock=[Threading.Mutex]::new($false,'Local\KV260_B03_Verification')
$owned=$false
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')
$out="evidence/b03/supplement/baseline_refresh/$stamp"
$work="build/b03_baseline_supplement_$stamp"
try {
 try{$owned=$lock.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owned=$true}
 if(!$owned){throw 'Another B03 verification is running'}
 Set-Location -LiteralPath $root
 New-Item -ItemType Directory -Force -Path $out | Out-Null
 $inputPaths=@('baseline/b02/src/w4a8_linear_v1.cpp','baseline/b02/src/w4a8_linear_v1.hpp','tb/tb_prefill_v1.cpp','tb/golden_w4a8.hpp','host/linear_validation.hpp','reference/quantization.hpp','tests/support/quantization_checks.hpp','hls_prefill_baseline.cfg','tools/refresh_prefill_baseline_provenance.ps1')
 $hashes=[ordered]@{}
 foreach($path in $inputPaths){$hashes[$path]=(Get-FileHash -LiteralPath $path).Hash.ToLowerInvariant()}
 $candidateBefore=(Get-FileHash -LiteralPath 'artifact/b03_candidate/w4a8_linear_v1.xo').Hash
 $drive=[IO.Path]::GetPathRoot($root)
 $shim=Join-Path $drive 'codex-vitis-shims'
 $env:PATH="$shim;$MingwRoot;$env:PATH"
 $env:CPATH=(Join-Path (Split-Path $VitisRoot -Parent) 'win64/tools/auto_cc/include').Replace('\','/')
 $env:XILINX_LOCAL_USER_DATA=(Join-Path $drive 'codex-vivado-userdata').Replace('\','/')
 $env:XILINX_TCLSTORE_USERAREA=(Join-Path $drive 'codex-vivado-tclstore').Replace('\','/')
 $posix="/cygdrive/$($drive.Substring(0,1).ToLowerInvariant())/codex-vitis-shims"
 $env:MAKEFLAGS="MKDIR=$posix/mkdir.exe RM=$posix/rm.exe CP=$posix/cp.exe MV=$posix/mv.exe RUNNING_LINUX=Windows_NT"
 $vivadoGccBin=Join-Path (Split-Path $VitisRoot -Parent) 'Vivado/tps/mingw/6.2.0/win64.o/nt/bin'
 $env:RDI_PREPEND_PATH="$shim;$vivadoGccBin;$MingwRoot"
 $steps=@(@{name='csim';tool='bin/vitis-run.bat';arguments=@('--mode','hls','--csim','--config','hls_prefill_baseline.cfg','--work_dir',$work)},@{name='synth';tool='bin/v++.bat';arguments=@('--compile','--mode','hls','--config','hls_prefill_baseline.cfg','--work_dir',$work)})
 foreach($step in $steps){
  $log="$out/$($step.name).log"
  $exe=Join-Path $VitisRoot $step.tool
  $watch=[Diagnostics.Stopwatch]::StartNew()
  & $exe @($step.arguments) *> $log
  $code=$LASTEXITCODE
  $watch.Stop()
  [ordered]@{status=$(if($code -eq 0){'PASS'}else{'FAIL'});scope='Fresh canonical frozen-baseline provenance; not recovery of missing old tb and not a new RTL run';step=$step.name;executable=$exe;arguments=$step.arguments;exit_code=$code;elapsed_seconds=$watch.Elapsed.TotalSeconds;input_sha256=$hashes;log=$log;log_sha256=(Get-FileHash -LiteralPath $log).Hash.ToLowerInvariant();finished_at_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$out/$($step.name).receipt.json" -Encoding utf8
  if($code -ne 0){throw "$($step.name) failed; preserved $log"}
  if($step.name -eq 'csim' -and (Get-Content -LiteralPath $log -Raw) -notmatch 'B03 PASS suite=full source=synthetic transactions=50'){throw 'Full50 Csim PASS absent'}
  Write-Host "PASS fresh baseline $($step.name)"
 }
 foreach($entry in $hashes.GetEnumerator()){if((Get-FileHash -LiteralPath $entry.Key).Hash.ToLowerInvariant() -ne $entry.Value){throw "Input changed: $($entry.Key)"}}
 if((Get-FileHash -LiteralPath 'artifact/b03_candidate/w4a8_linear_v1.xo').Hash -ne $candidateBefore){throw 'Frozen double XO changed'}
 Copy-Item -LiteralPath "$work/hls/syn/report/csynth.rpt" -Destination "$out/csynth.rpt"
 [ordered]@{status='PASS';directory=$out;fresh_csim_transactions=50;synthesis='PASS';original_history_retained=$true;double_candidate_unchanged=$true;input_sha256=$hashes} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath 'reports/b03/supplement_baseline_refresh.json' -Encoding utf8
 Write-Host "PASS baseline provenance refresh: $out"
}finally{
 if($owned){$lock.ReleaseMutex()}
 $lock.Dispose()
 foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}
 Set-Location -LiteralPath $location.Path
}
