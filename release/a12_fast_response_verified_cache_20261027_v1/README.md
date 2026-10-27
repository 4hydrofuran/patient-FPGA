# A12 快速响应与核验答案缓存：2026-10-27 无板交付 v1

[中文总结](../../docs/A12_FAST_RESPONSE_VERIFIED_CACHE_NOBOARD_SUMMARY_20261027.md)说明用途、实际改善、验证范围、资源成本、包的区别和后续实板工作。

| 文件 | 选择方式 |
| --- | --- |
| [KV260_Qwen35_A12_FastResponse_VerifiedCache_NoBoard_20261027_v1.zip](KV260_Qwen35_A12_FastResponse_VerifiedCache_NoBoard_20261027_v1.zip) | **推荐下载**；含总结、缓存部署候选、两个阶段工程源码/测试/证据及逐文件清单 |
| [KV260_Qwen35_A12_LiveModel_Short34T2_NoBoard_20261027_v1.zip](KV260_Qwen35_A12_LiveModel_Short34T2_NoBoard_20261027_v1.zip) | 纯实时模型34-token/2线程候选，逐问运行模型 |
| [KV260_Qwen35_A12_LiveModel_Legacy70T2_NoBoard_20261027_v1.zip](KV260_Qwen35_A12_LiveModel_Legacy70T2_NoBoard_20261027_v1.zip) | 原70-token/2线程独立回退候选 |

校验见 [SHA256SUMS.txt](SHA256SUMS.txt)，机器可读信息见 [DELIVERY.json](DELIVERY.json)。三个ZIP均已CRC/SHA回读；改名没有修改原部署或工程ZIP内部字节。总交付包解压后先读README_zh-CN.md，再按用途选择Deployment或EngineeringIncrement，工程按Stage01→Stage02接续。

实际同机真实浏览器25题，完整核验答案显示中位875.0→42.3毫秒，缓存25/25低于1秒。198条均由实际CPU模型生成并核验；每问重新路由、核验和评分，页面标明缓存来源。未命中走原模型路径。该结果属于开发机缓存命中，不能作为实板或模型本身计算加速的结论。

源码可直接浏览仓库platform/qwen35/web、system_qwen35/app及bench/qwen35/web；详细原始证据在evidence/model_pl_A/20261027-verified-answer-cache-v1。当前部署候选UNBOUND，无模型权重或执行授权。板端可见时延、真实PL未命中、Owner恢复/释放仍NOT_TESTED。
