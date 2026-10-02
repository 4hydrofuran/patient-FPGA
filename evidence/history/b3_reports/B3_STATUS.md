# B3 首轮开发状态（2026-10-01）

## 当前结论

已实现冻结 B2 ABI 下的 32-lane INT32 数据通路、128-bit 权重 burst、2048 字节有界 tile 缓存与连续 A8/Sw/Y 搬运。保持分组 FP32 恢复、输出 padding 和先完整检查权重再写 y 的规则。本轮输入全部是固定 seed 的合成数据，不依赖训练集。

| 验证 | 结果 | 当前证据 |
| --- | --- | --- |
| 普通 C++ 编译与 full 回归 | PASS；21 个事务，75963 个整数部分和、7712 个 FP32 输出 | `logs/native_test.console.log`、`reports/native_test.receipt.json` |
| 与原 B2 数学兼容 | 同一批保存输入，15 个合法用例 PASS；含四种实际 MLP 尺寸 | `logs/baseline_test.console.log`、`reports/baseline_test.receipt.json` |
| Vitis Csim | PASS；full 回归，0 errors | `reports/csim.log`、`reports/csim.receipt.json` |
| Vitis C 综合 | PASS；所有流水循环目标 II 满足 | `reports/csynth.rpt`、`reports/tile_compute_csynth.rpt`、`reports/tile_load_csynth.rpt`、`reports/synth.receipt.json` |
| XSIM C/RTL 联合仿真 | PASS；19 个事务，6688 个顶层 FP32 输出检查，含完整合成 up/down | `reports/cosim.rpt`、`reports/transactions.rpt`、`reports/cosim.receipt.json` |
| XO 导出 | PASS；C 综合流程已导出候选 XO | `artifact/w4a8_linear_v1.xo`、`reports/hls_compile.log` |
| A 平台链接、实现后时序、板测 | NOT_RUN | 后续与 A 联合验收 |
| HLS 专项可读性自动检查 | NOT_PASS；不作为功能通过证据 | `reports/hls_readability.json` |

## 综合报告中的真实结构

- 器件 `xck26-sfvc784-2LV-c`，Vitis HLS 2026.1 Build 6493734。
- 目标 6.667 ns（150 MHz），估算周期 5.241 ns、估算 Fmax 190.81 MHz。不是布局布线后的实际 Fmax。
- 整核估计资源：BRAM18K 117、DSP 58、FF 17068、LUT 30801、URAM 0。不是平台与核的整套实现资源。
- 实际 32-lane helper 使用 32 个 DSP，计算循环 II=1，128 元素一组、32 个输出的 helper 延时估计为 133 个周期。
- 权重缓存填充循环 II=1，128 轮搬入 2048 字节，局部流水模块延时估计 131 周期；外部 AXI 请求延时另在外层调度中体现，不能把 131 当作实际 DDR tile 服务时间。
- 编译日志明确推断 128-bit `gmem_w` burst；X 为 512-bit、Sw/Y 为 32-bit，metadata master 为 512-bit。与 B2 生成的端口宽度一致。
- 顶层参数为运行时维度，CSynth 总延时显示 `?`。代表性任务时延应使用 Cosim 事务报告及后续板端测量，不使用巨大的松弛循环上界冒充实际层时延。

## 本轮排除的瓶颈

第一版定长 memcpy 虽推断宽 burst，缓存更新仍逐字节执行，权重拷贝 outline 估计 6145 周期。改为 16 字节展开后，若 helper 不内联，HLS 丢失调用点的 tile 对齐信息，仍推断 8-bit burst、搬运 II=16。最终内联保留 2048 字节对齐关系，恢复 128-bit burst 和 II=1。

初轮探查报告和当时源码分别保存在 `reports/initial_probe/`、`reports/byte_burst_probe/`，与当前结果明确区分。三个方案的浮点数学未改变。

## RTL 联合仿真的事务时延

2026-10-01 的 XSIM Verilog 报告为 Pass，19 个事务的最小/平均/最大 latency 为 251/68336/641171 周期；平均值混合合法、错误及不同尺寸输入，不用作单层性能指标。

| 合成输入 | 事务号 | 核 latency（周期） | 按 6.667 ns 换算 |
| --- | ---: | ---: | ---: |
| T=1、K=896、N=4864（up） | 17 | 641171 | 约 4.275 ms |
| T=1、K=4864、N=896（down） | 18 | 619331 | 约 4.129 ms |

这里是仿真 AXI 存储模型下的核时延，包含权重预检查，不包含主机 BO 分配、主机传输或平台竞争。不能当作 KV260 实测，也没有进行 B2/B3 的同环境 RTL 时延比较，不能据此声称倍数加速。最后一个事务没有下一次调用，interval 显示 x 是报告的正常空值，不是仿真失败。

## 输入与检查范围

full 回归覆盖手算、随机满 tile、N/K 尾部、不同组 scale、全零、极值、T=4/8 既有功能、一般 FP32 scale、padding 保留码、多次调用和五类错误事务。实际尺寸的合成向量包括 896→4864、4864→896、896→896、896→128。原始字节和 JSON 保存在 `vectors/generated/`，每个文件都有 SHA-256。

INT32 expected 来自独立 dense INT64 累加参考，然后检查精确 INT32 相等。FP32 采用原 B2 的 1e-6 绝对阈值，另明确拒绝 NaN/Inf 假通过。未测试 NaN/Inf scale 的新处理策略，未更改冻结 ABI 对它们的行为。testbench 的 helper 检查是软件/Csim 部分和观测；RTL Cosim 验证的是顶层 Y 和元数据，不声称直接观测 RTL 内部所有部分和。

## 待继续的工作

1. A 依据同一平台链接本轮 `.xo`，检查实现后时序和实板输入/输出同步。本轮只确认参数 metadata 与 B2 相同，不声称平台连接已验证。
2. 拿到 A 的实际模型张量后补真实数据回归；合成尺寸通过不能替代模型推理或医学问诊评估。
3. 专项可读性检查仍提出命名、注释格式、函数长度等整理项。冻结的公共参数名不可为满足 typed-prefix 规则而擅自改动；本轮不宣称通过该独立风格门限，需在后续源码整理时按 ABI 例外与内部实现分别处理。因此当前版本是功能验证通过的接入候选，不是通过全部交付门限的最终版本。
4. 保留全权重预检查意味着 T=1 权重仍读取两遍；单缓冲不重叠搬运与计算。下一轮根据实际平台带宽和板测延时决定优化，64 路、双缓冲及多 token 权重复用尚未开展。
