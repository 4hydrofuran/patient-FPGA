# B03独立构建与分域验证；每次尝试保存源码指纹和日志，失败记录不覆盖。
[CmdletBinding()]
param(
    [ValidateSet('baseline','reuse','double')][string]$Variant='double',
    [ValidateSet('native','csim','synth','cosim','stall','all','recover')][string]$Target='native',
    [ValidateSet('combined','smoke','gate_t1','gate_t8','down_t1','down_t8')][string]$Group='combined',
    [ValidateSet('combined','basic','lifecycle','tail','max_k','max_n')][string]$StressGroup='combined',
    [string]$PreparedReceipt='',
    [string]$VitisRoot='D:\2026.1\2026.1\Vitis',
    [string]$MingwRoot='D:\mingw64\bin'
)
$ErrorActionPreference='Stop'
$root=$PSScriptRoot
$savedLocation=Get-Location
$runMutex=[Threading.Mutex]::new($false,'Local\KV260_B03_Verification')
$ownsMutex=$false
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
if($Group -ne 'combined') { $config="hls_prefill_${Variant}_${Group}.cfg" }
if($Target -eq 'stall') {
    $config=if($StressGroup -eq 'combined'){"hls_prefill_${Variant}_stall.cfg"}else{"hls_prefill_${Variant}_stall_${StressGroup}.cfg"}
}
$testbench=if($Target -eq 'stall'){'tb/tb_prefill_bounds.cpp'}else{'tb/tb_prefill_v1.cpp'}
$source=if($Variant -eq 'baseline'){'baseline/b02/src/w4a8_linear_v1.cpp'}else{'src/w4a8_prefill_v1.cpp'}
$defines=@('-DB02_CACHE_X','-DB02_AXI_X128','-DB03_TEST')
if($Variant -ne 'baseline') { $defines+='-DB03_REUSE' }
if($Variant -eq 'double') { $defines+='-DB03_DOUBLE_BUFFER' }
function Invoke-Step {
    param([string]$Name,[string]$Executable,[string[]]$Arguments,[string]$WorkingDirectory=$root)
    if($Executable -eq (Join-Path $MingwRoot 'g++.exe')) {
        # 避免GCC以包含../的路径启动子进程，收据记录真正传给编译器的参数。
        $Arguments=@("-B$healthyCompilerDirectory/")+$Arguments
    }
    $fingerprints=[ordered]@{}
    foreach($path in @($source,'src/w4a8_linear_v1.hpp','baseline/b02/src/w4a8_linear_v1.hpp',
        $testbench,'tb/golden_w4a8.hpp','host/linear_validation.hpp',
        'reference/quantization.hpp','tests/support/quantization_checks.hpp',
        'tests/numerical/prefill_tensor_replay.cpp',$config,'run_prefill.ps1')) {
        $fingerprints[$path]=(Get-FileHash -LiteralPath (Join-Path $root $path) -Algorithm SHA256).Hash
    }
    $code=-1
    $watch=[Diagnostics.Stopwatch]::StartNew()
    $log="$logDirectory/$Name.log"
    $stepLocation=Get-Location
    $stepCompilerSearch=$env:COMPILER_PATH
    Write-Host "B03 $Variant $Name started; log: $log"
    try {
        $previous=$ErrorActionPreference
        $ErrorActionPreference='Continue'
        Set-Location -LiteralPath $WorkingDirectory
        # 仅健康MinGW使用其配套编译器目录；Vitis/Vivado的另一版GCC保持自身搜索路径。
        if($Executable -eq (Join-Path $MingwRoot 'g++.exe')) {
            $env:COMPILER_PATH="$healthyCompilerDirectory;$($MingwRoot.Replace('\','/'))"
        }
        & $Executable @Arguments *> (Join-Path $root $log)
        $code=$LASTEXITCODE
        $ErrorActionPreference=$previous
    } finally {
        $watch.Stop()
        $env:COMPILER_PATH=$stepCompilerSearch
        Set-Location -LiteralPath $stepLocation.Path
        [ordered]@{stage='B03';variant=$Variant;step=$Name;executable=$Executable;
            arguments=$Arguments;working_directory=$WorkingDirectory;exit_code=$code;elapsed_seconds=$watch.Elapsed.TotalSeconds;
            log=$log;input_sha256=$fingerprints;finished_at_utc=[DateTime]::UtcNow.ToString('o')} |
            ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $root "$receiptDirectory/$Name.receipt.json") -Encoding utf8
    }
    Write-Host "B03 $Variant $Name exited $code after $([math]::Round($watch.Elapsed.TotalSeconds,1))s"
    if($code -ne 0) { Get-Content -LiteralPath $log -Tail 25 | Out-Host; throw "$Name failed: $code" }
    if($Name -in @('native_test','real_test')) {
        Get-Content -LiteralPath $log | Select-String 'PASS suite=|real-tensor PASS' | ForEach-Object { Write-Host $_.Line }
    }
}

