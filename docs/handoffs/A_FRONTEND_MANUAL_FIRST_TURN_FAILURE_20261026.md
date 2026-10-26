# 实体首问失败：已结束并释放

本轮用户选择病例3，输入“每次疼痛持续多久”，首问没有发布回答；用户结束问诊后能看评价，但不能开始新问诊。用户要求退出并分析。当前已关闭本次Firefox、结束后台、恢复默认PL并归档自己的租约；active_lease=false、zocl=false、default overlay applied。没有启动下一次问诊或重试用户问题。

确切链路：

1. 实体Firefox启动后，其gfxtest探测Vulkan/GPU，产生Snap AppArmor拒绝访问提示；日志也显示其短暂建立/销毁ZOCL客户端。系统随后产生 `<4>[6444.012890] kauditd_printk_skb: 4 callbacks suppressed`。
2. 原孤立验收的全局内核日志门在首问时读取这些新增日志，唯一rejected_diagnostics项是这条日志抑制提示，reason=UNREVIEWED_OR_DUPLICATE_DIAGNOSTIC；HealthSchedule随后锁止，许可线程记录 `PERMISSION_FAULT_RETAIN_OWNER: HealthBlocked: health schedule latched`。
3. 请求并非缓存miss：TT10_REQUIRE_HIT、hit=true、reused_tokens=70、new_tokens=37、prompt_tokens=107。Native返回status=ERROR、decode_rc=2、decode_calls=0、output_tokens=[]、state clear=true/position=-1。成功PL提交和完成仍为预热的648次，本问新增PL提交0。问诊退出检查仍余1076秒，不是30分钟窗口过期，也不是5000次预算耗尽。
4. NativePL异常后broken=true，服务ready=false/BACKEND_UNAVAILABLE，因此JS同时禁用提问和新会话。结束/评价不依赖模型；现有规则按医生已接受的问题覆盖计分，所以失败回答仍显示10/100和持续时间覆盖。这不证明问答成功，评分规则未改动。
5. 本地接入还有异常收尾缺口：WorkerTransport.send设inflight=true后，api.receive若先被健康门抛出异常，则终止响应未由get消费，inflight不会归零。interactive_case的结束循环一直等待该标志，导致自动退出卡住。属于软件接入生命周期问题，不是病例数据损坏。

退出实际过程：确认会话早已closed/busy=false，保留完整快照和规则评价；仅对本次profile/kiosk的Firefox主进程16128正常SIGTERM。原worker16027已返回终止ERROR并清空状态，648次allow提交与648次确认完成相等，没有新增提交；向它原stdin发送标准shutdown，进程退出码2（/proc原始wait status512）。不能称为正常worker退出或Owner.finish成功。此后FD/VMA扫描完整且无计算资源持有、zocl refcount=0，才结束自身卡住的纯软件manager15867、接持两个规范锁，普通dfx remove、rmmod zocl、load k26-starter-kits均exit0，并归档本次失败租约。没有强制卸载、重启、刷写或清除失败日志。

尚未部署修复，也没有将本轮记为PASS。后续修复应处理实体Firefox图形探测与计算设备的隔离、图形环境日志的准确归因、首问失败时的终止响应收集/有界收尾，以及服务失效/单次窗口结束后的明确界面提示。不能简单关闭全部日志检查或把所有警告放行。此前15项PC测试和ready/预热检查没有覆盖实体浏览器启动后首次人工提问，这次暴露的是该验收缺口。

取证均在 `evidence/frontend_board_A/20261026-manual-session-v1/`：USER_EXIT_DIAGNOSIS.json、TURN_FAILURE_DETAILS.json、HEALTH_FAILURE.json、USER_EXIT_RESTORED.json、MANUAL_RESULT.json及同名UART原始回执。顺序以monotonic_ns为准，板端墙钟与PC时间不同，原值保留。窗口v4已消费，不可再次运行；后续板端工作需独立新窗口，当前板卡已释放。
