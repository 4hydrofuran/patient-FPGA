# A10 工程与证据交付（2026-10-23）

结论：**PASS_MINIMAL_WITH_LIMITATIONS**，仅用户批准的安全精简 A10。
不是原 20 长度/1000 次回归通过，不是 A11/A12、全模型 FPGA 或长期稳定性验收。

本次打包前正常关机已完成：串口实际收到 `reboot: Power down`，COM5 已释放。
用户可以拔下圆头 12V 电源。本次关机未加载驱动/位流、未计算、未重启或强制复位。
原始关机日志保留了 USB U1/U2 与 display 注销提示；不声称零告警。
当前关机状态优先于历史报告中“仍上电、GDM active、临时 IP”的窗口末快照。

## 包内入口

- `project/evidence/board_platform/A10_20261023_isolated_single_v1/REPORT.md`：完整方法、真实命令、退出码、分域结果与限制。
- 同目录 `A10_ACCEPTANCE.json`、`board_profile.json`、`resource_ledger.json`、`audit_01.json`：验收、环境、内存双账、独立审计。
- 同目录 `result_readback_01/`：原始计算、资源、生命周期与内核记录；旧失败没有删除。
- `project/platform/qwen35/a10/`：工程源代码、保护门禁、测试、审计与暂存工具。
- `project/platform/local/a10-isolated-single-20261023-v1/`：实际核验的 21 文件冻结包，包括修复驱动、vector-add 位流/设备树/xclbin与隔离控制器。manifest SHA256 `ae21f1acacadbf5ceaeed85384cade0c575fbe8a5a88012530c911ebfce7cfb7`。
- `project/A10_refcount_交付包_20261023/A10_refcount_handoff_20261023/`：对方交接源码和可公开文本证据；非入选二进制见 EXCLUDED。
- `project/evidence/board_platform/A10_20261023_shutdown_publication/`：本次短时只读检查和正常关机回执。
- `project/docs/handoffs/A_A10_MINIMAL_COMPLETE_20261023.md`：后续 B/C 接入边界。

`project/` 对应当前工程根目录，恢复时不要额外套一层 project。包不是系统镜像或一键部署安装器。
测试脚本/历史 boot ID、PID、租约和执行窗口均不能直接重放；下次运行需重新确认现场与授权。
冻结包内 `board_accepted:false` 是构建当时的不可变状态；最终本次最小验收以 A10_ACCEPTANCE.json 为准，不回写冻结包。

## 已完成

一次真实 32 元素 vector-add 正确，4080 保护字正确；3×16448 字节 BO，metadata group=3/3/3。
独立子进程正常退出后，完整 FD/VMA/refcount 检查通过，普通卸载测试配置和驱动，恢复默认 PL/GDM，独立延迟读回通过。
整个控制流程约 15.228 秒，最高采样温度 32.624°C，不是压力测试或性能基准。
本次新流程 27+7+10=44 个电脑测试方法通过；不能算作 44 次板测。
既有空载和原系统恢复证据复用；另一个人的历史计算和失败分开保留。

## 未完成、取消和限制

1. 20 长度/1000 次数值回归已由用户取消，不补跑、不记通过。
2. 长时间稳定性、压力、最大 BO/全地址空间、功耗、持续带宽、在途 DMA 故障注入均未实施；3200 MiB 整体模型包络仍未证明。
3. 软件 reboot 可靠性仍未验收；本次正常 poweroff 成功不证明 reboot 可靠。历史 Oops/卸载失败/关机阶段提示保留。
4. 本次通过环境为 `6.8.12-a10irq2` + XRT 2.18.0；原默认 1036 启动包未改。下次正常开机不保证自动进入 irq2，不能把这个驱动直接加载到原内核。
5. A11 真实 MLP 核验收、A12 模型消费 PL 输出及整机性能未完成。下一步仅建议先做 A11 电脑侧兼容审查。

## 完整性与发布

MANIFEST.json 记录每文件来源 SHA256、发布 SHA256、字节数及是否脱敏。
源代码与冻结包保持原字节；部分历史 JSON/日志中的敏感字段仅在发布副本脱敏，原件不改。
因此历史 seal/manifest 中的源哈希可能不等于脱敏副本，需使用发布 MANIFEST 的显式映射，不能宣称脱敏文件仍是原始字节。
PACKAGE_CHECK.json 记录 ZIP 回读/CRC、文件数、SHA256 和扫描范围。扫描不构成不存在任何秘密的绝对保证。
不包含密码、许可证、私钥、操作员 known_hosts、系统/SD/QSPI/WSL 镜像、模型/语音权重；详见 EXCLUDED.json。
发布到独立分支 `a/a10-minimal-complete-20261023`，保留旧交付分支；不覆盖 main，不改当前工作分支或现有暂存区。
