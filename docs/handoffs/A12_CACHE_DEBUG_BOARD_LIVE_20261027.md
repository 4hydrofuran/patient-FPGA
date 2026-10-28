# 当前缓存调试版：实板运行中

最新前端提示调整覆盖下述仅问诊隐藏规则：按用户追加要求，case-label与case-pool现在所有页面状态均隐藏，因此评阅页的“下场随机抽取”和“每场从20例中随机抽取”也不显示。缓存设置仍仅问诊时隐藏。已同步板端CSS及当前浏览器样式，核对问诊/非问诊隐藏结果通过，session_id不变、未重启服务。证据：evidence/frontend_board_A/20261027-frontend-all-case-hints/board.json；DeepSeek仅提供CSS机械替换。

后续前端小改：问诊状态同时隐藏“病例随机抽取”及“每场从20例中随机抽取”两段提示；仅扩展evaluation.css的consultation-active隐藏规则。已同步当前板端并更新已加载页面样式，真实浏览器核对三个控件（含原缓存设置）在问诊状态均隐藏，页面状态立即恢复，session_id不变、服务未重启。证据：evidence/frontend_board_A/20261027-frontend-case-hints/board.json；旧CSS单独备份于运行目录frontend-case-hints-backup-20261027/。DeepSeek仅提供这一条CSS选择器的机械扩展，主代理检查应用。

服务：/var/lib/kv260-a12/case20-debug-20261027-v1；窗口a12-case20-debug-20261027-v1；Owner为用户使用保留，不能清租约或重复启动。
调试设置只影响下一场：auto/hit/miss；病例仍随机20例。命中说明为CPU/FPGA模式＋缓存命中，未命中说明保持原样。
电脑真实CPU与Edge、板端FPGA命中/真实未命中均通过。板端样本163ms/9614ms。
交接场次9283e82088134c6aa71a972ee242e353，记录时0提问、auto、ready=true。
原随机版已正常关闭/恢复，用户一条记录保留，本轮未重启。
详见[交付记录](../A12_CACHE_DEBUG_BOARD_20261027.md)及evidence/frontend_board_A/20261027-cache-debug-v1/LIVE_HANDOVER.json。

2026-10-27 23:31 北京时间，按用户要求仅更新当前运行目录下的index.html和evaluation.css，并同步派生源码：评阅按钮“抽取新病例”改为“新病例”；consultation-active状态隐藏缓存调试控件，开始前及评阅页仍可设置下一场。模型/服务未重启，当前session_id未改变。板端HTTP返回文件哈希与源码一致，真实浏览器核对按钮文字及问诊/非问诊两种CSS状态通过；仅临时切换页面类后立即恢复，没有提交问题或结束问诊。已加载页面的样式与按钮同步更新，刷新后仍从静态文件取得新版本。原发行包保留为历史证据，后续重建由cache_debug_prepare.py读取已更新派生源码。旧静态文件备份于运行根目录frontend-simple-adjust-backup-20261027/。证据：evidence/frontend_board_A/20261027-frontend-simple-adjust/board.json。历史契约检查与qwen35_config.py均退出0。DeepSeek仅返回按钮文字及一条CSS机械修改，主代理审查应用，无病例或凭据输入。
