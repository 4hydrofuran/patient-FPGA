# A12 普通 R0/warm/hit 资源探测：无板交付

本分支上传本次代码、优化计划、验证记录和最终探测包；基于此前已发布的A10至今工程汇总。

- [完整交接](../../docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md)
- [最终探测包 bundle-v2.zip](../../evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip)
- [验证报告](../../evidence/model_pl_A/20261025-resource-probe-v1/REPORT.md)
- [最终复核](../../evidence/model_pl_A/20261025-resource-probe-v1/FINAL_REVIEW.json)
- [安全检查优化计划](../../docs/A12_SAFETY_CHECK_OPTIMIZATION_PLAN_20261025.md)
- [CMA验收调整](../../docs/A12_CMA_AWARE_ACCEPTANCE_ADJUSTMENT_20261025.md)
- [用户提供的许可检查建议](../../docs/references/A12_PERMISSION_CHECK_RECOMMENDATIONS_20261025.md)
- [本任务状态](../../docs/status/A12_RESOURCE_PROBE_20261025.json)
- [既有工程基线源码与证据](../a10-to-current-b-review-20261025/README.md)

21项Linux PC控制测试和实际x86 CPU模型R0/warm/hit流程通过；无原始诊断文件，worker正常退出。
CMA门槛98304 KiB、MemAvailable门槛1114112 KiB及前缀规划余量保持。使用旧冻结107/70/37-token输入。
原生ARM程序、库、B来源硬件和公共契约未改；首包保持原逐调用许可、健康及fsync。

最终ZIP SHA256：acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa。
ZIP含manifest、固定工具链产物和UNBOUND管理器；不含权重、凭据或原始音频/数值转储。

包默认PLAN_ONLY、无计算授权。当前故障恢复、安全释放、新鲜审查和单独授权/绑定后才可另行板测。
BOARD/CMA改善/板端时延均未测；完整数值和最终性能验收尚未完成，不宣称TTFT达标。

直接代码和证据保持原始字节，部分历史文档仍保留本地绝对路径；本页提供仓库内可访问入口。
重复的解包目录、初版ZIP、其他任务的shared-before快照和全局状态文档未重复上传；原件均留本地。
完整复现还需要既有工程依赖及本地固定模型资产，不能将源码片段当作独立完整构建仓库。
