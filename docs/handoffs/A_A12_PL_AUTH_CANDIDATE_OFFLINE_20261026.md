# A12 PL 授权候选：真实后端派生与无板验证（2026-10-26）

本轮从原普通包中冻结的实际 XRT `backend.cpp` 派生 A 自有候选，将私有授权接到 BO 传输、唯一 `run.start()` 和结果提交位置。最终 v4 通过 **41 个 PC XRT 控制用例（839 个断言）及相同 41 个 ASan/UBSan 用例**，已有官方 2026.1 SDK 的 A53 共享库与完整 gate 编译对象均构建成功。独立包完成 ZIP 回读与解包后 PC 替身运行。没有执行 ARM 制品、连接板卡、SSH、恢复、部署、释放、推送或修改 B/HLS/公共数学/ABI。

## 代码与所有权

原后端 SHA 为 `bb0d6f439239606b79acbca541d28be9e63db5e7d882f7bcd8413dfa0dbd062c`。`pl_auth_derive.py` 对每一处替换检查唯一性，逆向替换逐字符还原原件；最终派生源码 SHA 为 `8a4d37222dc221ca8c0fa1701968893b4d952d757f6b08aecbc5566ab2de833d`。原普通包、B 核、契约及历次失败不变。

1. 参数、形状和输入检查仍在授权前。新共享页在第一次输入传输前保留 IO 所有权并原子扣一次任务预算；不同映射不能重复领取同一额度。单个 `run.start()` 前紧邻检查撤销、活动位、请求代次、期限、健康新鲜度、上下文身份和预算，并只允许一次启动意图。原 RUNNING-before-start、超时、ERT 错误、精确 meta 与有限/尾部 Y 检查继续执行。
2. 只有确认完成、原有 meta/Y 验证和私有授权提交都成功后，才计 host verified completion 并复制调用方 Y。错误锁存撤销与 POISONED，不清除未知 IO/启动状态，不退款、不重试、不释放 BO；调用方 Y 不变。原公共 hardware counter 继续 null，host intent 不冒充硬件完成。
3. 权重上传使用同样 IO 保护，未确认完成的 BO 转由 context.pending 持有；旧局部变量退出释放的路径不再用于该派生候选。pending 声明顺序确保正常析构时先销毁 BO、再 device、最后 DeviceLock；POISONED 路径仍不允许 close/unload。
4. 页大小4096字节，使用对齐的 lock-free 64-bit 原子状态和同一 manager 的活 pidfd。attach 固定 parent PID/start ticks，取得同一 PID 的 pidfd 后再次核对，避免重认新父进程。上下文事实来自实际打开的 transport UUID、build、组、窗口及 IO BO 地址/大小，并包含 boot、worker start ticks 和每次 open 的随机 nonce；进程地址不作为代次身份。**这些是诊断绑定材料，尚不是独立设备代次审批。**

共享 RW 页仍假设可信受控 worker，不提供对恶意写者的隔离。PC fixture 的1秒健康上限只用于测试，未批准为板端安全参数。热路径检查不重新读取长前缀原件、全目录 SHA、完整 PSS/VMA 或每次 fsync；本轮未建立真实 PL 批量 grant manager，不能宣称已消除其 IPC 开销。

## 实际测试及边界

测试编译和链接的是派生实际后端，XRT 替身仅模拟 BO 传输/ERT/meta/control，输出固定零哨兵，**不是矩阵数学、Csim、FPGA 仿真或性能测试**。用例包括正常3次、共享72额度、重复任务/错误绑定/不同 worker/重开新 nonce、RO 页拒绝、无绑定拒绝、真实 manager 退出（无 IO/已保留 IO 两种）、输入/权重上传错误、许可后启动前撤销/代次/上下文/健康/期限/预算变化、启动异常/超时/ERT错误、完整原 meta 错误及非有限/尾部 Y、meta/Y 返回后撤销。

`start_entry_revoke` 故意在最后本地检查之后进入 start 的替身入口时撤销，实际记录一个 host start intent，结果拒绝、调用方 Y 不变、BO 所有权保留。**主机原子检查不能原子取消设备提交，不能承诺撤销后零 DMA 或自动安全释放。** 这条竞争作为预期风险证据保留，而非删掉该用例或改为成功输出。

最终 PC 与 sanitizer 构建均无编译警告；ARM 保留原 XRT API 的 deprecated 警告，未升级 SDK 或更换 API。A53 链接使用 `-mcpu=cortex-a53`，无 `-march=native`、PC test define 或 stub include；ELF 为 AArch64，公共导出保持原六函数及既有私有 completion extension。完整 portable gate 单独编译对象强制覆盖 attach/传输/启动/完成/撤销，避免把禁用 open 后的优化裁剪误当成全 gate 的 ARM 编译证明。64位原子使用 SDK 的 AArch64 原子助手，未引入 libatomic 锁式回退；这不是板端运行证明。

开发 v1—v4 的源码/构建/测试收据保留。独立审计首轮将用例总数误写为42而失败；实际两份不变清单均为41用例/839断言。修正审计计数后通过，原 FAIL、旧审计源码与说明保留，没有删除测试、放宽数值或资源门槛。

## 包和仍未完成的工作

候选包：`evidence/model_pl_A/20261026-pl-auth-binding-v1/pl-auth-offline-unbound-v1.zip`，SHA `f691ec88dcbf933afa109f5152100838fae100d97be97ee1b9b9772b6c6e520c`。仅含派生源、PC 控制替身、A53 UNBOUND 制品及小型合成 fixture；无权重、真 bitstream、原件长诊断或安装/上板脚本。原普通 `bundle-v2.zip` 的 SHA 仍是 `acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，仍为故障恢复且安全释放后首轮板测的基线，本候选不替换它。

**当前仍有无板工作，目标 active：** 真实 PL manager 协议/旧 router 序列通道兼容、继承页 writer 与有界批量 grant/请求 BEGIN-END、独立设备代次审批绑定、PL 窗口模式编排和端到端故障验证。现有 PC 模型 mode coordinator 仍仅适用于 CPU，不追认为 PL 可用。

为使未闭合部分不能被误用，A53 候选在 device_open 前硬返回 UNSUPPORTED；私有 attach 在非 PC 编译中同样 UNSUPPORTED，编辑 JSON 不能开启。BOARD 为 NOT_TESTED，SERVICE=false，CMA/板端时延收益均 null。没有新短提示词验收，不重新引入长前缀诊断；沿用原普通 R0/warm/hit 路径及安全门槛。

本轮复杂核心、设计、测试与证据验收未委派；未使用 DeepSeek，实际模型设置仍 unknown，不声称已切换。两个仓库治理 guard 均 exit0。
