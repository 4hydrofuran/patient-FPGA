# KV260 Qwen3.5 A12 实时模型长尾优化，无板交付 v2

版本冻结：2026-10-27T14:46:17.748279+08:00（北京时间UTC+08，文件名精确到分钟）。封包开始：2026-10-27T14:50:34.296560+08:00。

推荐总包：KV260_Qwen35_A12_RealtimeTail_DualPrefix_NoBoard_20261027_1446_BJT_v2.zip。内含两个子包：

- packages/KV260_Qwen35_A12_RealtimeTail_DualPrefix_Deployment_NoBoard_20261027_1446_BJT_v2.zip：独立部署候选。解压后从dual-neutral34-43-t4-out32/START_HERE.md开始，先做PC package检查。需要现有模型资产和依赖。
- packages/KV260_Qwen35_A12_RealtimeTail_DualPrefix_EngineeringIncrement_NoBoard_20261027_1446_BJT_v2.zip：工程增量源码、测试、真实命令与证据、既有v1相关参考材料及本轮中文总结。仓库基线为e7a76cb0d60ae087f796c98fcb10def74733042b。

总结：A12_REALTIME_TAIL_NOBOARD_SUMMARY_20261027_1446_BJT_v2.md。三个独立热服务窗口75题均低于1秒，冻结副本另25题复测；均每问真实运行CPU模型，未加载答案缓存。这里只报告开发机x86数据。双前缀34/43-token与4线程用于连续候选，评分值仍实时输入；未改原checker、评分、模型或native二进制。

文件名规则：项目_阶段_功能_内容类型_NoBoard_YYYYMMDD_HHmm_BJT_v2.zip；日期时间表示本次版本冻结，测试起止另见总结，实际上传时间见仓库PUBLISH_RECEIPT.json。

BOARD为NOT_TESTED/null；实板操作按部署包中已有入口和专项授权执行。旧v1包可独立回退。模型权重、SDK、镜像、凭据及可重放执行授权不随包提供。
