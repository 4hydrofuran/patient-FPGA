# 前端 Python 接入已准备，等待本轮 PL 验收交接

用户在本聊天明确授权：板卡正在被 PL 验收与修复占用时等待；可读取时读取实际接口并匹配，先修改本地代码；验收通过后立即开始板侧前端接入。本轮目前只有本地操作，没有打开 COM5、SSH、HTTP 板卡接口或执行板端命令。

本地实现：`system_qwen35/app/web_managed.py`。`create_app/serve` 接收既有 BOARD NativePL、真实 readiness 回调及 remaining_seconds 回调，复用已安装的 patient_web.managed。不创建 Owner/worker/BO，不修改 NativePL、HLS/XRT、公共契约、前端冻结参考、病例或评分。不从 JSON 自动启用计算。网页退出仍由 PS 原流程收尾。

当前 Owner.expires 是 monotonic ns；示例剩余时间为 `(owner.expires-time.monotonic_ns())/1e9`。180 秒网页预算内有足够剩余时间才接受新问题，原 Owner/worker 许可与健康服务必须继续工作。这个轻量适配只读取现有内存状态，没有加入额外内核/设备扫描。

提示词决定：保留网页的冻结长版本。读取当前在修复的普通 PL requests.json 发现，它也使用该长版本；此前当前 PC checking.py 的缩短 system/问题前缀不是这轮实板基线。因此不在前端接入时偷偷换提示词。

本地测试在既有 WSL KV260-A-2204 的 Python 3.10.12/Jinja2 3.0.3 执行：7 项通过，实际 NativePL 类及已接收 CorrelatedPL 类参与，但 worker 是明确的协议替身，未跑模型、ARM 或 PL。覆盖请求关联/R0状态、Owner 未就绪零提交、剩余预算不足零提交、错误预算拒绝、原生错误保持、安装前端工厂接线及 CPU/PC fixture 身份拒绝。首轮测试模板被 Jinja 去掉最后换行，1 error/1 failure 保留说明；只修测试模板，最终源码重测7项通过。历史契约和新版配置检查各exit0。

独立准备包：`evidence/frontend_board_A/20261026-integration-prep-v1/overlay-v1.zip`，4746字节，SHA256 `3cb140a0bcf591e3f5a4dcef5ac1165fa9c531614614000f7e5b50ac56aad780`。准备命令 `python platform/qwen35/web/prepare.py --output evidence/frontend_board_A/20261026-integration-prep-v1/overlay-v1`，exit0。包仅含 Python 适配器、未绑定配置、说明及摘要，未部署。PC命令/输出见同目录 PC_CHECKS.json。

现场接口边界：当前普通资源测试是固定 R0/warm/hit 三请求窗口，不能在正在运行或已用完的窗口后追加网页请求。新版 resident BoardService 的 session/submit/ack 与 NativePL.generate 不同，且 resident 实板未验收，本包未把它假装成 NativePL。验收通过后，先读取实际获准运行接口，再在独立网页窗口中绑定；如实际接口发生变化，更新本地适配与对应测试后部署。普通基线通过不自动等于 resident 候选通过。

跟随的现有聊天：`优化PL验收安全检查耗时`，thread `01a1720f-fe0d-7582-b8ae-743e190835c3` / local。只读取其紧凑 wait_threads 状态，不获授权就不向它发消息。最近游标 `967f3b5b-6e71-4082-a14a-2cad9c33072f:3`。目前该任务仍 active，正修复/恢复，并非板卡交接。

本地旧 RESULT.json 仍为 `FAILED_PL_ACCEPTANCE_ATTEMPT`、manager_exit_code=null、active_lease=true、zocl=true；这只是旧失败快照，不能视为持续现场状态，也不能据其改变当前板卡。跟进时读取新结果/新交接；目前不得进入板侧前端部署。

继续条件：本轮真实普通 PL 验收产生通过证据，例如 `PASS_ORDINARY_R0_WARM_HIT_BOARD` 且 manager_exit_code=0、ordinary_pair_equal=true、platform_restored=true、active_lease=false、zocl=false，原任务确认完成释放/交接，且没有新任务再次占用。线程完成或磁盘上出现 PASS 字样单独不足。复用该任务已有结果，不为网页再增加一套硬件验收。

届时用户已授权直接开始接入：使用新的独立覆盖目录，不覆盖原前端/验收包；复核实际 Python/NativePL/managed 接口，接入真实回调和新窗口，先一问一评检查 MODEL、FPGA_REAL 回执与实际网页。原入口会停 GDM，实体屏幕演示必须明确采用与图形共存的入口，不能悄悄删除原板测条件。等待不授权本聊天重启/刷写、终止其他任务或代处理它的审批。

运行监测只在有意义的完成、失败或需要用户处理时通知；未通过、仍占用或没有变化时保持安静。实际模型设置unknown；本轮未调用DeepSeek评审/验收，未改其他聊天设置，未提交或推送。

已创建当前聊天的每分钟自动跟进，名称“PL验收后接入板端前端”，automation id `pl`，ACTIVE。持久游标与等待状态在 `evidence/frontend_board_A/20261026-integration-prep-v1/monitor-state.json`；继续时更新游标并避免重复通知。完成实际接入后停用此跟进。
