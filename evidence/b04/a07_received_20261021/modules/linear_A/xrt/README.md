# A07 XRT 后端：无板验证与部署门禁

2026-10-04：B double实际核已通过A06离线接收；当前应用仍默认CPU。本库的 `config.pending.json` 必须在设备发现之前返回 `SP_UNSUPPORTED`，因为没有已验证的部署 profile，且 `allow_device_access=false`。核接收不等于板卡可用，不要为了测试填写虚假的BOARD_VERIFIED。

## 已实现与验证层级

- 六个 `sp_linear_v1` C ABI，所有异常留在库内；权重只在 load 时校验/复制/同步，BO 持有所有权，没有另一套完整 CPU 权重副本。
- 持久 device/kernel/run、最多一个 in-flight、预分配 X/Sx/Y/meta 池；run 不重新分配或同步权重。Xq/Sx 各自取实际 `kernel.group_id`，不把共享 bundle 当一个 BO。
- 公共 W4/Sw/A8/Sx、pad、shape/字节长度检查；每个 BO 的实际地址/大小必须落入到板验证后的参数地址窗口。预算、地址窗口、group_id 不从物理 4GB 推定。
- meta 采用候选 40B 私有布局，BO 至少64B；17参数类型/顺序来自已有 A06 候选映射。实际 XO 到达还须重新核对，不能用这份代码替代 A06。
- 有限主机轮询、job/build/magic/status/done 校验、完整有限输出与 N 尾部检查后才复制给调用者。任何启动后错误使 ctx POISONED；run/load/unload/close 拒绝继续，资源和排他锁保留，没有“超时即释放”和静默 CPU 回退。
- `hardware_done_count/cycles/measured_bus_bytes` 为 null。B 私有 count 每次用 host seed=0，核应回写1，只作回显一致性，不冒充累计硬件计数。

PC主机规则970项及真实归档meta66笔/396篡改检查保留。新增29个完整C ABI控制替身场景、554检查及相同ASan/UBSan通过，实际链接生产backend.cpp；替身只模拟传输与故障，绝不计算矩阵或表示真实XRT设备。测试报告execution_kind=null且public_metrics_eligible=false。真实SDK Cortex-A53库/独立host交叉构建通过、6导出/9依赖及生产替身隔离已核对。**真实设备BO/sync/kernel/超时恢复、ARM执行和BOARD仍NOT_TESTED。**

## 尚不可越过的门

1. B 实际包接收、源码/XO/内嵌 metadata 与仿真闭环，A06 才可填 accepted/frozen 及 kernel_build_id。
2. A07 真实 v++ 链接/布局布线，产出匹配 xclbin、UUID、参数 group/地址拓扑。
3. A10/A11 到板实测启动、设备身份、可见内存、合法 BO 范围/预算、恢复与租约，才可生成 BOARD_VERIFIED profile；用户允许后才 enable device access。不能把生成配置当板测。
4. A12 将模型显式接入此库并验证实际输出消费；当前 A05 Bridge 仍只连 CPU。

部署 profile 需要：status、source_xo_sha256、xclbin_sha256、xclbin_uuid、kernel_build_id、device_index/name、verified_bo_budget_bytes、bo_charge_alignment、argument_groups[6]、argument_address_windows[6]（base/span）。这些是本库私有受信配置，不新增公共协议。当前没有 profile，所有物理预算为 null。

## 故障与局限

没有自动 unpoison、reset、abort、刷写或卸载路径。调用者必须保持故障进程/动态库资源，不得在未知 DMA 状态下 dlclose/杀进程并宣称安全恢复。真实恢复流程留板端验证。

轮询避免直接把 SDK 的 wait(timeout) 当硬时限；但 state/sync/驱动本身阻塞的情况尚未实板验证，**不是硬实时 deadline 保证**。SDK 的 device.load_xclbin/kernel(device,uuid,...) 在 2.23 仍可链接，但给出 deprecated 警告；保留告警，未擅自改变匹配平台的装载路线。

头文件/接口依据：已安装2026.1 SDK `usr/include/xrt/`，以及 [AMD XRT Native C++ API](https://xilinx.github.io/XRT/master/html/xrt_native.main.html)。实际编译以本机 SDK 头文件为准，不以网页 master 代替固定版本。

当前增量证据入口：`evidence/A07_closeout/20261004-v1/`。旧 `evidence/A07_independent/preboard-v1/REPORT.md` 与 `evidence/A07_B04/v1/REPORT.md` 保留历史失败与通过范围。目标链接的最终结论另见当前增量报告，不由本README推断。未复制任何模型/语音权重。
