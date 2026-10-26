# 板端手动一问一评：实时窗口已就绪

最新状态：此处“已就绪”为首问之前的历史记录。用户实际首问失败，本次窗口已退出并释放；见 `A_FRONTEND_MANUAL_FIRST_TURN_FAILURE_20261026.md`。不能继续依据本文件把v4当作运行中或问答已通过。

用户已授权板端前端接入、保留 HDMI 图形桌面、基本功能检查并进行一次手动一问一评。用户报告关闭浏览器后重新访问 localhost 失败。本轮修复的是实时前端启动及桌面共存；没有替用户发送问诊问题。

当前有效目录 `/var/lib/kv260-a12/manual-web-20261026-v4`，租约 `a12-manual-web-20261026-v4`，manager PID15867。板端 Firefox 全屏打开 `http://127.0.0.1:8000/`。最终基本检查：GET / 返回200，5483字节；status.phase=READY、ready=true、backend.execution_kind=FPGA_REAL、hardware_enabled=true、busy=false、current_session_id=null。模型问题数0，手动问答仍 NOT_TESTED，不能据此宣称问答通过。最终取证时剩余1497秒，窗口原始限时1800秒。不要另开窗口抢占它。

已真实验证148个 BO、72份权重、140591104字节、地址位于低2GiB且不重叠。中性70-token前缀已实际 cache_create 成功，状态已清零。用户第一问强制 TT10_REQUIRE_HIT / neutral / 同一 binding；返回必须 hit=true且reused_tokens=70。只允许一次模型问题，原提示词、病例、规则评分、公共ABI、核和XRT保持原包。复用普通优化验收的二进制和健康/许可服务；不使用未经实板验收的 resident 服务。

触屏模式的显式变化：

- `interactive_entry.py` 保留 GDM，并采用独立 graphical admission。MemAvailable 仍扣未分配 BO 且保留1114112KiB；CmaTotal需覆盖全BO和98304KiB。原 CmaFree及原 isolated admission结果如实保存，但图形模式不将可迁移普通页占据的CmaFree当成固定DMA不可用量。模型ready前必须通过真实BO分配及完整地址清单验证。原孤立板测策略文件不变。
- 临时规则 `/run/udev/rules.d/99-patient-pl-headless.rules` 将 `SUBSYSTEM=="drm", KERNEL=="card[0-9]*", DRIVERS=="zocl-drm"` 的 `ID_SEAT` 设为 `seat-patient-pl`，避免桌面/logind自动持有计算card1；显示card0不匹配该规则。只在本次运行时有效。修改后实读计算设备FD/VMA为空、zocl refcount=0。切换已有设备归属时桌面回到登录，用户已重新登录；之后新窗口提前检查用户桌面，期间重建桌面则等待而不逃逸worker所有权。
- 保留现有 PS normal shutdown、释放、恢复default PL和归档流程。完成问诊或到窗口限时后关闭worker，再恢复平台；结果HTTP额外保留30分钟。关闭Firefox不关闭后端。该模式是限时体验窗口，不是跨重启的常驻模型服务。
- 安装 ibus-libpinyin 及8项依赖，0升级、0移除；板端直接下载超时，改由PC从原Ubuntu包URL通过HTTPS下载6个缺失包，核对APT给定大小/校验值后传入板端缓存，最后 `apt-get ... --no-download` 完成，exit0。没有改板端网络或全局升级。gsettings屏幕键盘=true，sources为libpinyin/us；最终 `ibus engine` 读取libpinyin。首次set-engine返回1，随后读取已为目标引擎，原回执保留。物理触控中文输入还需用户实际操作验证。

失败与释放如实保留：v1早期入口缺路径导入失败已修复，随后原CmaFree容量门拒绝，未执行PL命令、无worker；验证自身零设备后结束自己的纯软件等待进程并归档。v2桌面抢开计算card1，发生binding/node/holder拒绝，仍未启动worker；席位调整使FD/VMA为空、refcount=0后正常remove/rmmod/load default，退出码均0，归档自身租约。v3完成实际warm并启动HTTP，但用户桌面消失使入口退出到原retain循环；在无session/无问题、最后响应cache_created/OK的状态下向该worker原stdin发送标准shutdown，实读僵尸退出码0、资源释放，再正常恢复default；仅随后结束自己的软件管理进程并归档，不声称原Owner.finish完成。这些是本次自身失败窗口的处理，不是抢占或代处理其他聊天。v4为独立新窗口，当前正常运行。

早期只建议清理25个已知历史归档页缓存没有改善CmaFree；一次compact_memory反而降低CmaFree，均未当作成功修复，不再重复。最终采用上述显式图形模式和实际分配验证。没有重启、刷写、强制卸载、Vivado/Vitis调用或重跑规则演示。

证据目录 `evidence/frontend_board_A/20261026-manual-session-v1/`：SOURCES-v4.json（源码及overlay哈希）、PC_CHECKS.json（历史契约exit0、新版配置exit0、15项PC测试通过）、basic-ready-uart.json、board-receipt.zip以及各版本setup/start/failure/close回执。板端包中 BASIC_READY.json、ready.json、warm-result.json、graphical-allocation.json、INTERACTIVE_READY.json、ime安装和配置回执已收回。此前真实网页一问一评通过证据仍在 `20261026-board-integration-v1`，不把它冒认为本次手动提问。

下一步由用户在实体屏幕选择病例、开始问诊、输入自己的一个问题、发送，然后结束问诊查看规则主任评价。新会话不可被代理测试占用；如用户已开始，优先读取实际结果和正常释放证据。窗口自动处理自身正常退出，不能因为聊天结束就关闭它。HTTP结果保留期结束后再次访问失败需启动新窗口；当前没有承诺永久在线。
