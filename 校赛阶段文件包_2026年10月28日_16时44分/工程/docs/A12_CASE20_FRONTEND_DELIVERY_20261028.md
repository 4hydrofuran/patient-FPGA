# 二十例病例与前端最新更新（2026-10-28）

本次发布本对话已完成的二十例病例接入、有限口语短答、答案缓存优化、随机病例、下一场缓存调试和前端文字调整。发布基于已公开的A12实时短答分支，另建`codex/case20-frontend-updates-20261028`，不合并其他任务的本地修改。上传过程中不访问板卡。

## 当前实现

- 20例均为合成胸痛病例，清单7组，其中一组为信息不完整；不代表20种主诉或疾病。每例3条预写开场主诉。模型每轮接收当前问题对应的一至两个事实句，执行有限口语表达，不宣称基于整份病例自由问答或通过医学审核。
- 从20例服务端随机分配病例，刷新及请求重试保留当前场次。1320条答案目录来自真实目标模型CPU生成；缓存命中为MODEL_CACHE、actual_backend=null、model_called=false，保留原CPU来源。共享模型/公共前缀，不为每例复制模型状态。
- 下一场可以选择正常、命中或未命中；未命中绕过答案目录、实际调用当前后端。问诊中隐藏此设置。命中回答下方仅显示CPU/FPGA模式与缓存命中，未命中说明保持原样。
- 评阅按钮为“新病例”；问诊及评阅页面均隐藏病例随机抽取、下场随机抽取和每场从20例中随机抽取的提示。

## 源码和验证入口

最新网关：`platform/qwen35/web/integrated/B_601e69ca_A_case20_debug_20261027/web_gateway/`。其余case20及random派生目录保留为历史步骤。最新静态页面在该目录的`src/patient_web/static/`。准备脚本`cache_debug_prepare.py`读取这份最新源码。

病例：`system_qwen35/cases/`。接收来源固定为`12c29cee1a57e64d2cf5533b90d46959bf8e0733`；资料位于`data/patient_cases/chest_pain_20_20261027_v1/`。

缓存和真实生成证据：`evidence/model_pl_A/20261027-case20-natural-v1/full1320/`，目录SHA256为`b97871b7bd67252d63d4834544b323680824ce49dc4dcabc084cf124bf3ec79f`。历史失败试验保留，不重新生成缓存或改写原回执。

在已安装网关锁定依赖的Python环境，各测试分别运行，避免不同派生网关同名模块混用：

```text
python -B -m unittest bench.qwen35.web.test_cache_debug -q
python -B -m unittest bench.qwen35.web.test_case20_random -q
python -B -m unittest bench.qwen35.web.test_case20_natural -q
```

上传前复核：上述测试分别2、2、3项通过；历史契约检查及qwen35_config.py通过。Windows默认Python缺少FastAPI的两次测试导入失败已记录；实际成功复核使用已有WSL虚拟环境，没有安装或升级依赖。此前实板和真实浏览器证据见下列报告；本次上传未重新推理或板测。

- `docs/A12_CASE20_NATURAL_NOBOARD_20261027.md`
- `docs/A12_CASE20_RANDOM_BOARD_20261027.md`
- `docs/A12_CACHE_DEBUG_BOARD_20261027.md`
- `docs/A12_CASE20_DIVERSITY_AUDIT_20261027.md`
- 最新静态改动：`evidence/frontend_board_A/20261027-frontend-simple-adjust/board.json`、`20261027-frontend-case-hints/board.json`和`20261027-frontend-all-case-hints/board.json`。

实板运行/Owner记录是2026-10-27各自采样时的历史现场，上传时未确认服务仍在线。旧报告中“抽取新病例”和控件可见状态以本页最新说明及最后CSS为准。

本次提供源码、病例、答案目录及验证证据。准备/部署脚本依赖本机既有封存运行包，不能直接在全新检出目录重放板端授权或现场窗口。模型权重、许可证、凭据、系统镜像、预填充二进制状态和旧整包副本不纳入本次增量；原始发行包与其旧清单作为历史证据保留于本机。
