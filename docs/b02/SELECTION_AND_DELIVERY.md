# B02 访存消融、选型与交付

## 选型结论

选 `B02_X128` 作为 **B03 开发基线**：它保留 `B02_CACHE_X` 的每 token 激活复用，只将 `gmem_x` 最大加宽位数限制为 128 bit，与本机 KV260 平台元数据中的 PS DDR 入口宽度一致。相对仅缓存激活的候选，两种 T=1 尺寸均只多 1 个 XSIM 周期，而 HLS 估计 BRAM_18K 从 120 降到 78，LUT 从 30,553 降到 28,006。私有 build ID 为 `0xB3020002`，公共 ABI、字节布局、padding 与 FP32 恢复顺序保持原样。B01 冻结基线和 CACHE_X 均保留，可随时按构建标签重现。

该选择是**无板开发选型**，不是 150 MHz 实现时序通过，也不是板上/整机加速结论。相对 B01，X128 的 gate/up T=1 快 6,925 周期（约 1.29%），down T=1 慢 1,315 周期（约 0.25%）。因此 B03 必须继续守住 decode 的 down 延时，B04 必须完成平台链接与实现时序，B05 才能评价真实 DDR 行为。

## 同输入消融

以下周期来自同一 25 笔合成输入的 XSIM RTL 仿真；B01 与 CACHE_X 使用已记录的本机 XSIM 恢复流程，X128 使用 Vitis 原生 Cosim（退出码 0）。资源和 slack 只来自 Vitis HLS 2026.1 综合估计。

| 构建 | 独立差异 | gmem_x 位宽 | BRAM_18K | DSP | FF | LUT | gate/up T=1 周期 | down T=1 周期 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| B01 | 冻结 32-lane 基线 | 512 | 117 | 58 | 17,068 | 30,801 | 537,195 | 523,099 |
| B02_CACHE_X | 每 token A8 片上缓存 | 512 | 120 | 58 | 17,057 | 30,553 | 530,269 | 524,413 |
| B02_X128 | 在 CACHE_X 上仅限制 gmem_x 加宽 | 128 | 78 | 58 | 15,105 | 28,006 | 530,270 | 524,414 |

X128 相对 CACHE_X 节省 42 个 BRAM_18K。综合报告中 `gmem_x` 接口自身的 BRAM 估计由 57 降为 15，解释了这项差异；片上 A8 缓存仍占 4 个 BRAM。两者顶层 HLS slack 均约 **-0.37 ns**（6.667 ns 周期、1.80 ns 不确定度），需要在 B04 看实现后时序。`gmem_w` 已为 128 bit，2048 字节 tile 按 128 bit 连续加载；`gmem_sw` 仍为 32 bit，报告指示 scale 自动加宽受起始索引对齐分析限制。没有实际总线计数器，因此逻辑请求字节不能写成物理 DDR 流量。

## 正确性与证据

- X128 PC native：43 笔合成事务通过，2,140,479 次 INT32 部分和与 173,728 次 FP32 输出检查通过；T=1..8 的两种新尺寸均在内。4 笔真实首层 gate/down 权重加合成激活通过，516,096 次 INT32 和 41,472 次 FP32 检查通过。合成 288 文件、真实权重回放 40 文件分别与 B01 逐字节一致。
- X128 Vitis Csim：43 笔通过；HLS 综合及 XO 生成退出码 0；原生 Vitis Cosim 25/25 RTL 事务及输出回放通过，退出码 0。Cosim 包含两种真实尺寸 T=1；T=8 真实尺寸 RTL 属于 B03，仍未测。
- X128 波形、输入和 RTL 输出保存在本机 `evidence/b02/x128_rtl_recovered/`；约 2 GB 波形不进入 Git，逐文件 SHA256 在 `reports/b02/x128/rtl_evidence.receipt.json`。三版原始 HLS 报告、RTL 性能文件和成功日志的小文件副本在 `evidence/b02/ablation_raw/`，哈希清单为 `reports/b02/ablation_raw_manifest.json`；提取值在 `reports/b02/ablation.json`。首次 native 编译时本机 MinGW 子进程启动失败（退出码 1），重试通过；原始失败日志被运行脚本覆盖，补记的终端错误与证据限制见 `evidence/b02/x128_attempt_first/NOTE.md`。

## 复现入口与交付范围

在本目录执行 `run_b02_x128.ps1 -Target native|csim|synth|cosim`；X128 配置为 `hls_b02_x128.cfg`。冻结 B01 和 CACHE_X 的构建配置分别为 `hls_b02_baseline.cfg`、`hls_b02_cache_x.cfg`，后者运行入口为 `run_b02.ps1`。综合/RTL 性能提取可运行 `python tools/summarize_b02_ablation.py`；有成功的 X128 Cosim 后运行 `python tools/archive_b02_x128_evidence.py`，再用 `python tools/package_b02_ablation_evidence.py` 生成 Git 内的小型原始证据副本。

Git 交付包含源码、配置、独立测试、状态、报告收据和复现脚本；大波形、模型权重、生成向量及 HLS build 目录留在本机并由 SHA/来源记录，不放入公开源码仓库。本阶段不交付公共 `sp_linear_v1` 动态库或板端 xclbin：它们属于 B04。`BOARD`、aarch64 构建和实现时序继续标为 `NOT_TESTED`。
