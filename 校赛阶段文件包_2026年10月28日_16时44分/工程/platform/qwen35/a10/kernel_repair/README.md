# A10 IRQ 生命周期修复候选（仅电脑）

最新（2026-10-19，覆盖下方旧快照）：完整内核/配套修复ZOCL/模块审计/FIT候选与独立回读已通过电脑检查，`PC_BOOT_CANDIDATE_NOT_BOOT_TESTED_NOT_DEPLOYABLE`。用户已关机，本轮无板连接；电脑构建总时限取消，板端安全约束不变。新驱动独立源码在`platform/build/a10-driver-irq-repair-20261019-v1`；内核/模块/initramfs/FIT在私有WSL `.../a10-kernel-full-20261019-v1/boot-candidate-v2`。暂存漏签名及缺dtc失败保留，修复后6218模块/6127签名检查通过，91 staging按原策略不签名。原启动用户空间和KV260 DT保留。完整证据见 `evidence/board_platform/A10_20261018_intake/DRIVER_AND_BOOT_CANDIDATE_PC_REPORT.md`；这些不是部署指令，不改板上默认启动。

状态：`PC_SOURCE_CANDIDATE_NOT_BOOTABLE_NOT_BOARD_ACCEPTED`。
当前候选：`platform/build/a10-kernel-repair-20261019-v2/`。不是可刷写镜像，不得上传后当模块 insmod，也不得覆盖板上内核。

2026-10-19后续：完整Ubuntu源树的Image/modules/dtbs在私有电脑目录构建中，独立release `6.8.12-a10irq1`，未部署。新增原启动包备份/CRC解析、只读FIT提取和initramfs清单；内存临时网络已获用户授权并核验Unsaved。完整命令/退出码及新增驱动IRQ上下文风险见 `evidence/board_platform/A10_20261018_intake/KERNEL_FULL_PREPARATION_REPORT.md`；最终构建结果以 `kernel_full_build_01.json` 为准，不把预留凭据当成功。原启动数据只存platform/local，不分发；签名私钥留WSL私有目录。

范围固定为 Ubuntu `linux-xilinx 6.8.0-1015.16` 的三个源文件：

- `drivers/of/irq.c`：extended 解析临时引用、解析后创建映射的引用释放。
- `drivers/irqchip/irq-xilinx-intc.c`：卸载遍历以固定 `nr_irq` 为界，避免 `mapcount` 随释放缩减或稀疏映射漏清理。
- `drivers/irqchip/irqchip.c`：experimental probe 的父节点引用由 devres 管理，处理分配失败、自引用、延迟探测及正常解绑。

`prepare.py` 校验源 SHA、拒绝复用输出目录，保存原文件、候选文件、补丁和 manifest。旧候选 v1 保留。数学、HLS、模型、语音、频率和内存预算均未修改。

## 工具与证据

- `test_prepare.py`：生成器拒绝/范围测试。
- `generate_harness.py`、`harness.c`、`parent_harness.c`、`run_native.sh`：从实际源提取函数，在 PC stub 环境复现旧缺陷并验证候选。原版 PASS 表示成功复现缺陷，不表示原内核正常。
- `prepare_arm_objects.py`、`Kbuild`、`build_arm_objects.sh`：精确头文件配置下编译三个完整 ARM64 翻译单元；不是完整内核链接或板测。
- `check_patch.sh`：正反向 dry-run 和 SHA 核验，不改源。

在 Windows 工程根 `C:\Patientqwen` 使用 `platform/local/a1/venv/Scripts/python.exe`；交叉编译与 native 检查使用 WSL `KV260-A-2204`。完整命令/退出码保存在 `evidence/board_platform/A10_20261018_intake/kernel_repair_*.json` 的 `argv` 字段。脚本目前锁定此次输出目录；如复测，应显式选择新的输出目录和记录文件，不能删除/覆盖旧证据。没有必要重复已有效的检查。

## 不可越过的边界

电脑 stub 不模拟真实设备核心、并发 IRQ、DMA 或 MMIO；没有证明在途任务可安全卸载。未改屏蔽中断的顺序，不通过故意挂死实板来验证恢复。候选仍需审查正常静止条件下的生命周期，并完成全内核、配套模块、FIT 与可回退启动验证。

详见 `ROLLBACK_PLAN.md` 和 `evidence/board_platform/A10_20261018_intake/KERNEL_REPAIR_PC_REPORT.md`。A10 未通过；用户取消的数值回归不会恢复执行。
