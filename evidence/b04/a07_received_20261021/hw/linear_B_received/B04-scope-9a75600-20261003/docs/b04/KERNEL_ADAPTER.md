# B04：double 核适配说明

本文及 `config/b04/kernel_profile.json` 面向 A 的公共 XRT 调用层。B 提供独立布局/完成记录探针，A 负责实际六函数库、BO 分配、同步、有限等待、poisoned 状态和恢复。冻结核、公共数学、布局和 C ABI 未改动。

## 身份与参数

核名 `w4a8_linear_v1`，私有 ABI 1，build_id `0xB3030002`，协议 `ap_ctrl_hs`。实际 XO SHA256：`96ca2a5825c4e044e0159b7a1553a30d8546cc59ab5cfc9201d6d44d4b7ddd23`。profile 从该 XO 的 XML 提取，并编译实际核头核对布局。

| 参数索引 | 参数 | 类型/控制字节 | AXI-Lite 偏移 | 接口 |
|---|---|---|---|---|
| 0 | w_packed | BO / 8 | 0x10 | GMEM_W，128 bit |
| 1 | sw | BO / 8 | 0x1C | GMEM_SW，32 bit |
| 2 | xq | BO / 8 | 0x28 | GMEM_X，128 bit |
| 3 | sx | BO / 8 | 0x34 | 同 GMEM_X |
| 4 | y | BO / 8 | 0x40 | GMEM_Y，32 bit |
| 5 | meta | BO / 8 | 0x4C | GMEM_META，512 bit |
| 6 | t | uint32 / 4 | 0x58 | CONTROL |
| 7 | n | uint32 / 4 | 0x60 | CONTROL |
| 8 | k | uint32 / 4 | 0x68 | CONTROL |
| 9 | w_bytes | uint64 / 8 | 0x70 | CONTROL |
| 10 | sw_bytes | uint64 / 8 | 0x7C | CONTROL |
| 11 | x_bytes | uint64 / 8 | 0x88 | CONTROL |
| 12 | sx_bytes | uint64 / 8 | 0x94 | CONTROL |
| 13 | y_bytes | uint64 / 8 | 0xA0 | CONTROL |
| 14 | meta_bytes | uint64 / 8 | 0xAC | CONTROL |
| 15 | job_id | uint64 / 8 | 0xB8 | CONTROL |
| 16 | abi_version | uint32 / 4 | 0xC4 | CONTROL |

表中端口名缩写对应 XML 的 `M_AXI_GMEM_*`。**参数索引不能当成内存 bank/group 数字**；A 按实际加载的匹配 xclbin 元数据查询每个 BO 参数的可用内存组。xq 和 sx 使用同一 master，但仍是两个独立参数和缓冲区。

## 缓冲区与格式

T=1..8、N/K=1..4864；Np=ceil(N/32)*32、Kp=ceil(K/128)*128、G=Kp/128。