# 原生链接失败时仅连接本次已编译目标；实际RTL与输出回放必须各自退出0。
function Invoke-CosimRecovery {
    param([string]$Step,[string]$Preparation)
    $prepared=Get-Content -LiteralPath (Join-Path $root $Preparation) -Raw | ConvertFrom-Json
    foreach($entry in $prepared.input_sha256.PSObject.Properties) {
        if($entry.Name -eq 'run_prefill.ps1') { continue }
        if((Get-FileHash -LiteralPath (Join-Path $root $entry.Name)).Hash -ne $entry.Value) {
            throw "Prepared vectors/source changed: $($entry.Name)"
        }
    }
    $sim=Join-Path $root "build/b03_${Variant}_hls/hls/sim/verilog"
    $objectDir=Join-Path $sim 'xsim.dir/w4a8_linear_v1/obj'
    $started=([DateTime]::Parse($prepared.finished_at_utc)).ToUniversalTime().AddSeconds(-$prepared.elapsed_seconds)
    # xelab已生成的新鲜C若仅缺object，使用同一Vivado GCC和原编译选项补编。
    # -B只纠正包含../的子进程路径；C源码不改，旧object不补用。
    $vivadoRoot=Join-Path (Split-Path $VitisRoot -Parent) 'Vivado'
    $vendorBin=Join-Path $vivadoRoot 'tps/mingw/6.2.0/win64.o/nt/bin'
    $vendorHelpers=Join-Path $vivadoRoot 'tps/mingw/6.2.0/win64.o/nt/libexec/gcc/x86_64-w64-mingw32/6.2.0'
    $repairs=[ordered]@{}
    for($round=1;$round -le 3;$round++) {
    $generated=@(Get-ChildItem -LiteralPath $objectDir -Filter 'xsim_*.c')
    foreach($c in $generated) {
        $o=Join-Path $objectDir ($c.BaseName+'.win64.obj')
        if(!(Test-Path -LiteralPath $o) -or (Get-Item -LiteralPath $o).LastWriteTimeUtc -lt $c.LastWriteTimeUtc) {
            if($c.LastWriteTimeUtc -lt $started){throw "Stale generated C: $($c.Name)"}
            $beforeC=(Get-FileHash -LiteralPath $c.FullName).Hash
            $cRelative="xsim.dir/w4a8_linear_v1/obj/$($c.Name)"
            $oRelative="xsim.dir/w4a8_linear_v1/obj/$($c.BaseName).win64.obj"
            $languageArgs=if((Get-Content -LiteralPath $c.FullName -Raw) -match 'extern "C"'){@('-x','c++')}else{@()}
            $compileArgs=@("-B$($vendorHelpers.Replace('\','/'))/","-B$($vendorBin.Replace('\','/'))/",'-fPIC')+$languageArgs+@('-c','-Wa,-W',"-I$vivadoRoot/data/xsim/include",$cRelative,'-O1','-o',$oRelative,'-DXILINX_SIMULATOR')
            $vendorPath=$env:PATH
            try {
                $env:PATH="$vendorBin;$vendorPath"
                Invoke-Step "${Step}_object_$($c.BaseName)_round$round" (Join-Path $vendorBin 'gcc.exe') $compileArgs $sim
            } finally {$env:PATH=$vendorPath}
            if((Get-FileHash -LiteralPath $c.FullName).Hash -ne $beforeC){throw 'Generated C changed while compiling'}
            $repairs[$c.Name]=[ordered]@{generated_c_sha256=$beforeC;object_sha256=(Get-FileHash -LiteralPath $o).Hash}
        }
    }
    # 部分C编译后，xelab还须生成DPI胶水和2026.1快照类型/版本文件。
    # 不以object连续或CLI退出0代替快照完整性。
    $snapshotSupport=@('xsim.svtype','xsim.version','xsim.mem','xsim.reloc','xsim.type')
    $supportFresh=$true
    foreach($name in $snapshotSupport) {
        $file=Join-Path $sim "xsim.dir/w4a8_linear_v1/$name"
        if(!(Test-Path -LiteralPath $file) -or (Get-Item -LiteralPath $file).Length -eq 0 -or
           (Get-Item -LiteralPath $file).LastWriteTimeUtc -lt $started.AddSeconds(-2)) {$supportFresh=$false}
    }
    if($supportFresh){break}
    if($round -eq 3){throw 'Current snapshot support files incomplete; RTL was not run'}
    $elaborateLine=@(Get-Content -LiteralPath (Join-Path $sim 'run_xsim.bat') | Where-Object {$_ -like 'call *xelab *'})
    if($elaborateLine.Count -ne 1){throw 'Generated xelab command is ambiguous'}
    $elaborateBatch=Join-Path $root "$logDirectory/${Step}_elaborate_round$round.cmd"
    @('@echo off',($elaborateLine[0]+' -v 1'),'exit /b %errorlevel%') | Set-Content -LiteralPath $elaborateBatch -Encoding ascii
    try {Invoke-Step "${Step}_elaborate_round$round" $env:ComSpec @('/d','/c',$elaborateBatch) $sim}
    catch {Write-Host 'Elaboration failure preserved; next round only repairs fresh generated files.'}
    }
    $generated=@(Get-ChildItem -LiteralPath $objectDir -Filter 'xsim_*.c')
    if($repairs.Count){$repairs | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$receiptDirectory/${Step}_object_repairs.json" -Encoding utf8}
    $objects=@(Get-ChildItem -LiteralPath $objectDir -Filter '*.win64.obj' | Sort-Object Name)
    $indices=@($objects | ForEach-Object {
        if($_.Name -notmatch '^xsim_(\d+)\.win64\.obj$' -or $_.Length -eq 0 -or $_.LastWriteTimeUtc -lt $started) {
            throw "Incomplete/stale compiled object: $($_.Name)"
        }
        [int]$Matches[1]
    } | Sort-Object)
    if($objects.Count -eq 0 -or $indices[0] -ne 0 -or $indices[-1] -ne $objects.Count-1) { throw 'Compiled object set has gaps' }
    foreach($c in $generated) {
        $o=Join-Path $objectDir ($c.BaseName+'.win64.obj')
        if(!(Test-Path -LiteralPath $o) -or (Get-Item -LiteralPath $o).LastWriteTimeUtc -lt $c.LastWriteTimeUtc) {
            throw "Missing object for generated C: $($c.Name)"
        }
    }
    $pc=Join-Path $sim '../wrapc_pc/cosim.pc.exe'
    # 本机basename启动失败可令Vitis把PC程序误命名为TV；明确强制POST_CHECK并隔离其object缓存。
    $nativeShim=$shim.Replace('\','/')
    $postMakeArguments=@('-f','cosim.pc.mk','DIRECTORY=wrapc_pc',"ObjDir=postcheck_objects_$stamp",'VERBOSE=1',
        "MKDIR=$nativeShim/mkdir.exe","RM=$nativeShim/rm.exe","CP=$nativeShim/cp.exe","MV=$nativeShim/mv.exe")
    $postCompilerPath=$env:PATH
    try {
        $env:PATH="$VitisRoot\lib\win64.o;$VitisRoot\bin\unwrapped\win64.o;$postCompilerPath"
        Invoke-Step "${Step}_postcompile" (Join-Path $MingwRoot 'make.exe') $postMakeArguments (Join-Path $sim '../wrapc_pc')
    } finally { $env:PATH=$postCompilerPath }
    $postCompileLog=Get-Content -LiteralPath "$logDirectory/${Step}_postcompile.log" -Raw
    if($postCompileLog -notmatch 'POST_CHECK') { throw 'Explicit POST_CHECK compile flag absent' }
    # Vitis可复用同一编译选项的postchecker；argv选择用例，无须每组重编。
    $latestDependency=(Get-Item -LiteralPath (Join-Path $root $testbench),(Join-Path $root $source),
        (Join-Path $root 'src/w4a8_linear_v1.hpp'),(Join-Path $root 'tb/golden_w4a8.hpp') |
        Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc
    if(!(Test-Path -LiteralPath $pc) -or (Get-Item -LiteralPath $pc).LastWriteTimeUtc -lt $latestDependency) { throw 'Prepared postchecker is missing or older than its source' }
    $hashes=[ordered]@{}
    foreach($o in $objects) { $hashes[$o.Name]=(Get-FileHash -LiteralPath $o.FullName).Hash }
    $snapshot=Join-Path $sim 'xsim.dir/w4a8_linear_v1/xsimk.exe'
    # 使用相对object路径缩短Windows子进程命令行，并明确链接器搜索目录。
    $linkArgs=@('-Wa,-W','-O','-Wl,--stack,104857600,--image-base,0x400000','-o','xsim.dir/w4a8_linear_v1/xsimk.exe')+
        @($objects | ForEach-Object { "xsim.dir/w4a8_linear_v1/obj/$($_.Name)" })+
        @("-L$vivadoRoot/lib/win64.o",'-lxv_simulator_kernel','-lxv_simbridge_kernel')
    $compilerSearch=$env:COMPILER_PATH
    try {
        $env:COMPILER_PATH=$MingwRoot.Replace('\','/')
        Invoke-Step "${Step}_relink" (Join-Path $MingwRoot 'g++.exe') $linkArgs $sim
    } finally { $env:COMPILER_PATH=$compilerSearch }
    [ordered]@{prepared_receipt=$Preparation;object_sha256=$hashes;
        snapshot_sha256=(Get-FileHash -LiteralPath $snapshot).Hash;
        postchecker_sha256=(Get-FileHash -LiteralPath $pc).Hash} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$receiptDirectory/${Step}_snapshot.json" -Encoding utf8
    $xsimLine=@(Get-Content -LiteralPath (Join-Path $sim 'run_xsim.bat') | Where-Object {$_ -like 'call *xsim *'})
    if($xsimLine.Count -ne 1) { throw 'Generated XSIM command is ambiguous' }
    $batch=Join-Path $root "$logDirectory/${Step}_rtl.cmd"
    @('@echo off',$xsimLine[0],'exit /b %errorlevel%') | Set-Content -LiteralPath $batch -Encoding ascii
    Invoke-Step "${Step}_rtl" $env:ComSpec @('/d','/c',$batch) $sim
    $completedLog=Join-Path $sim 'xsim.dir/w4a8_linear_v1/xsimkernel.log'
    if(!(Test-Path -LiteralPath $completedLog) -or (Get-Content -LiteralPath $completedLog -Raw) -notmatch 'Simulation completed') {
        throw 'XSIM wrapper exit is not proof of completed RTL; kernel completion marker absent'
    }
    $suiteLine=Get-Content -LiteralPath $config | Where-Object {$_ -like 'cosim.argv=*'}
    $suite=($suiteLine -split '--suite ')[1].Trim()
    $postPath=$env:PATH
    try {
        $toolParent=Split-Path $VitisRoot -Parent
        $env:PATH="$toolParent\win64\lib\csim;$VitisRoot\tps\mingw\10.0.0\win64.o\nt\bin;$toolParent\win64\tools\fpo_v7_1;$postPath"
        Invoke-Step "${Step}_postcheck" $pc @('--suite',$suite) (Join-Path $sim '../wrapc_pc')
    } finally { $env:PATH=$postPath }
}
# 已完成的RTL只补做实际输出校验；准备阶段失败仍走新鲜object恢复路径。
function Invoke-VerifiedRecovery {
    param([string]$Step,[string]$Preparation,[string]$RecoveryGroup,[int]$Count)
    $prepared=Get-Content -LiteralPath (Join-Path $root $Preparation) -Raw | ConvertFrom-Json
    $nativeText=Get-Content -LiteralPath (Join-Path $root $prepared.log) -Raw
    $kernelLog=Join-Path $root "build/b03_${Variant}_hls/hls/sim/verilog/xsim.dir/w4a8_linear_v1/xsimkernel.log"
    if($nativeText -match "RTL Simulation\s*:\s*$Count / $Count" -and
       $nativeText -match 'Starting C post checking' -and
       (Test-Path -LiteralPath $kernelLog) -and
       (Get-Content -LiteralPath $kernelLog -Raw) -match 'Simulation completed') {
        & (Join-Path $root 'tools/complete_prefill_postcheck.ps1') -Variant $Variant -Group $RecoveryGroup -PreparedReceipt $Preparation -VitisRoot $VitisRoot -MingwRoot $MingwRoot
    } else {
        Invoke-CosimRecovery $Step $Preparation
    }
}
Set-Location -LiteralPath $root
try {
    try { $ownsMutex=$runMutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $ownsMutex=$true }
    if(!$ownsMutex) { throw 'Another B03 run owns the verification lock. Run serially.' }
    $activeSimulation=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'xsimk.exe' -and $_.ExecutablePath -like "$root\build\b03_*" })
    if($activeSimulation.Count -gt 0) { throw 'An interrupted B03 simulation is still active; no overlapping run started.' }
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
    # Vivado自带GCC的cc1位于libexec；优先提供配套bin DLL，避免与另一版MinGW混用。
    $vivadoGccBin=Join-Path (Split-Path $VitisRoot -Parent) 'Vivado/tps/mingw/6.2.0/win64.o/nt/bin'
    if(!(Test-Path -LiteralPath (Join-Path $vivadoGccBin 'gcc.exe'))) { throw 'Configured Vivado GCC runtime not found' }
    $env:RDI_PREPEND_PATH="$shim;$vivadoGccBin;$MingwRoot"
    $gpp=Join-Path $MingwRoot 'g++.exe'
    $cc1=(& $gpp '-print-prog-name=cc1plus').Trim()
    $healthyCompilerDirectory=(Split-Path (Resolve-Path -LiteralPath $cc1).Path -Parent).Replace('\','/')
    if($Target -in @('native','all')) {
        Invoke-Step 'native_compile' $gpp (@('-std=c++17','-O2','-ffp-contract=off','-Wall','-Wextra','-Wno-unknown-pragmas')+$defines+@($source,'tb/tb_prefill_v1.cpp','-o',"$buildDirectory/numerical_test.exe"))
        Invoke-Step 'native_test' (Join-Path $root "$buildDirectory/numerical_test.exe") @('--suite','full','--dump',$vectorDirectory)
        Invoke-Step 'real_compile' $gpp (@('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas')+$defines+@($source,'tests/numerical/prefill_tensor_replay.cpp','-o',"$buildDirectory/model_tensor_replay.exe"))
        Invoke-Step 'real_test' (Join-Path $root "$buildDirectory/model_tensor_replay.exe") @($realDirectory)
    }
    $run=Join-Path $VitisRoot 'bin/vitis-run.bat'
    if($Target -in @('csim','all')) { Invoke-Step 'csim' $run @('--mode','hls','--csim','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
    if($Target -in @('synth','all')) { Invoke-Step 'synth' (Join-Path $VitisRoot 'bin/v++.bat') @('--compile','--mode','hls','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
    if($Target -in @('cosim','all')) {
        $cosimStep=if($Group -eq 'combined'){'cosim'}else{"cosim_$Group"}
        try { Invoke-Step $cosimStep $run @('--mode','hls','--cosim','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
        catch {
            if($Group -eq 'combined'){Invoke-CosimRecovery $cosimStep "$receiptDirectory/$cosimStep.receipt.json"}
            else {Invoke-VerifiedRecovery $cosimStep "$receiptDirectory/$cosimStep.receipt.json" $Group $(if($Group -eq 'smoke'){30}else{1})}
        }
    }
    if($Target -eq 'recover') {
        if(!$PreparedReceipt -or $Group -eq 'combined') { throw 'Recovery needs the exact preparation receipt and group' }
        Invoke-CosimRecovery "cosim_$Group" $PreparedReceipt
    }
    if($Target -eq 'stall') {
        $stressSuffix=if($StressGroup -eq 'combined'){''}else{"_$StressGroup"}
        $stressSuite=if($StressGroup -eq 'combined'){'smoke'}else{"stress_$StressGroup"}
        $stressCount=@{combined=32;basic=12;lifecycle=11;tail=7;max_k=1;max_n=1}[$StressGroup]
        Invoke-Step 'stall_native_compile' $gpp (@('-std=c++17','-O2','-ffp-contract=off','-Wno-unknown-pragmas')+$defines+@($source,$testbench,'-o',"$buildDirectory/boundary_test.exe"))
        Invoke-Step 'stall_native_test' (Join-Path $root "$buildDirectory/boundary_test.exe") @('--suite',$stressSuite)
        Invoke-Step 'stall_csim' $run @('--mode','hls','--csim','--config',$config,'--work_dir',"build/b03_${Variant}_hls")
        $stallStep="stall_cosim$stressSuffix"
        try { Invoke-Step $stallStep $run @('--mode','hls','--cosim','--config',$config,'--work_dir',"build/b03_${Variant}_hls") }
        catch { Invoke-VerifiedRecovery $stallStep "$receiptDirectory/$stallStep.receipt.json" "stall$stressSuffix" $stressCount }
    }
} finally {
    if($ownsMutex) { $runMutex.ReleaseMutex() }
    $runMutex.Dispose()
    foreach($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name,$saved[$name],'Process') }
    Set-Location -LiteralPath $savedLocation.Path
}
