# A11 实板数值、含搬运服务时间及正常恢复验收（2026-10-23）

结论：**PASS_WITH_LIMITATIONS**。独立窗口 `a11-mlp-20261023-v3` 完成冻结23次有效调用（手算1、尾块/双scale1、真实gate/up/down各7），另有一次T=0的非法参数检查，返回SP_BAD_ARGUMENT=1、输出保持哨兵、不可消费、无硬件提交。23份FP32实际Y逐份取回、核SHA并在本机独立重新比较，全部与冻结参考**逐字节一致**，最大绝对/相对误差0。原atol=1e-4、rtol=1e-5门槛保留。完整单次生命周期与计算后正常释放/恢复通过；A12未启动。

## 实际性能

| 算子 / N×K | T1 中位数 | T8 中位数 | T3 | 冷权重总加载 |
|---|---:|---:|---:|---:|
| gate / 3584×1024 | 5.263 ms | 16.764 ms | 8.567 ms | 56.795 ms |
| up / 3584×1024 | 5.268 ms | 16.753 ms | 8.594 ms | 56.788 ms |
| down / 1024×3584 | 5.109 ms | 15.257 ms | 6.935 ms | 56.720 ms |

T1/T8每形状各3次，T3各1次；表中中位数保留首个常驻调用，不删除样本。剔除首个常驻调用后的T1暖态中位数：gate 5.284378、up 5.278933、down 5.086416 ms（各2次）；T8均为常驻后调用。`AUDIT.json.performance` 包含全部样本、min/max和暖态组，不计算小样本p95。

服务时间包含激活量化、原生ABI输入复制/BO同步、参数设置/提交/完成轮询、meta同步校验、输出同步/数值保护和返回复制；冻结参考比较、诊断、许可等待、磁盘导出在计时外。冷权重总加载包含文件读取、调用方复制及原生加载；原生加载分别25.209/25.034/25.057 ms。每次调用的native细分时间完整保存；submit-to-completion是主机测量，不能称纯核周期时间。

真实权重复制约2 ms、sync调用约0.03 ms，后者不是PL读取DDR的有效带宽测量，不能据此导入design_budget或宣称几十GB/s。未测PL/DDR有效带宽、AXI字节、硬件周期、CPU同路径加速比均null。未运行额外优化或压力测试，不把单层服务时间换算为完整模型tokens/s。

## 先审查并修复的失败释放路径

此前引擎把所有错误统一停车。新路径只允许以下正常退出：open明确返回错误且未产生context；或已经确认READY、job/build/meta/完成数正确、BO范围/复用/账面及调用方保护字完整，但独立数值/量化比较失败。后一类保存原始Y和失败ledger，停止后续调用，获得独立`abort_close`父许可，依次unload/close；失败结果使用`FAILED_CLOSED_A11_MINIMAL`并据实际提交数记账，不宣称矩阵成功。管理器仍须waitpid(exit0)、完整FD/VMA扫描、refcount0、内核/健康门禁后才能普通卸载与恢复。

超时、POISONED、错误build/job、保护字异常、关闭失败、未知完成、内核异常或设备残留继续隔离，不kill、不强制卸载、不重放。新增可信failed-result验证协议与父许可规则，并在Linux真实子进程/flock/日志fixture中验证数值失败正常恢复，额外提交/假成功/身份篡改/残留VMA/refcount均拒绝。没有在板上故意制造挂死DMA，超时隔离验证域为PC。

代码：`platform/qwen35/a11/mlp_engine.py`、`manager_support.py`、`compute_result.py`、`prepare_compute_bundle.py`；标准打包入口`prepare_bundle.py`已指向新完整路径。派生管理器/边界独立存入`bundle-v2/`，原受保护A10/旧计算/原open包不改。复用原native ARM64库SHA `4d30d6dfb744aa47e0ce4a3faf5a6f685a1ee88fbeb6fe5c241c2dbed7990e38`，不改公共ABI/数学/核/驱动/内核。

## 验证和证据

- PC：旧契约、新配置各exit0；引擎14方法通过；完整恢复编排11方法通过；最终前置扫描断言1方法通过；修正后的包清单、标准入口与离线实板审计均exit0。真实量化与冻结参考复用，不用mock数值冒充BOARD。
- BOARD：boot `8422f92f-d01f-4849-ad19-6e66b640a9ad`，内核`6.8.12-a10irq2`，manifest `64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde`。实际23调用、5次权重加载，四IO BO始终复用，每个权重集合warm期间地址/handle不变，无重复上传；14为显式BO的主机创建计数，不是硬件完成计数。有效调用均由原生ERT完成、内核meta的build/job/状态/输出大小检查后返回，report中的per-call计数是host-seeded私有字段，不冒充全局硬件计数。
- worker17974、manager17873均正常exit0。释放前完整FD/VMA/refcount门禁通过，随后普通恢复默认PL/GDM并归档租约、释放双锁；生命周期约32.580秒（含管理/日志/许可，非算子时延）。74.899秒后独立读回扫描完整：FD0/VMA0、ZOCL absent、双锁无人持有、active lease absent、默认PL applied、FPGA operating、GDM active，worker/manager均已退出。
- 生命周期温度采样最高31.661°C；独立后验29.158–32.376°C。已有action-scoped overlay属性/IRQ枚举advisories保留；无新增未审查内核诊断。
- 证据：`readback-v3/actual-job-01.f32`至`actual-job-23.f32`、worker-result/完整stdout、lifecycle、kernel原文、review/profile/退出/独立state均逐文件hash取回；`audit_01.json`记录本机独立审计命令和exit0。`RESOURCE_ACCOUNTING.json`保留进程PSS/RSS/CMA与BO双账，不相加。

显式BO峰值charge为2162688字节（约2.063MiB），4MiB上限、8192对齐和逐BO低2GiB检查均执行；这不是隐式XRT/全系统/完整模型的物理峰值，物理BO峰值仍null。冻结vectors manifest内的旧proposed_allocation只是历史方案，实际资源以本次report/profile/账面为准。

## 保留的失败和限制

首次计算窗口v2在任何GDM/PL/核动作前被`verify_bundle`拒绝：新打包器按文件名排除manifest，误排除嵌套vectors/manifest.json。已修正为只排除根manifest，并在打包时真正调用verify_bundle。本地旧bundle和板端v2/exit1保留，未复用消费过的启动记录；新v3包全部校验后执行。首轮PC管理测试仅旧扫描事件名断言失败，改为检查真实不完整扫描被保留、两个完整观察先于修改；失败日志保留。初次只读preflight记录PROCESS_SET_CHANGED，未冒充完整扫描；执行入口有界重采并保留全部样本，正式维护仍使用严格门禁。

没有硬件integer-debug导出接口，内部整数和无法BOARD直接观察；FP32输出与独立参考bit-exact不冒充整数探针结果。仅小样本描述性服务时间，无p95/长稳/功耗/架构优化/完整模型PL通过声明。新板端故意超时/复位恢复未测，PC隔离测试与正常BOARD计算后恢复分域记录。仍使用当前已验证irq2启动，不改启动配置、不重启/刷写/升级，不提交或推送。

下一步：A11目标层数值与含搬运服务验收已完成；审查A12完整模型消费PL输出的独立前置与资源预算。本轮不自动进入A12，不将本次候选提升为生产默认。所有旧失败与A00—A17历史保留。
