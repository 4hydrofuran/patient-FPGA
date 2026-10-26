# 当前默认病人提示词变更（2026-10-25）

用户最新明确要求已应用于system_qwen35/app/checking.py：

```text
<|im_start|>system
你是模拟病人。用1—2句说完事实，保留是否和不清楚。<|im_end|>
<|im_start|>user
学生问题：
```

默认facts_v4继承上述system；问题原文、事实载荷和宿主数值/单位/肯否/未知检查保持。43项既有PC测试通过，25组应用文本已离线重新生成。新token数、模型质量及性能尚未验证。没有部署到板端，也没有改变失败现场。

证据：evidence/model_pl_A/20261024-ttft10-01-v1/prompt-short-20261025-v1/REPORT.md、AUDIT.json、PAYLOADS.json；命令记录位于同任务logs/prompt_short_*.json。

后续新窗口必须重新分词并派生新前缀/缓存身份/调用预算。旧TT10-00与v3包仍冻结为旧提示词；它们的70-token快照与通过项不能用于新文本。现有tt10_01_common.config及历史打包器继续用于旧输入复现，不代表已适配本次提示词；不得直接重跑历史目录写入脚本。当前新PAYLOADS不含token列表，不能直接发送执行。

TT10-01未完成，整体BOARD不通过，PL普通应用TTFT保持null，≤10秒未验证。当前板端隔离现场保持。此前CMA原因分析和读取端候选修复方案仍属分析/设计，没有因本次文字修改而解决。
