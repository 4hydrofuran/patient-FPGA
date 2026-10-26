# 图形网页真实验证通过，等待用户输入

最新有效结果见 `evidence/frontend_board_A/20261026-manual-session-v2/REPORT.md`。

本轮真实图形Firefox中病例3问答已通过MODEL/FPGA_REAL和原内容检查，缓存真实命中70，新token38，完整网页应答39.891秒、原生39.261秒，实际回答“每次疼痛持续 20 分钟。”，原评价10/100。并已实际验证“新问诊”按钮，创建了不同ID的新空白用户会话，turns=[]，ready=true。用户自己的问答尚未发送，不可追记完成。

用户明确授权本轮一次正常重启，已临时启动原已验收irq2，boot68fc4950-b776-4f54-8b67-c40ddeac6bb6，没有持久启动修改。当前有效窗口 `a12-gui-qa-20261026-v2`，root `/var/lib/kv260-a12/gui-qa-20261026-v2`，manager PID3281。活动租约、ZOCL和worker为用户有意保留。不要基于前一失败/关机交接认定板卡现在已释放，也不要在本窗口另插入代理问题。

本窗口含预热、一次自动验收及一次用户回答；保留原5000次/72次权重/BO预算。取证时已完成1656次，余3344次；保守完整两问预算4680。用户直接在HDMI文字框输入并发送，完成后结束，原PS执行正常释放和恢复。取证时剩1625秒，最大窗口1800秒，结果HTTP额外30分钟。PC源文件HTTP服务停止后不影响板端问诊。

修复仅图形适配：审计限流提示准确归因且完整留痕，其他内核异常仍拒绝；专用Firefox采用软件渲染和避免GL探测；异常收尾不再无限等待inflight。三个管理源码和原生二进制与已通过普通优化包精确一致，见PIN_MATCH_LATEST.json。旧失败、默认内核、网络临时地址丢失及运行时锁缺失等记录保留；没有把34-token短提示词候选或resident当成本次已验收路径。

正常释放尚待用户结束/窗口到期，manager exit/最后恢复不能提前标PASS。后续读取实际manual-session.json、manual-compute-closed.json、run-v1/result.json和实际lease/defaultoverlay以确认；本轮已通过的仅自动GUI问答及空白用户窗口准备。
