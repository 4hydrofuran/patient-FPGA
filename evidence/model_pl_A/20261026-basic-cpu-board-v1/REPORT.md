# A12 板端CPU基础运行（2026-10-26）

结论：**一次实际ARM CPU模型生成及原内容检查通过；实时应用交付与PL验收未通过本轮验证。** 全部工作在用户要求的20分钟内结束，没有重跑模型。

已找到普通R0/warm/hit轻量方案，其交付入口仍为PLAN_ONLY/UNBOUND。现场内核为6.8.0-1036-xilinx，与PL候选要求的6.8.12-a10irq2不匹配；经用户选择，本轮改为明确的CPU基础运行，没有改变fpga_required配置或把CPU作为静默PL回退。

使用新上传包中的A53原生程序、既有Qwen3.5-0.8B权重及事实句提示词。原Session/planner选择合成病例SYN_CP_01的location事实，实际CPU加载72权重、完成936次后端调用；PL调用0。

- 问题：疼痛在什么位置？
- 模型原文：疼痛在胸骨后。
- 自然EOS=true，原内容checker=pass，活动状态已清理，进程退出码0，无存活遗留进程。
- 加载/就绪39.932秒；原生首token30.206秒，prefill30.182秒、decode8.752秒。后两者合计38.933秒，不能当作完整应用输入到交付时延。

验收脚本在模型返回后误读了不存在的`enabled`字段，原始记录保留为FAILED。CPU禁用PL的实际报告字段为`execution_kind=CPU_REFERENCE`。随后对同一份已保存结果，使用原planner/checker补核，生成独立REVIEW-v2.json；没有改写原失败、没有再运行模型，也没有补造实时Session交付成功。

板端原始结果：`/home/ubuntu/a12-resident-basic-20261026-v1/run-v1/RESULT.json`，补核为同目录`REVIEW-v2.json`，原生stdout/stderr同目录保留。本机摘要为本目录RESULT.json，串口原件为cpu-run-uart.json及review-uart.json。

本轮没有重启、切换内核、加载PL、修改原模型权限或执行长诊断。未知PL性能、优化私有管理链及生产/医学验收均未因本次CPU运行追认。
