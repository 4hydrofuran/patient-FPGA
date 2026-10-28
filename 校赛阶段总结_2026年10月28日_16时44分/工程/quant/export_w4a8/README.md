# A04 原始 BF16 → SP_W4A8_128x32_V1

仅支持锁定的 Qwen3.5-0.8B / revision `2fc06364715b967f1860aea9cf38778875588b17`。读取`models/model.lock.json`和`quant/qwen35_tensor_map.json`，逐文件/逐张量核对原始safetensors哈希、dtype、shape、offset与方向。绝不读取GGUF量化字节；旧`quant/exporter/`不变。

## 精度与布局

- BF16按位左移16无损升FP32；FP32 absmax/7为每行每128个K的Sw，FP32 w/Sw，再ties-to-even和[-7,7]夹取。全零组Sw=1。
- 激活每条有效K一个FP32 absmax/127尺度；同样round与[-127,127]，全零Sx=1，尾0。T限制1..8，N/K限制1..4864；先限长再分配。
- 非有限输入、非零尺度下溢0、非法输入类型/形状显式拒绝。保留合法subnormal，不夹epsilon。PC采用NumPy1.26.4，C++独立检查IEEE/little-endian/FE_TONEAREST/非FTZ。
- W:`[Ntile32][G][k128][16 lane pairs]`；相邻输出行共一个字节，偶行低半字节。Sw:`[Ntile32][G][lane32]`，FP32小端。W pad=0，pad行Sw=1。原模型N/K整除，无实际padding或对齐开销。
- 不导出attention、视觉、MTP、embedding/head；共享embedding/head仍属原运行库。72个MLP均无bias，manifest明确null。

所有72矩阵同样有3,670,016个权重，各W=1,835,008字节、Sw=114,688字节，合计1,949,696；72份总计**140,378,112字节**。gate/up N3584/K1024/G8，down N1024/K3584/G28。无二进制头/对齐开销；JSON manifest另88,101字节，逐文件SHA见manifest，不把JSON计入理论payload。

## 复现

在WSL `KV260-A-2204`、`/mnt/c/Patientqwen`，已存在且不升级的Python3.10.12/NumPy1.26.4环境：

```sh
/home/member-a/voice-a03/venv/bin/python -m quant.export_w4a8 --output models/sidecar_A/NEW_UNIQUE_RUN
```

目录必须不存在；不覆盖旧产物。现有两份为`qwen35-v1`、`qwen35-repro-v1`，manifest相同SHA `cdb2a04dbd95d426ea8967cda0adb219a769d3630107a2af72d6ddf2d5285688`。源码producer哈希写入manifest。现有env名字含voice，但本命令不加载ASR/TTS模型。

`loader.Sidecar(path).load('l00_gate')`返回只读memmap(W,Sw)，每实例初次读时检查manifest身份、预期72项、路径/长度/hash；资产须是本地可信且不可变目录。非签名认证，不防持有本机写权限者在校验后改文件。执行入口还必须做C++保留码/尾/尺度语义校验；A05负责将该机制接到正式ABI，不能把Python加载器当完整运行时。

## 内存和限制

导出一次只处理一个原张量，FP32单矩阵14 MiB加临时布局/码/scale，不把整个原权重常驻。实际导出rusage峰值105720 KiB；只读加载全部sidecar并触页最大观测173516 KiB，包含Python/NumPy、文件页和哈希临时区，不是C++/KV260预算。推理权重不逐token量化；未制作第二套完整模型，磁盘复现副本不计作同时常驻。许可沿用model.lock及原LICENSE；不自动发布权重。

报告及原命令：`eval/qwen35/a04/REPORT.md`、`platform/qwen35/a04/evidence/`。BOARD仍NOT_TESTED；全图S1、正式调用ABI、GGUF/sidecar页常驻优化留A05。
