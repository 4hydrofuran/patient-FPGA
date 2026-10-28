# 缓存调试与回答说明：实板交接（2026-10-27）

已更新并在板端运行，记录时间2026-10-27T22:27:06.939519+08:00（北京时间）。展开“调试设置”，在“下次问诊”选择正常（优先缓存）、缓存命中或缓存未命中（实时推理）；结束本场后点击“抽取新病例”生效。当前场次不会随下拉框变化，刷新会保留当前模式及下一场设置。病例仍从20例随机抽取，没有恢复病例选择入口。

用户已确认原请求最后一句指“未命中保持现状”。命中回答的下方现为“CPU 模式 · 缓存命中”或“FPGA 模式 · 缓存命中”，删除原“已核验模型答案”文字与旧提示；未命中回答下方继续显示原来的CPU/FPGA说明。顶部服务状态提示未改。

CPU/FPGA表示提问时选定的运行模式，逐条保存，之后切换模式不会改变历史回答标签。缓存命中仍是MODEL_CACHE、actual_backend=null、model_called=false，原CPU模型来源保留在回执，不标成本次PL计算。新增execution_mode只用于展示，不替代实际计算来源。

调试“未命中”会让该场问诊绕过答案目录并实际调用所选模型，不删除1320条目录，也不伪造目录缺失。公共前缀及常驻权重继续复用。策略澄清/拒绝仍遵循原路由，不强行运行模型。选择命中时，对已有可用答案复用缓存。切换CPU/FPGA后共享目录保持可用，本场未命中设置仍有效。

| 验证 | 实际结果 |
| --- | --- |
| 针对性PC回归 | 2项通过：命中/未命中、下一场绑定/重试、切换模式及历史模式保持 |
| 真实CPU与Edge | 命中显示“CPU 模式 · 缓存命中”；更改下一场设置再刷新，本场仍命中；下一场确实执行1次CPU模型，说明仍为“CPU” |
| 实板启动 | 一条真实FPGA启动问答通过，随后启用1320条缓存 |
| 实板显式命中 | “FPGA 模式 · 缓存命中”；完整答案绘制163ms；模型调用0 |
| 实板显式未命中 | MODEL/FPGA_REAL/model_called=true；说明“FPGA”；完整答案绘制9614ms |
| 实板模型结果数 | 测试前1、测试后2，恰好多出一次真实模型回答 |

上述板端耗时各为单条样本，不作为全部输入性能保证。CPU类型的真实计算和展示在电脑验证；本轮没有额外运行板端CPU未命中矩阵。回答文本、事实核对、评分、模型/native/HLS/公共计算与语音ABI均未改，不重新生成旧目录。

运行目录：`/var/lib/kv260-a12/case20-debug-20261027-v1`；窗口：`a12-case20-debug-20261027-v1`；Owner PID 12056，boot `98886b24-96d3-409e-a783-ce9c54873da9`，kernel `6.8.12-a10irq2`。当前服务ready=true、busy=false，已留新场次`9283e82088134c6aa71a972ee242e353`，记录时0提问，默认auto（优先缓存），调试设置已展开。原Owner/模型/PL为用户使用而保留，当前未释放；记录时剩余约3.92小时。

旧随机版本通过原Owner正常退出0，792次许可/完成一致，默认平台恢复、ZOCL卸载、租约归档；本轮开始时原场次的一条用户问诊已保存。旧HTTP进程正常结束，本轮没有强杀模型、重启、刷写、升级SDK或改公共数学。新版放在独立staging与运行目录，源包SHA256为8a0341e1a80361a75880a7bab887868f6fe22aba16bfd396570ed8407a64f8c0。没有推送远程仓库。

应用接口兼容扩展记录在API_CHANGE.json：POST /ui/v1/sessions增加可选cache_mode=auto/hit/miss，缺省auto；snapshot记录本场cache_mode，TurnResult增加可选execution_mode。原无此参数的随机问诊请求继续有效，计算/语音契约及fixtures字节保持不变。

源码派生：`platform/qwen35/web/integrated/B_601e69ca_A_case20_debug_20261027/`；准备脚本：`platform/qwen35/web/cache_debug_prepare.py`；候选：`release/a12_case20_cache_debug_20261027_v1/case20-debug-t4/`。证据：`evidence/frontend_board_A/20261027-cache-debug-v1/`，重点为LIVE_HANDOVER.json、board-receipt/CACHE_DEBUG_BROWSER.json、pc-browser/RESULT.json、old-release.json。

正常停止整个服务仍向`/var/lib/kv260-a12/case20-debug-20261027-v1/continuous/stop-request.json`写请求，等待原Owner正常关闭/恢复/归档；结束问诊只冻结本场。当前服务为用户保留，不再追加自动提问。

复杂逻辑及板端证据验收由主代理完成；DeepSeek MCP仅精简了一句UI提示“仅下一场生效，当前场次不变。”，由主代理检查应用，未发送病例/凭据或授权文件命令执行。请求Sol/High，单次实际设置unknown。未做无关故障矩阵或新增多层检查。
