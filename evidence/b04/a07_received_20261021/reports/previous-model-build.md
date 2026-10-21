# A06/A07：不等待 B 实物的工作收口

2026-10-03 · A · `PASS_INDEPENDENT_SCOPE_A06_AND_A07_NOT_PASSED`

本轮已实际实现、测试并构建可独立推进的部分。**A06仍未接收完整核包，A07整体未通过，BOARD全部NOT_TESTED。** 原A05电脑CPU通过状态、模型、72矩阵、公共契约和默认选择不变；没有重写HLS核、访问B/C工作区、刷写或推送。

## 实际交付

| 路径 | 内容与边界 |
|---|---|
| `modules/linear_A/xrt/` | 候选C++六函数XRT库；主机数值/长度/pad检查、常驻BO与I/O池、job/meta核对、错误隔离、默认拒绝设备访问。不是应用已接入或板测通过 |
| `platform/qwen35/a07/` | 独立构建入口、生产共用主机逻辑测试、ZIP/XO只读收件工具、构建输入快照、ELF/依赖审计和收口工具 |
| `platform/build/a07-independent-a53-v2/` | 本地staging：真实AArch64 S1程序、CPU库、XRT候选库、主机自测程序及llama/ggml库、manifest与许可证；非完整安装包，无模型/语音权重 |
| `artifact-audit-v2/REPORT.json` | 136编译单元、8个主产物的ELF/hash、依赖闭包和10个rootfs/SDK库比较、实际命令与退出码 |
| `REPORT.json` | 本轮机器报告：分域、原件保护、失败、命令、未决项 |

主产物SHA256：

```text
qwen35-s1
52b70f375bab3626d836a87216eb06849daa02b112b43ba338e6c1a42cc8aafd
libsp_linear_cpu.so
1d1f2dc83d56b1390f2429f14d41154d73fe27a3310b1057d261dceed8bbd3c8
libsp_linear_xrt_candidate.so
58ad2c1cfe2d34a058cd87c8bde638d1ef682740ba81ec11a5310fb13cac42f9
```

## 分域与真实命令

| 域/检查 | 本轮结果 |
|---|---|
| PC主机生产共用逻辑 | 969断言PASS：两真实shape和边界T1..8、W4/A8保留码、scale有限性、pad、短缓冲、非法维度、BO窗口溢出、meta、job、POISONED、发布门禁 |
| PC ASan/UBSan | 同一969断言再次PASS；不是1938个不同案例 |
| ZIP/XO工具 | 8个unittest方法PASS；含仅文档无XO、SHA错误、路径穿越/重复/链接、大小限制、内嵌XML/DTD。合成结构fixture不算收到B核 |
| ARM64交叉构建 | S1、CPU库、XRT候选库、自测及llama/ggml库实际编译链接成功；6个C ABI符号存在 |
| ISA/依赖 | `GGML_NATIVE=OFF`、armv8-a、cortex-a53，无强制dotprod/i8mm/SVE；相对`$ORIGIN`，136单元核验；10库与Common rootfs hash一致 |
| Csim | 本轮不重跑；前一轮旧三版Csim 183例已PASS，不能借给B新源码版本 |
| Cosim/综合/实现/xclbin链接 | NOT_TESTED |
| ARM64程序执行、真实XRT/BO、BOARD | NOT_TESTED；性能、功耗、硬件误差和可用BO预算null |

实际命令都经 `platform/a1/record.py` 保存argv/cwd/时间/stdout/stderr/exit。共享队列独立work目录，未共用B或旧CPU build。

- `scripts/release/check_contracts.py`、`scripts/release/qwen35_config.py`：开工均exit0，收口再次检查。
- 队列 `build_a53.sh` 首次exit0；发现依赖库开发机绝对RPATH，保留旧构建，新v2改为`$ORIGIN`后exit0，未更改旧A05库。
- 队列 `build_host.sh` 首次exit1：主机953断言及sanitizer通过，但XRT链接缺`-luuid`；失败日志保留。修复依赖并补BO窗口/发布门禁用例，v2 exit0，969断言及sanitizer通过，ARM库链接成功。
- `test_delivery.py`：exit0，8方法。
- `audit_build.py v1/v2`：均exit0。v1循环变量遮蔽导致staging目录被命名为`...-host`；保留原目录，v2修正命名；最终使用v2。未因此改二进制或冒称新计算测试。
- 首次`finalize.py` exit1：Windows输入清单反斜杠键在WSL下未归一化。修正读取兼容后重试，原清单不改，失败记录保留；不涉及核/模型/数学或容差。

## 内存唯一归属

未来XRT load成功后，W/Sw归后端BO；输入主机临时数组可释放。72矩阵有效数据仍为140378112B，不在候选库内另保留完整CPU副本。当前默认CPU模型与未打开的XRT候选是两个互斥选择，未同时载入两套模型。

I/O池逻辑字节为X=38912、Sx=32、Y=155648、meta=64，总194656B；每个BO按到板确认的alignment记账。该数字是代码尺寸，不是测得物理占用。BO budget、参数group/address windows、CMA均待板，不能用4GB或256MiB规划值解锁。原GGUF页、sidecar文件页、CPU后端权重与工作区继续遵循A05记录；A12切换时还须实测页/BO重叠与释放。

## 设计差距和剩余门

- 已完成且保留：A01/A04/A05有效成果，许可恢复和旧核Csim。
- 已补实现：D09的候选六函数封装、持久对象/BO、部分sync、受控失败；D11的A53独立构建、可搬移依赖、地址/容量门禁；只读新包接收检查器。
- 已补测：纯主机检查969项、sanitizer、8归档方法、真实交叉链接/符号/ISA/库一致性。
- 仍需B：实际选定版ZIP/XO/内嵌metadata/原始仿真数据及同版来源闭环。旧fdd1源码Csim不能自动证明新e227候选通过；不合并整仓、不另写HLS。
- B包到达后的A工作：先inventory/hash，再A06同版复测，随后A07实际v++链接/布局布线和最终ABI核对。此轮没有发B消息或代签。
- 仍需平台/板卡：匹配KV260启动链、DT/内存差异、设备身份/租约、CMA与BO预算、装载恢复、timeout/驱动挂起、target数值。Common rootfs库吻合不等于可直接启动；不混用EDF/Kria/未核验DT。
- 仍需后续A12：真实模型消费PL结果。当前Bridge继续CPU，不把候选库存在视为FPGA接入。
- P2：更大I/O arena、异步预取、更多并发/缓存和性能优化，未实施不计收益。

`state/sync`驱动调用的最坏阻塞时间尚无实板证明；候选不自动abort/unpoison，POISONED不释放BO或锁。SDK两个旧式装载/构核API的deprecated告警完整保留，不掩盖、不借机升级工具版本。

## 保护与提交

原25项输入留before；收口核对72矩阵的144个payload、默认CPU二进制及契约未变。构建/失败/staging目录全部保留。源码与本轮证据清单见 `files.sha256.json`（不自包含该文件）。分支仍`member-a/qwen35-a00-20261002`，HEAD未变，无新commit、无远程push。没有切模型/强度/速度或启用子代理，实际设置unknown。
