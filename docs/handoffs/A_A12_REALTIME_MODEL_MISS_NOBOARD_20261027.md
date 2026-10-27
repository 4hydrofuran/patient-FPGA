# A12 实时模型未命中优化交接

最终候选realtime34-threads3-out32；真实浏览器25题中位879→618.3ms，23/25低于1秒；每题实际模型请求1、答案缓存命中0。
当前输入短表达+严格目标贪心验证，错草稿全清并重放。最终198组逐token/EOS/原checker通过，普通24、连续32/22320预算。
SOURCE-v3除main.cpp外保持旧源SHA，PC/ARM新二进制已构建；部署副本25题及正常退出0验证完成。
原24上限EOS失败与较慢no-space试验原件保留。未上板，板端时延/真实PL未命中/恢复释放/CMA功耗计数均NOT_TESTED/null。
完整报告docs/A12_REALTIME_MODEL_MISS_NOBOARD_SUMMARY_20261027.md；入口release/a12_realtime_model_draft_20261027_v1/START_HERE.md。
