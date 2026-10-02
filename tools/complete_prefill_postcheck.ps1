# 原生RTL已完整结束而POST_CHECK启动失败时，只恢复实际输出回放，不重复长仿真。
[CmdletBinding()]
param(
 [ValidateSet('baseline','reuse','double')][string]$Variant='baseline',
 [ValidateSet('smoke','gate_t1','gate_t8','down_t1','down_t8')][string]$Group='down_t8',
 [Parameter(Mandatory=$true)][string]$PreparedReceipt,
 [string]$VitisRoot='D:\2026.1\2026.1\Vitis',
 [string]$MingwRoot='D:\mingw64\bin'
)
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$location=Get-Location
$names=@('PATH','CPATH','MAKEFLAGS')
$saved=@{}
foreach($name in $names){$saved[$name]=[Environment]::GetEnvironmentVariable($name,'Process')}
$lock=[Threading.Mutex]::new($false,'Local\KV260_B03_Verification')
$owned=$false
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fffffff')
$receiptDirectory="reports/b03/$Variant/$stamp"
$logDirectory="logs/b03/$Variant/$stamp"
$step="cosim_${Group}_postcheck_only"
try {
 try{$owned=$lock.WaitOne(0)}catch [Threading.AbandonedMutexException]{$owned=$true}
 if(!$owned){throw 'Another B03 verification is running'}
 Set-Location -LiteralPath $root
 if(@(Get-CimInstance Win32_Process | Where-Object {$_.Name -eq 'xsimk.exe' -and $_.ExecutablePath -like "$root\build\b03_*"}).Count){throw 'RTL process is still active'}
 $prepared=Get-Content -LiteralPath $PreparedReceipt -Raw | ConvertFrom-Json
 if($prepared.variant -ne $Variant -or $prepared.step -ne "cosim_$Group" -or $prepared.exit_code -eq 0){throw 'Exact failed native preparation receipt required'}
 foreach($entry in $prepared.input_sha256.PSObject.Properties){
  if($entry.Name -eq 'run_prefill.ps1'){continue}
  if((Get-FileHash -LiteralPath $entry.Name).Hash -ne $entry.Value){throw "Changed input: $($entry.Name)"}
 }
 $started=([DateTime]::Parse($prepared.finished_at_utc)).ToUniversalTime().AddSeconds(-$prepared.elapsed_seconds)
 $sim=Join-Path $root "build/b03_${Variant}_hls/hls/sim"
 $nativeText=Get-Content -LiteralPath $prepared.log -Raw
 $kernelLog=Join-Path $sim 'verilog/xsim.dir/w4a8_linear_v1/xsimkernel.log'
 $count=if($Group -eq 'smoke'){30}else{1}
 if($nativeText -notmatch "RTL Simulation\s*:\s*$count / $count" -or
    $nativeText -notmatch 'Starting C post checking' -or
    (Get-Content -LiteralPath $kernelLog -Raw) -notmatch 'Simulation completed'){
  throw 'No proof that this native RTL run completed before postchecking'
 }
 $proofFiles=@(Get-ChildItem -LiteralPath "$sim/tv/rtldatafile" -Filter 'rtl.*.dat')+
  @((Get-Item -LiteralPath "$sim/verilog/w4a8_linear_v1.performance.result.transaction.xml"),(Get-Item -LiteralPath $kernelLog),(Get-Item -LiteralPath "$sim/verilog/xsim.log"))
 $before=[ordered]@{}
 foreach($file in $proofFiles){
  if($file.LastWriteTimeUtc -lt $started.AddSeconds(-2)){throw "Stale actual RTL evidence: $($file.Name)"}
  $relative=$file.FullName.Substring($root.Length+1).Replace('\','/')
  $before[$relative]=(Get-FileHash -LiteralPath $file.FullName).Hash
 }
 foreach($path in @($receiptDirectory,$logDirectory)){New-Item -ItemType Directory -Force -Path $path | Out-Null}
 $shim=Join-Path ([IO.Path]::GetPathRoot($root)) 'codex-vitis-shims'
 $nativeShim=$shim.Replace('\','/')
 $env:PATH="$VitisRoot\lib\win64.o;$VitisRoot\bin\unwrapped\win64.o;$shim;$MingwRoot;$env:PATH"
 $env:CPATH=(Join-Path (Split-Path $VitisRoot -Parent) 'win64/tools/auto_cc/include').Replace('\','/')
 $env:MAKEFLAGS=''
 $compileLog="$logDirectory/${step}_compile.log"
 $compileStart=[DateTime]::UtcNow
 Set-Location -LiteralPath "$sim/wrapc_pc"
 & (Join-Path $MingwRoot 'make.exe') -f cosim.pc.mk DIRECTORY=wrapc_pc ObjDir=postcheck_objects VERBOSE=1 "MKDIR=$nativeShim/mkdir.exe" "RM=$nativeShim/rm.exe" "CP=$nativeShim/cp.exe" "MV=$nativeShim/mv.exe" *> (Join-Path $root $compileLog)
 $compileCode=$LASTEXITCODE
 if($compileCode -ne 0){throw "Explicit POST_CHECK compile failed: $compileCode; $compileLog"}
 if((Get-Content -LiteralPath (Join-Path $root $compileLog) -Raw) -notmatch 'POST_CHECK'){throw 'POST_CHECK flag absent'}
 $pc=Join-Path $sim 'wrapc_pc/cosim.pc.exe'
 if(!(Test-Path -LiteralPath $pc) -or (Get-Item -LiteralPath $pc).LastWriteTimeUtc -lt $compileStart.AddSeconds(-2)){throw 'Fresh postchecker missing'}
 $toolParent=Split-Path $VitisRoot -Parent
 $env:PATH="$toolParent\win64\lib\csim;$VitisRoot\tps\mingw\10.0.0\win64.o\nt\bin;$toolParent\win64\tools\fpo_v7_1;$env:PATH"
 $suite=if($Group -eq 'smoke'){'smoke'}else{"b03_$Group"}
 $log="$logDirectory/$step.log"
 $watch=[Diagnostics.Stopwatch]::StartNew()
 & $pc --suite $suite *> (Join-Path $root $log)
 $code=$LASTEXITCODE
 $watch.Stop()
 Set-Location -LiteralPath $root
 foreach($entry in $before.GetEnumerator()){
  if((Get-FileHash -LiteralPath $entry.Key).Hash -ne $entry.Value){throw "Actual RTL evidence changed during postcheck: $($entry.Key)"}
 }
 $proof=[ordered]@{prepared_receipt=$PreparedReceipt;native_exit_code=$prepared.exit_code;
  rtl_completed_by_native_logs=$true;rtl_child_exit_code=$null;rtl_evidence_sha256=$before;
  postcompile_exit_code=$compileCode;postcompile_log=$compileLog;
  snapshot_sha256=(Get-FileHash -LiteralPath "$sim/verilog/xsim.dir/w4a8_linear_v1/xsimk.exe").Hash;
  postchecker_sha256=(Get-FileHash -LiteralPath $pc).Hash;postcheck_exit_code=$code}
 $proof | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$receiptDirectory/${step}_proof.json" -Encoding utf8
 [ordered]@{stage='B03';variant=$Variant;step=$step;executable=$pc;arguments=@('--suite',$suite);
  exit_code=$code;elapsed_seconds=$watch.Elapsed.TotalSeconds;log=$log;
  input_sha256=$prepared.input_sha256;finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
  ConvertTo-Json -Depth 8 | Set-Content -LiteralPath "$receiptDirectory/$step.receipt.json" -Encoding utf8
 if($code -ne 0){throw "Actual RTL output postcheck failed: $code"}
 Get-Content -LiteralPath $log | Select-String 'B03 PASS suite=' | ForEach-Object {Write-Host $_.Line}
 Write-Host "Completed native RTL + explicit POST_CHECK passed; native CLI failure preserved; $receiptDirectory/$step.receipt.json"
}finally{
 if($owned){$lock.ReleaseMutex()}
 $lock.Dispose()
 foreach($name in $names){[Environment]::SetEnvironmentVariable($name,$saved[$name],'Process')}
 Set-Location -LiteralPath $location.Path
}