| 缓冲区 | 逻辑最小字节 | 格式 |
|---|---|---|
| w_packed | Np*Kp/2 | tile32 × group128，偶数输出 lane 低4位、奇数高4位 |
| sw | Np*G*4 | FP32，索引 (n//32*G+k//128)*32+n%32 |
| xq | T*Kp | INT8 行主序 |
| sx | T*4 | 每 token FP32 scale |
| y | T*Np*4 | FP32 行主序，成功时 padding 输出为0 |
| meta | 40 | 私有小端完成记录 |

`*_bytes` 使用实际可用容量，满足至少关系。逻辑字节数不等于 BO 物理分配粒度。权重驻留从 load 到 unload；xq/sx 每次 run 更新。A 在安全释放前确认设备不再访问；超时不构成停止证据。

W 必须在[-7,7]，X 必须在[-127,127]；scale 有限且为正。padding W/X 为0，padding权重 scale 为1。全部规则见冻结公共契约。私有核只在有效 W 区拒绝 −8；其他数值和 padding 校验由主机层完成。HLS 的 depth 是仿真拷贝窗口，不能直接作为公共尺寸上限或板端 BO 容量。

## meta 的40字节布局

| 偏移 | 字节 | 字段 |
|---|---|---|
| 0 | 4 | abi_magic=`0x57344138` |
| 4 | 4 | kernel_build_id=`0xB3030002` |
| 8 | 8 | job_id |
| 16 | 4 | status |
| 20 | 4 | done |
| 24 | 8 | hw_completed_count |
| 32 | 8 | algorithm_weight_bytes |

**done=1 表示调用结束，包含错误结束。只有 status=0 且其余字段核对成功，才允许消费 Y。**

首次 meta BO 清零。计数存储在 meta 内存中：核读取调用前值，成功写回该值+1，失败保持该值；它不是独立的设备全局持久计数寄存器。跨调用需要持续计数时，A 保留实际上次返回值及本次调用前值，不能清零整个 meta 后仍假设计数连续，也不能以主机自增冒充核返回的计数。uint64 的回绕按冻结核无符号加法语义处理。

正常完成必须核对 magic、build、非零任务编号、done、status、计数与算法字节。success 计数为 previous+1（模2^64），错误计数为 previous。算法字节在 ABI/维度错误时为0，其余可写 meta 的结果为本形状 Np*Kp/2。该字段是算法 W 字节，不包括 Sw，也不等于实测总线字节。

meta 不可写或小于40字节时，核直接返回，不能保证提供错误记录。调用层须先保证合法 BO/长度，并拒绝未更新或错误的完成记录。错误和超时后均禁止消费 Y，即使缓冲中仍有上次输出。

## 状态规则

| 私有状态 | 含义 | B 提供的公共映射 |
|---|---|---|
| 0 | 成功 | SP_OK |
| 1 | ABI 错误 | SP_CONTRACT_MISMATCH |
| 2 | 维度错误 | SP_BAD_ARGUMENT |
| 3 | 缓冲长度错误 | SP_BUFFER_TOO_SMALL |
| 4 | 数据空指针 | SP_BAD_ARGUMENT |
| 5 | 有效权重中的保留码 −8 | SP_NUMERIC_ERROR |

该表是适配输入与 B 验收规则；A 实现翻译和错误隔离。未知状态、错任务、错完成计数或算法字节应拒绝结果。magic/build 不匹配属于契约/核版本不匹配。`host/b04_private_probe.hpp` 提供独立检查器，不持有设备，不证明 DMA 已结束，也不实现安全 close。

## 同步顺序及报告

1. load 保存并同步 W/Sw，建立驻留句柄；调用方的原数组可按公共契约释放。
2. run 检查尺寸/长度/数值，更新并同步 xq/sx，以及本次 meta 初始状态。
3. 以全部17个参数启动匹配核，进行有限等待。实际超时进入 poisoned，保留可能被设备引用的资源。
4. 完成后先同步 meta 并核验；只有有效成功结果才能同步并提供 Y。
5. 报告记录核实际回显、对应契约/xclbin摘要和分段耗时；未测量字段为 null。

CPU/替身验证明确标记，公共 report 的 execution_kind 按契约使用 CPU_REFERENCE 或 FPGA_REAL。没有真实设备执行时不能填写 FPGA_REAL。量化在外部运行时时，后端 quant_ms 为 null，整机汇总仍记录外部量化成本。

## 当前证据与限制

P1 实际布局编译与 profile 已通过；P2 独立40项检查、66笔实际归档 meta 和108次任务/计数篡改负例通过。原始 RTL 不是本轮新仿真；新检查不证明公共 XRT 生命周期、实际实现时序或 BOARD。

HLS 估计 slack −0.40ns 保留。A 的实际运行时、链接、布局布线和匹配 ARM64 产物到位后，再完成 G1～G6 联合验收。
