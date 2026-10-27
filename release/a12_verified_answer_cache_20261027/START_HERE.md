# A12 核验模型答案复用：无板交付

已按用户授权完成方案C0～C5。默认候选为 [hybrid34-threads2](hybrid34-threads2/START_HERE.md)：固定病例答案命中时复用真实模型原文，未命中继续原NativePL；本轮未部署或访问板卡。

| 实际同机浏览器25题 | 原v2实时CPU模型 | 新核验答案复用 |
| --- | ---: | ---: |
| 完整核验答案绘制中位 | 875.0ms | **42.3ms** |
| 最快/最慢 | 755.0 / 1630.1ms | 29.5 / 69.8ms |
| 低于1秒 | 按逐题回执 | **25/25** |

逐题配对减少时间中位835.8ms；双方输入、病例、输出一致，使用真实HTTP/SSE和真实Edge绘制观测。新路径每问仍重新路由、检查事实、发布新回执和评分。以上为开发机结果，板端数值未测。

198/198条均来自实际Qwen CPU贪心生成并通过原checker/EOS，目录约686KiB；每条UI标记“已核验模型答案·缓存”。MODEL_CACHE的本轮model_called=false、actual_backend=null，原CPU生成来源另存。缓存模式不声称本轮PL推理。

产品ZIP与逐文件SHA见 [ARCHIVE.json](ARCHIVE.json)；具体改动见 [CHANGES.json](CHANGES.json)。执行与失败修复、全部命令/退出码见 [报告](../../evidence/model_pl_A/20261027-verified-answer-cache-v1/REPORT.md)。完整方案为 [10小时方案](../../docs/A12_VERIFIED_ANSWER_CACHE_10H_PLAN_20261027.md)。

源码、测试、方案和本轮原始证据另存 [工程增量包](a12-verified-answer-cache-engineering.zip)，摘要见 [ENGINEERING_ARCHIVE.json](ENGINEERING_ARCHIVE.json)，逐文件清单见 [ENGINEERING_MANIFEST.json](ENGINEERING_MANIFEST.json)。工程包用于现有仓库接续，不含模型权重、工具链或板端执行授权；部署使用前述产品ZIP。

现有WSL环境的离线依赖/目录检查（不会启动Owner、模型或设备）：

```sh
cd /mnt/c/Patientqwen
/home/member-a/kv260-build/a12-fast-response-20261027-venv/bin/python -B release/a12_verified_answer_cache_20261027/hybrid34-threads2/continuous/fast_response_verify.py --domain PC --bundle release/a12_verified_answer_cache_20261027/hybrid34-threads2 --suite package
```

包内START_HERE提供下一次独立Board窗口的启动、停止和回退命令；只有另行获实板授权后才运行。旧纯实时34/70包保留于 `release/a12_fast_response_20261027_v2/`，正常停止/释放后可在新窗口回退。

实际验证：39网页测试、15浏览器协议回归、198个真实来源及198组原planner输入复核、1次真实CPU未命中、7策略零模型、同场20分/上下文追问/10场归档通过；部署副本额外完成真实浏览器25题和正常worker exit0。

本聊天后续推理配置已通过支持的接口设为gpt-6.1-sol/High，UI核实为“高”；此前阶段和单次执行参数未追认。未推送、未改HLS/公共ABI、未全局升级依赖。BOARD、实际PL未命中/硬件恢复、CMA/功耗/硬件计数与板端时延仍NOT_TESTED/null。
