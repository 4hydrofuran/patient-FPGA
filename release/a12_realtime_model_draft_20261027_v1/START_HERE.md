# KV260 Qwen3.5 A12：实时模型未命中优化（2026-10-27，v1）

推荐下载总包：[KV260_Qwen35_A12_RealtimeModel_VerifiedDraft_NoBoard_20261027_v1.zip](KV260_Qwen35_A12_RealtimeModel_VerifiedDraft_NoBoard_20261027_v1.zip)，约37.3MiB。内含Deployment、EngineeringIncrement、中文总结和校验清单；两个子包的区别见总包README。

[中文总结](../../docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md)说明实际改善、完整性、资源、失败尝试及使用方式。新鲜真实浏览器25题，完整核验答案中位879.0→618.3ms，23/25低于1秒；部署副本复测622.8ms。每题实际运行模型，答案缓存命中0；中性34-token KV前缀仍复用。198组最终输入逐token/EOS/原checker通过。

默认候选realtime34-threads3-out32：3线程、原checker短表达、严格目标贪心验证。连续32输出/22320保守额度覆盖验证与完整重放；ordinary仍原24。旧缓存目录保留原生成来源，不冒充新推理。

从Deployment解压目录的START_HERE开始，先做PC package检查；现有模型资产和依赖仍需本机提供。ARM已显式按2026.1 SDK/cortex-a53构建；新BOARD时延、真实PL未命中、硬件恢复/释放、CMA及功耗计数仍NOT_TESTED/null。另获实板授权后才能执行包内BOARD命令。

[SHA256SUMS.txt](SHA256SUMS.txt)与[ARCHIVES.json](ARCHIVES.json)提供总包及子包摘要。仓库主下载是总包，子包位于其packages内；本地同目录也保留两份子包，方便复核。工程源码及证据在仓库原路径直接浏览。旧交付均保留。
