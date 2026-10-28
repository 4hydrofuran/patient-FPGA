# A05：Qwen3.5 同数学 CPU 图接入

这是实际计算的 **PC / CPU_REFERENCE** 后端，不是 FPGA，也不是用 Python 调用 72 次子进程。原 A01/A03 可执行文件、A04 导出器和参考保持原样。当前模块身份见 `modules/linear_A/manifest.json`；本次收口证据在 `eval/qwen35/a05/batch-fix-v1/`。原 `eval/qwen35/a05/REPORT.md` 是保留的首次部分完成报告。

## 入口与固定输入

- llama.cpp：`81e39ad34368329b5db77620721510fd91107e80`，当前隔离源码 `/home/member-a/qwen35-a05/source-v3`、库 `llama-build-v4`。原graph-v2.patch后叠加batch-fix-v1的stable-projections.patch、stable-attention.patch；实际hook实现随构建封存。
- 原始 Qwen revision：`2fc06364715b967f1860aea9cf38778875588b17`。原 Q4_K_M GGUF 只提供非目标张量/元数据；MLP 72 个权重来自 A04 原始 BF16 导出的 sidecar，不解释 Q4 字节。
- 当前本地 S1：`/home/member-a/qwen35-a05/build-v8/qwen35-s1`；同目录 `libsp_linear_cpu.so` 实现原 `SP_LINEAR_V1`，与v3库SHA256相同，不改公共头或数学。
- 启动/权重/图身份及哈希：`eval/qwen35/a05/batch-fix-v1/runtime-build-v8.json`。这些 WSL 路径不是可转发安装包或 B/C 已收到交付。

在现有 WSL 的 `/mnt/c/Patientqwen` 中运行：

```bash
python3 -m system_qwen35.app.cli --case SYN_CP_01 --software-test --model-backend s1 --output eval/qwen35/a05/manual-new-run
```

stdin 每行一个既有应用请求，例如 `{"request_id":"q1","text":"哪里痛？","source":"typed","final":true}`。输出目录必须全新。保留 `--model-backend s0` 及现有入口默认值，避免重写旧基线；选择 S1 失败绝不切回 S0。

语音服务同样支持 `VoiceLoop(..., model_backend='s1')` 和 `voice_cli --model-backend s1`。录音仍必须人工授权，A05 自动测试仅复用已标注合成 WAV。不能把播放 drain 当声学实测。

## 数学与真实执行点

`build_lora_mm` 仅对登记的 72 个精确名字构造 `GGML_OP_CUSTOM`；节点唯一输入是真实归一化/门控后的激活。构图不读激活。`ggml_custom_4d` 的 CPU 执行回调收集实际 strides 数据，进行 A8，然后同步调用 C ABI。SiLU、attention、norm、残差和共享 embedding/head 仍由固定原图执行；不重加 bias，不支持 LoRA/w_s 时硬拒绝。

W4/Sw 的大小与 SHA256、模型锁与 tensor map 均核验。加载成功后库拥有一份权重，临时读取/哈希数组释放。A8 使用 A04 已核验代码，每 token 有效 K 的 FP32 absmax/127、ties-to-even、范围[-127,127]、全零 scale=1，拒绝非有限与下溢为0。gate/up 缓存包含 epoch、执行号、层、shape、输入 tensor/strides、一次消费掩码；两次消费或 down 后失效。down 在 SiLU 门控后独立量化。

标量调用独立 A04 scalar；优化路径按32输出lane分组，4 OpenMP线程，支持运行时选择的 AVX2 **整数**路径；其他CPU用可移植整数路径。组内INT32，按组 `float(sum)*Sw`、再 `*Sx`、再 FP32顺序累加。`-O3 -fno-fast-math -ffp-contract=off`，不启编译器全局 `-march=native`，未构建ARM。优化不解包/复制整套模型。正常返回前检查有限值；错误不消费输出，不转硬件或其他模型。

