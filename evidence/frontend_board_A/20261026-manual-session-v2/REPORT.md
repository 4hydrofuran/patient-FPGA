# 实体 Firefox 真实问答通过，已留空白问诊

**PASS_REAL_GRAPHICAL_MODEL_FPGA_QUESTION**。本轮实板GUI验证完成，当前第二场空白问诊留给用户；最终释放尚待用户结束或本窗口限时到达，不把运行中的租约记为已释放。

## 是否复用了另一聊天的优化

是。三个管理源码及模型原生二进制与 `20261026-pl-authfix-board-v2/TESTED_SOURCE_PINS.json` 完全匹配，见 PIN_MATCH_LATEST.json。复用已通过的原始模型、计算核、XRT及70-token公共前缀命中。上次失败的手动问诊也已命中70 tokens，其失败点是实体Firefox审计日志被全局内核门误拒；不是没有启用缓存。

另一聊天新增的34-token短提示词仍为候选方案，没有将它冒充本报告所引用的已验收优化，也没有静默改病例、提示词或评分。

## 本轮实际结果

| 项目 | 实测 |
| --- | --- |
| 浏览器 | 板端图形 Firefox158.0，HDMI桌面中的全屏窗口，非headless |
| 病例 | SYN_CP_03 |
| 问题 | 每次疼痛持续多久？ |
| 回答 | 每次疼痛持续 20 分钟。 |
| 回执 | answer_source=MODEL，actual_backend=FPGA_REAL，原内容检查pass |
| 网页输入至完整回答 | 39.891秒 |
| 原生请求处理 | 39.261秒 |
| 前缀 | TT10_REQUIRE_HIT；实际复用70，仅处理38个新token；总提示词108token |
| 输出 | 9 tokens，9次decode；status=OK，最终状态清零 |
| 主任评价 | 原规则评价正常，10/100 |
| 实际提交/确认完成 | 1656次；其中预热648，问答1008 |
| 权重 | 72次加载；模型及权重留在同一进程供下一场复用 |
| 硬件全局计数 | null，未测 |

39.891秒只是一组实测，不承诺所有问题相同耗时，不能与报告中的短输出定位问题直接计算配对提速。加载和预热在ready前完成，不计入本次问题时延。

验证结束后实际点击“新问诊”，控件正常，创建了不同session ID的新空白会话。取证时用户场次turns=[]、ready=true、busy=false、failure=null，尚未代用户提问；剩余窗口1625秒。`user-input-ready.png`已人工检查：病例3、等待提问、空白文字框、“发送问题”和“结束问诊”均显示正常。物理触摸和用户自己的下一问仍待实际操作，不据自动GUI问答追记用户问诊完成。

## 最小软件修复

- 私有图形适配准确记录并接受 `kauditd_printk_skb: N callbacks suppressed` 的审计限流提示，原始日志/哈希保持；其他内核异常及日志连续性检查保持。用上次完整实际日志重放验证新旧行为，并验证DMA timeout仍拒绝。没有关闭全部日志门。
- 本次Firefox专用profile关闭硬件加速/WebGL，使用软件渲染，并设置 `MOZ_AVOID_OPENGL_ALTOGETHER=1`；没有降低浏览器沙箱或AppArmor。依据：[Mozilla硬件加速配置](https://firefox-admin-docs.mozilla.org/reference/policies/hardwareacceleration/)、[Mozilla图形探测源代码](https://raw.githubusercontent.com/mozilla/gecko-dev/master/toolkit/xre/glxtest/glxtest.cpp)。
- 异常后的终止响应只作有界收尾收集、不作为成功交付，避免无限等待inflight；原PS许可、BO预算及正常关闭责任保持。
- 新窗口只允许一次自动验证和一次用户回答。原5000次/72权重/140591104字节预算不扩充；两次24-token回答的保守预算4680次。每场仍仅允许一个模型问题。

## 执行和保留失败

用户单独授权一次正常重启，已执行一次临时irq2启动，未改默认启动文件、未saveenv、未刷写。当前kernel6.8.12-a10irq2，boot68fc4950-b776-4f54-8b67-c40ddeac6bb6。

冷启动后原临时192.168.2.2地址和/run/lock文件消失。第一次下载因无路由未执行setup；补回eth0的192.168.2.2/24临时地址，保留原192.168.137.2及原默认路由。首次管理器在Owner创建阶段因缺少规范运行时锁文件退出，未创建租约、未加载PL。失败目录 `gui-qa-20261026-v1`保留。补齐运行时锁文件后在独立 `gui-qa-20261026-v2` 成功启动，没有重试旧计算窗口或再重启板卡。

19项相关PC测试、历史契约与新版配置均exit0，见PC_CHECKS.json。安装/启动/取证命令和退出码见各UART回执，完整24项板端证据在board-receipt.zip及解包目录。本轮未调用DeepSeek进行核心接入/证据验收，未调用Vivado/Vitis，未提交或推送。

## 当前交接

板端root `/var/lib/kv260-a12/gui-qa-20261026-v2`，manager PID3281；Owner窗口 `a12-gui-qa-20261026-v2`。活动租约/ZOCL/worker均为用户问诊有意保留，不要抢占或关闭。HTTP仅板端localhost8000；临时PC源码服务已完成用途并停止。用户在屏幕直接输入、发送，收到回答后结束问诊；正常PS流程随后释放、恢复default PL，结果HTTP再保留30分钟。不是永久常驻服务。
