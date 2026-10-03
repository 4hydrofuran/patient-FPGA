# A07 XRT 候选：无 B 实物、无板准备

当前不是默认后端，不是已验收核。`config.pending.json` 必须在设备发现之前返回 `SP_UNSUPPORTED`，因为现有 `KERNEL_SOURCE.json` 的 accepted/frozen 为 false；无已验证部署 profile，也未允许设备访问。不要为了测试改这些字段。

## 已实现与验证层级

- 六个 `sp_linear_v1` C ABI，所有异常留在库内；权重只在 load 时校验/复制/同步，BO 持有所有权，没有另一套完整 CPU 权重副本。
- 持久 device/kernel/run、最多一个 in-flight、预分配 X/Sx/Y/meta 池；run 不重新分配或同步权重。Xq/Sx 各自取实际 `kernel.group_id`，不把共享 bundle 当一个 BO。
- 公共 W4/Sw/A8/Sx、pad、shape/字节长度检查；每个 BO 的实际地址/大小必须落入到板验证后的参数地址窗口。预算、地址窗口、group_id 不从物理 4GB 推定。
- meta 采用候选 40B 私有布局，BO 至少64B；17参数类型/顺序来自已有 A06 候选映射。实际 XO 到达还须重新核对，不能用这份代码替代 A06。
- 有限主机轮询、job/build/magic/status/done 校验、完整有限输出与 N 尾部检查后才复制给调用者。任何启动后错误使 ctx POISONED；run/load/unload/close 拒绝继续，资源和排他锁保留，没有“超时即释放”和静默 CPU 回退。
- `hardware_done_count/cycles/measured_bus_bytes` 为 null。B 私有 count 每次用 host seed=0，核应回写1，只作回显一致性，不冒充累计硬件计数。

PC 单测直接执行生产使用的 host_contract/release_gate 函数（包括 ASan/UBSan）；meta 是明确合成的字节校验样例，不调用假的 HLS/FPGA。XRT 整库只完成真实 SDK 的 ARM64 编译/链接，**没有执行 BO/sync/kernel/timeout/释放操作**。库中未来 FPGA_REAL 报告不会被无设备测试生成。

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

证据入口：`evidence/A07_independent/preboard-v1/REPORT.md`。构建产物只是本地 staging，未发布或复制任何模型/语音权重。
