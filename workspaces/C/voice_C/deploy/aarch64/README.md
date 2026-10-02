# aarch64 安装准备，BOARD_NOT_TESTED

本材料面向 KV260 Cortex-A53 的 GNU/Linux aarch64，固定 CPython 3.12。已下载同版本的 NumPy 2.5.3、sherpa-onnx / sherpa-onnx-core 1.13.8 ARM64 wheel，并校验 PyPI SHA256 与内部 AARCH64 ELF 文件头。这不是交叉编译成功，也不是 ARM64 原生导入或板端运行成功。

A53 的目标是 ARMv8-A / NEON，不假定支持 SVE、dot-product 或 ARMv8.1 LSE。ELF 的 e_machine=183 只能证明架构标记，不能证明 wheel 的全部指令兼容 A53；必须上板验证。NumPy wheel 的 manylinux tag 要求 glibc >=2.27，sherpa wheel 要求 >=2.17；真实 rootfs、glibc、Python、CPU features 与内存预算未提供，不自动改系统。

先在已确认的独占板端窗口采集环境：

```bash
python3 deploy/aarch64/preflight.py > /approved/new/path/preflight.json
```

满足 Python/架构/glibc 后，先在新目录安装，仅使用包内离线依赖：

```bash
python3 tools/install_candidate.py --target-runtime /approved/new/voice_C_runtime
/approved/new/voice_C_runtime/.venv/bin/python /approved/new/voice_C_runtime/bin/selftest.py --output /approved/new/contract_result
```

模型权重因分发许可待确认而未包含。获准的本地模型另按 assets/asr、assets/tts 的固定 lock 核对和安装，然后再执行 --real 自测；模型缺失应报失败，不能以契约测试替代真实语音运行。

Windows WinMM 麦克风适配器不能用于 Linux。板端主应用需使用本地 ALSA/USB 音频采集并统一为 16 kHz mono PCM16，再通过同一 SP_VOICE_V1 spool/JSONL 接口提交；这部分尚未接入或实测。worker 的 transcribe / streaming / synthesize 本身不调用声卡或扬声器。

上板不得抢占 A 默认服务，不能在根文件系统全局升级 Python、pip 或驱动。若预编译 wheel 因 rootfs/指令集不兼容，应先提供真实平台信息，再按官方构建文档制作匹配依赖，固定源版本与 `-march=armv8-a -mtune=cortex-a53` 并验证实际产物。没有工具链和 rootfs 时不编造已构建的库。

来源：[sherpa ARM64 构建文档](https://k2-fsa.github.io/sherpa/onnx/install/aarch64-embedded-linux.html)、[NumPy 固定版本](https://pypi.org/project/numpy/2.5.3/)、[sherpa-onnx](https://pypi.org/project/sherpa-onnx/1.13.8/)、[sherpa-onnx-core](https://pypi.org/project/sherpa-onnx-core/1.13.8/)。