CPU API 单 in-flight；实际线程争用返回 BUSY，超时在同步计算结束确认 CPU quiescent 后标 POISONED，再调用拒绝，close可安全释放。本规则**不适用于仍有DMA在途的硬件**。所有 C 入口包括锁获取的异常边界均捕获，不泄漏 C++异常。调用者不得在已经成功 close 后访问旧指针。

## 分块和状态：物理T与提交长度分开记录

原物理批量路径 `state-v1` 在 T=1/2/4/8 与整段间违反固定阈值，失败保存；标量/优化在同一路径却逐位相同。第一层MLP真实输入已存在分歧，不能把它归因于核实现错误或放宽阈值。

当前默认 **physical_ubatch=8**：外部整段提交按不超过8个token推进混合状态，72个MLP直接接收真实T，尾块保留。`physical_cpu_calls_by_T` 是实际成功CPU调用计数，不是硬件计数。命令行末参数可设1/2/4/8；S1大于8硬拒绝，256仅是合法外部提交长度。

两处数值调度修复均仅作用于隔离S1 profile：非MLP权重投影按token构造原SIMD GEMV，再拼回批量张量；完整注意力使用原SIMD逐查询归约，关闭该算子的query tiling与单查询长KV split/reduce。Gated DeltaNet、卷积、RoPE、norm、SiLU、残差公式及权重精度不改，MLP仍批量。`SP_QWEN35_STABLE_ATTN` 由进程在context创建前强制设置，不采纳外部环境覆盖；ready记录两种调度身份。没有全局启用CPU慢参考。

必须保留零输出位置：仅末位置logits模式的中间块会合法出现T=0的LM head，直接走原空张量运算；不能构造空concat后返回null。正常模式依然只计算所需位置，全logits/节点dump只用于诊断。

v6空输出崩溃、v7长KV分歧及原state-v1失败都保留。数值验收以本次完整报告为准，不凭最终文字相同通过；算子阈值1e-4/1e-5、整图既定阈值0.002/0.0002未放宽。

R0是每轮清空所有混合状态后重算；响应发出前再次清空。因此检查器拒绝或未播放文本不会残留在下一轮 recurrent/conv/KV 中。应用只将已确认交付内容写入已播历史；下一轮仅渲染合法紧凑事实。R1/R2未验收，显式拒绝而非伪造snapshot/cache hit。SIGUSR1是真取消，部分输出不可用；下一轮清理重算。旧 NativeCPU 的真实deadline隔离也保留。

## 内存与日志

只对精确选中的 MLP 跳过上游自动 CPU_REPACK。GGUF 的目标完整页在图执行前 `MADV_DONTNEED` 后 `PROT_NONE`，实际 `/proc/self/smaps` 显示保护页RSS=0；边界共享页保留并逐张量登记。不会改写原GGUF文件。非目标CPU_REPACK仍存在，启动时有短暂重复/加载峰值，不能仅以最终RSS推算启动预算。系统文件缓存不等于进程RSS，也未全局清缓存。

sidecar为拥有的packed内存，不mmap第二份；无每token导出/加载，无BO。CMA、Linux/PL可分配预算和所有硬件字段保持null/NOT_TESTED。正常模式只请求最后输出位置logits；全logits/全层dump是显式有界诊断，时间不得冒充正常性能。持久进程stdout仅JSONL，stderr保留真实运行库日志。

## 复现和已知限制

实际命令/退出码在 `platform/qwen35/a05/evidence/continue-*.json`，含失败。旧构建、原始证据及本次before快照保留。新构建通过唯一 `platform/ra02/build_queue.py` 队列；`build_native_v8.sh`记录本次步骤，复验须指定全新独立build目录，不覆盖旧二进制。初始化源码脚本只用于尚不存在的隔离目录，不重跑迁移/安装。应用从经过SHA256核验的manifest读取native_entry，并核对CPU、72权重、物理T8及注意力调度身份。

A05源码包括：桥、CPU库、持久进程、精确行SIMD、加载/调用错误边界。全图质量与本次数值误差分账：H0/S0/S1有真实非零logits差异；少量合成病例一致不代表通用医学质量。未做教师审核/最终300题/实板/PL/Csim/Cosim/ARM，不扩大通过范围。
