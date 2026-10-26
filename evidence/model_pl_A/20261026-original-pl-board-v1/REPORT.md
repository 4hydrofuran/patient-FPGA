# 原PL验收尝试（2026-10-26）

**本轮未通过，未完成模型计算。** 任务在25分钟内停止新增操作，原始失败保留。

用户明确授权一次正常重启及一次临时RAM引导。实际各执行一次，当前内核为6.8.12-a10irq2，boot为8a0276fb-86d1-4ef8-b067-adcc903a999a；默认启动文件未改，无刷写或saveenv。临时传输地址恢复；网络操作首次回执解析失败，随后只读身份确认地址已存在，没有重复网络变更。

准备原普通R0/warm/hit包的新授权窗口，保留原Owner、双锁、资源及内核门槛，无长诊断。首次启动在PL变更前被历史残留DTBO阻断；核对为同版文件后原样归档。两个初步归档脚本的失败记录保留，未删除固件或旧失败。

第二次入口启动已加载匹配驱动与测试PL。随后资源探测策略拒绝`spec.authorization_included=true`：该字段应保持工作量包的false，计算授权应单独绑定Owner review。这是本轮绑定代码错误。异常发生在execute_case的validate_plan阶段、发送模型请求之前；没有R0/warm/hit回答，也不能把驱动/PL加载成功记为模型验收通过。

**当前板端未释放：管理器2907、worker3039仍存在，活动租约a12-original-pl-20261026-v1、测试PL及ZOCL保留。** 未强杀、卸载或再重启。原旧管理链只有finalize-only入口；未能在本轮内完成合作关闭与默认平台恢复，不能宣称已收口或板卡空闲。

后续必须先处理此次保留的Owner/worker并完成原正常关闭、恢复及独立释放，再修正独立绑定并重新安排计算。新优化候选未执行；本轮仍无PL模型验收PASS或时延数据。

证据：boot.json、identity.json、preflight-local.json、BASELINE_REVIEW.json、start-uart.json、archive-remaining.json、start2-uart.json、final-scene.json及RESULT.json。板端目录：/var/lib/kv260-a12/original-pl-20261026-v1/。原始两次入口结果分别为ATTEMPT_RESULT.json和ATTEMPT_RESULT-v2.json。
