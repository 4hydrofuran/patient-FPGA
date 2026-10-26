# A12 本对话已完成工程交付（2026-10-26）

本次仅发布本对话已完成的工程、说明及其依赖/失败证据。上一条关于首token小于10秒的后续优化建议未纳入，也没有把建议写成已实现功能。

| 内容 | 实际状态与入口 |
| --- | --- |
| 普通PL验收及授权修复 | [最终报告](../evidence/model_pl_A/20261026-pl-authfix-board-v2/REPORT.md)：真实R0/warm/hit通过，2880次权限提交；完整核验应答60.71→27.85秒，单组样本；首token16.97秒，未达10秒 |
| 可复用普通探测包 | [bundle-fixed-v2.zip](../evidence/model_pl_A/20261026-pl-authfix-board-v2/bundle-fixed-v2.zip)：修复授权绑定、应用适配器导入和瞬时扫描中止；保持UNBOUND，授权不随包交付 |
| 无板常驻候选 | [收口说明](A12_PARALLEL_PREBOARD_CLOSEOUT_20261026.md)、[交接](handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md)、[PC入口](A12_RESIDENT_PC_CLI_USAGE_20261026.md)：无板验证与A53制品准备完成，候选仍未板测 |
| 短提示词私有链前件 | [交接](handoffs/A_A12_FACTS_ONLY_PRIVATE_ROUTE_PC_20261026.md)：保留原PC证据与封存包，不追认为BOARD通过 |
| 文件传输和CPU基础运行 | [CPU报告](../evidence/model_pl_A/20261026-basic-cpu-board-v1/REPORT.md)、evidence/model_pl_A/20261026-upload-only-v1；CPU结果不替代PL验收 |
| 原PL失败与关机记录 | [失败报告](../evidence/model_pl_A/20261026-original-pl-board-v1/REPORT.md)、同目录shutdown.json；历史现场描述以各自记录时间为准 |
| 本次测试中的失败 | [v1记录](../evidence/model_pl_A/20261026-pl-authfix-board-v1/REPORT.md)、最终报告中的失败说明；旧失败、未知退出码与租约归档证据保留 |

最新板测结束时worker和管理器退出0，默认PL/GDM恢复，ZOCL卸载，活动租约为空。此为验收结束时的已记录状态，不是发布时重新访问板卡所得。整体A12、医学、长期稳定性及生产启用未完成。

源码包括A12工程及其既有运行时/应用依赖；依赖文件随包提供不表示本对话重新实施或验证了所有历史模块。原模型权重、开发机工具链、凭据、许可证和系统镜像不在交付范围。

当前汇总见[范围状态](status/A12_CHAT_COMPLETED_20261026.json)，完整文件清单及字节摘要见[发布清单](../release/a12_chat_completed_20261026/MANIFEST.json)。历史封存文档中NOT_TESTED和当时现场原样保留，最新结论以本页链接的最终PL报告为准。
