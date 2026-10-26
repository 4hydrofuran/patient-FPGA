# A13 不改线时钟与文件TTS接续

最新证据`evidence/a13_A/20261024-audio-nowire-tts-v1/REPORT.md`、`REVIEW.json`。
用户授权无板评估/准备，保留接线/24MHz，不试音；明天外5V只是计划，当前3.3V
总100mA、电流null。禁止把本轮结果当部署、播放或供电变更授权。

时钟：推荐codec由24MHz/PLL生成ADC/DAC与BCLK/LRCLK，现有H12/E10改成**新PL
输入**，用约100MHz过采样、帧事件/FIFO/设备节拍DMA。无需额外MCLK线或拆晶振，
但新RTL/驱动/DT/位流仍未实现。建议16bit槽、双声道S16、BCLK32Fs=1.536MHz，
显式区别旧a06的32bit槽/64Fs。实际a06两脚仍输出，不能切codec主去试。

关键新缺陷：PG308明确Slave mode不支持，安装2026.1 revision11却保留隐藏
C_IS_MASTER0/输入端口，GUI隐藏该参数。不能据旧a06能综合就认定该功能受支持。
不复用隐藏模式作为推荐生产路径。MM2S独立aud_mclk的名义48k也不能当真实codec
节拍；更改主从标志不足。完整推导/预算/待实现清单在`nowire_tts/CLOCK_FEASIBILITY.md`。
原3条CDC仍在旧硬件，未豁免；新架构能否真正消除要看实现后的网表/仿真/报告。

TTS：新增`modules/voice_A/file_tts/`，不替代原SP_VOICE worker。固定Baker+Vocos、
sid0/speed1/silence1、TTS1线程。4个现有wheel和19资源离线包426402232B/2266文件，
144ELF为AArch64，CPython3.12/旧板端glibc2.39依据，未运行ARM/未安装。私有包
`evidence/.../package-arm64-file-only/`被本地Git exclude防误收权重；外部PACKAGE及
MANIFEST索引可核验，禁止再分发。目标符号/ISA/内存/实际导入仍NOT_TESTED。

21项PC测试exit0；网络namespace内两次真实TTS只生成WAV。最新v2从保存的22050
monoPCM16转换320/147至48k双声道，独立重放字节相同，默认文件衰减-30dB。
这不是硬件音量、限流或ASRC。x86调用ARM启动器预期exit2，无输出目录；不是
目标失败或目标执行通过。PC峰值303776KiB高于256MiB设计预算，ARM值不能推断。
ASR/LLM/完整问诊链本轮未新增验证，A12第11步仍待其工作线收口。

后续可先无板实现新PL/握手/设备节拍DMA/驱动并真实RTL/STA/CDC验证。静默板窗
另需新鲜身份、租约/双锁、供电/电平/时钟、IIC与文件TTS导入/内存/回滚；未通过
不解锁声卡。不改现有a06、禁流驱动、disabled DT、默认启动、计算位流或工具安装。
不推送、不用子代理；实际设置unknown。并行TT10新文档/结果原样保持，勿整体恢复
旧docs快照。回滚说明及运行命令在`platform/qwen35/a13/nowire_tts/README.md`。
