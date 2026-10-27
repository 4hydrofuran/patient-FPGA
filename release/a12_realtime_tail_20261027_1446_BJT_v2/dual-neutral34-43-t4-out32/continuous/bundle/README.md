# A12 无板候选，未部署

这是 01—05 的本地候选，不是板端通过或默认启用证明。公共数学、B 核和旧 A11 原件不变。
ARM64 构建通过；ARM 执行、模型 PL 数值、内存峰值和速度均 NOT_TESTED。
PC_MATH_DOUBLE 真实运行 CPU 数学并验证图消费，不能记作 FPGA_REAL。

`python3 -B tests/selftest.py` 仅检查清单/哈希/禁用配置，不加载 ARM 库。
bin 中的模型进程可作为 S1（无 SP_A12_CONFIG）或经过新窗口审查的 S2 候选。
目标资产根固定 /opt/patient-qwen；原模型/sidecar 不复制到本包。依赖现有锁定资产和匹配系统库。
XRT 候选仅面向 2.18.0。所有库置于独立目录，禁止覆盖系统库或旧默认 manifest。

设备访问默认关闭。下一步须执行 A12 06：新鲜身份/平台/资源检查、同板 S1 与加载峰值验证。
Window/OwnedWorker 提供新租约、双锁、逐次许可与保留隔离机制；实际 PL 准备、默认恢复编排和 BOARD 生命周期仍须在后续窗口联调验收。
close/deadline 不 kill；POISONED 不 unload。普通恢复和完整资源门禁通过后才可归档租约；不复制旧 review/launch。
