# B02：A8 激活复用候选与消融

## 设计边界

基线是 B01 已通过新尺寸测试的 32-lane 核，源码逐字节冻结在 `baseline/b01/src/`。候选是相同入口加 `B02_CACHE_X` 构建开关，私有 build ID 为 `0xB3020001`；不启用时保持 B01 的 `0xB3010001`。同一个公共 W4A8 字节布局、padding、保留码检查、INT32 组内求和及 FP32 的 `(sum * Sw) * Sx` 和逐组累加顺序均未改动。

候选在每个 token 开头将 `Kp` 个 A8 元素连续读到片上 `token_activations[4864]`，随后每个 32 输出 lane 的 tile/group 从对应 128 字节窗口读取。基线在每个 tile/group 从 `xq` 重读 128 字节。缓存只对 **同一 token 的不同输出 tile** 起效；跨 token 的 W4 权重复用属于 B03。

构建入口：`hls_b02_baseline.cfg` 对冻结基线，`hls_b02_cache_x.cfg` 对候选，`run_b02.ps1 -Target native|csim|synth|cosim` 保存退出码、输入 SHA 和日志。每次只打开一个优化开关，B01 到 B02 的资源及周期差异可归因于本次 A8 缓存改动。

## 源码级访存预期

以下是 C 源码中读请求的**逻辑字节数**，不是物理 AXI/DDR 已传输字节，也未计平台宽度变换、突发切分和缓存行为。两种目标层均以 T=1 计算：

| Qwen3.5-0.8B 目标层尺寸 `(N,K)` | B01 A8 请求 | B02 A8 请求 | 源码级减少 |
|---|---:|---:|---:|
| gate/up `(3584,1024)` | 114,688 B | 1,024 B | 113,664 B |
| down `(1024,3584)` | 114,688 B | 3,584 B | 111,104 B |

计算方式：B01 为 `T × ceil(N/32) × Kp`，候选为 `T × Kp`。在 T=1 时两种形状的 W4 权重仍由保留码预扫和计算阶段分别读取约 1,835,008 B，因此 A8 减少量不能直接转化为同等百分比的端到端收益。

## 已取得的消融数据

同一 Vitis 2026.1、K26 器件、6.667 ns 目标周期、`-ffp-contract=off` 和关闭 unsafe math 下：

| 项目 | B01 冻结基线 | B02 CACHE_X | 解释 |
|---|---:|---:|---|
| HLS 内层输出 tile 估计延时 | 502 cycles | 431 cycles | 减少了逐 group 的 A8 搬运 |
| HLS 单个 group 估计延时 | 322 cycles | 322 cycles | 解包、32 路 MAC、FP32 还原未改 |
| BRAM_18K | 117 | 120 | 用片上 BRAM 换取 A8 复用 |
| DSP | 58 | 58 | 未叠加 DSP |
| FF | 17,068 | 17,057 | HLS 估计 |
| LUT | 30,801 | 30,553 | HLS 估计 |
| 时钟估计 | 5.241 ns | 5.241 ns | 本次未解决潜在时序问题 |
| XSIM gate/up `T=1` | 537,195 cycles | 530,269 cycles | 少 6,926 cycles，约 1.29% |
| XSIM down `T=1` | 523,099 cycles | 524,413 cycles | 多 1,314 cycles，约 0.25% |

HLS 报告给出 6.667 ns 目标与 1.80 ns 不确定度。若将不确定度作为周期预留，可用组合路径预算是 4.867 ns；5.241 ns 估计超出 0.374 ns。因此本表不声称 150 MHz 已收敛，也不把 190.81 MHz 的估计 Fmax 写成实现后/板上频率。关键环路实测周期须以完整 RTL 仿真输出为准；最终时序须以后续平台实现报告为准。

顶层 HLS 延时报告因运行时维度而列出 `?` 或极大的循环上界；这些并非目标层的实际周期数，不用于性能比较。

循环定位：A8 连续装载 `VITIS_LOOP_423_2`、W4 解包加 32 路 INT32 乘加的 `VITIS_LOOP_165_2`、FP32 还原 `VITIS_LOOP_481_7` 的 HLS achieved II 均为 1。乘加循环 128 次、133 cycles，使用 32 DSP；FP32 还原 32 次、53 cycles，使用 8 DSP，估计组合延时 4.828 ns。这说明本轮提升来自搬运位置，而非提高乘加并行度或改变浮点顺序。内层单组延时仍 322 cycles；下一轮若要进一步降低它，应单独评估 W4 装载和 FP32 恢复，不应把多个变化混进 CACHE_X 的消融数据。

## 接口与平台边界

本机安装的 `kv260_base.xpfm` 对应 XSA 标出默认 150 MHz、可连接 HP3 FPD 和 LPD 的 DDR 入口，两者在 PS 端配置为 128 bit。核 HLS 推断的 `gmem_x` 为 512 bit、`gmem_w` 为 128 bit、`gmem_sw` 为 32 bit；512 bit 核口与 128 bit PS 入口之间的实际互连、仲裁和总线流量须在 B04 离线链接/B05 实板验证。`reports/b02/platform_probe.json` 记录本机平台文件 SHA 与原始 PFM 端口声明；不代表已取得用户板卡运行时 profile。

## 验证域

PC native：B01 冻结基线与 B02 候选都通过 43 个 transaction；候选有 2,140,479 次 INT32 部分和与 173,728 次 FP32 输出核对，16 个新尺寸 T1..T8 组合及边界/错误回归均通过。合成向量的 288 个文件逐字节同 B01 一致。Qwen3.5-0.8B 首层 gate/down 真实权重配合合成激活的 4 个 PC 用例通过，40 个记录文件与 B01 逐字节一致。Csim：完整 43 个 transaction 与 16 个新尺寸组合通过。以上都不能代替 RTL/板上验证。

原生 Vitis Cosim 在 Windows 的 XSIM 生成 C 编译阶段退出 1，未启动 RTL。原始日志及收据保留在 `evidence/b02/cosim_attempt_first/`；不把此结果记作通过。对同一 HDL 和生成测试向量的 Xelab 重新编译全部 56 个目标文件，本机编译/链接故障另行记录；手动链接后的 XSIM 实际完成 25/25，退出码 0。Vitis 生成的 C 回放程序核对实际 RTL Y/meta，退出码 0，`max_abs=0`、`nrmse=0`。生成向量、RTL 输出、约 2.0 GB 波形、仿真批处理和性能文件保留在 `evidence/b02/rtl_recovered/`，SHA 见 `reports/b02/rtl_recovered_summary.receipt.json`。

本次 CACHE_X 的结果是正确但性能混合：gate/up 受益、down 略慢，且顶层时钟估计未改善。它是可复核的消融候选，不应被宣传为两个目标层都加速或可达 150 MHz 的最终实现。对 `gmem_x` 512-bit 核口的独立宽度实验、三版比较与 B02 选型见 `SELECTION_AND_DELIVERY.md`；原始提取值见 `reports/b02/ablation.json`。
