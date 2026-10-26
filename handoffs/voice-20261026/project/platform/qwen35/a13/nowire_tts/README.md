# A13 不改线时钟评估与文件型TTS运行包

此候选不替换`voice_A`现有SP_VOICE_V1 worker；只用于独立模型到WAV的维护验证。没有声卡、播放、麦克风、SSH、板端加载或运行时下载接口。

## 入口与运行命令

- [时钟可行性与推荐方案](CLOCK_FEASIBILITY.md)：保留24MHz及所有信号接线，codec主时钟＋新PL过采样/设备节拍DMA；不是改一下现有a06即可运行。
- 运行包目录：`C:/Patientqwen/evidence/a13_A/20261024-audio-nowire-tts-v1/package-arm64-file-only/`，本机Git exclude防止误收权重，禁止自动再分发。
- 固定4个已有ARM64依赖wheel：numpy1.26.4、scipy1.15.3、sherpa-onnx/core1.12.40；19个锁定TTS文件。使用CPython3.12、AArch64；旧板端快照glibc2.39，仅作准备依据，不是当前目标导入证明。
- 包内`MANIFEST.json`逐文件hash；`PACKAGE.json`记录RECORD/ELF、外部库名和未测项。离线展开到私有site-packages，没有pip安装、系统库改动或板端复制。

无板重跑（每次使用全新证据和输出目录，不覆盖现有批次）：

```sh
cd /mnt/c/Patientqwen
/home/member-a/voice-a03/venv/bin/python -B platform/qwen35/a13/nowire_tts/test_offline.py
unshare -Urn /home/member-a/voice-a03/venv/bin/python -B -m modules.voice_A.file_tts \
  --root /mnt/c/Patientqwen --pc-validation --output-dir /absolute/new/pc-output
```

`build_package.py`生成本批次固定唯一目录；已存在则拒绝。新包应先派生新版本目录并重新哈希，不删除或覆盖旧版本以重跑。

将来**经授权的板端文件验证窗口**才可运行下列命令；本轮没有执行，没有提供自动传输/安装/播放：

```sh
bash /absolute/verified/package/run-file-tts.sh \
  --output-dir /absolute/new/private-output --text '你好，这是离线语音测试。'
```

输出`tts-22050-mono.wav`、`tts-48000-stereo.wav`、`RESULT.json`。输出目录须全新；最多128字符/30秒，固定sid0、speed1、silence1、默认TTS1线程。目标解释器和架构不匹配立即拒绝；还需在板端检查库符号、实际导入、A53指令及内存，不能直接认为可运行。

转换为精确320/147有理比、多相低通FIR，按源WAV逐字节可重算；不是改WAV头，也不作重复在线转换。输出S16双声道L=R，默认文件衰减-30dB、边界过冲另记比例。这不是硬件音量设定、电流限流或试听许可。

## 回滚与后续

现有engine/worker/资源锁/manifest未改；新工具与包不被默认配置引用。未装到板端，无需板端撤销；不用新候选即可回到原路径，不加载旧音频位流冒充回滚。原a06、禁流驱动、disabled DT、六份旧封存和器件私有备份都保留。后续复制到板端也要新目录，不覆盖`/opt/patient-qwen`或既有维护版本，不创建服务/默认启动链接。

阶段性PC文件合成结果不能作为BOARD、可懂度、声学时延或医疗审核通过。Matcha/Baker非商业/再分发限制保持；不推送模型或包。当前3.3V总100mA、电流未核实，播放/录音/功放操作始终为0。
