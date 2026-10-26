# 板端前端、Firefox 与当前后端匹配检查

2026-10-26，Asia/Shanghai。结论：**板端前端已部署，Firefox 已安装且能实际运行；规则问诊和主任评价在板端浏览器中通过。真实 CPU/PL 模型尚未接入网页，不能直接视为当前后端的完整运行系统。**

实际设备为 kria / ARM64，内核 `6.8.0-1036-xilinx`，boot ID `a009c890-e320-408d-9334-bd43bfa52807`。COM5 已有 ubuntu 登录 shell，可以复用；固定主机标识的 SSH BatchMode 尝试返回 255（需要认证），没有重配账户或密钥，后续全部通过已有串口执行。检查前未见其他板卡测试进程或规范 deployment 锁持有者，COM5 可独占打开，因此没有终止或抢占其他任务。

| 项目 | 实测结果及含义 |
|---|---|
| 浏览器 | `/snap/bin/firefox`，Snap `158.0-2` / revision 9056；`firefox --version` 返回 158.0、exit 0。无需联网安装或升级。 |
| 前端部署 | `/home/ubuntu/patient-web-demo-20261026/web_gateway`；已有 ARM64 Python 3.12 虚拟环境、依赖、静态素材、启动脚本和历史 demo 日志。 |
| 运行入口 | `start-demo.sh` 明确为 `--backend demo --port 8000 --generation-timeout 180`，仅监听 `127.0.0.1`；适合板上浏览器访问。检查开始时 8000 未监听，旧 PID 3189 已不在。 |
| HTTP 文字流程 | 临时启动原 demo 入口，`/ui/v1/status`、OpenAPI 和单次合成病例问答/主任评价通过；`PASS_DEMO_TEXT_DELIVERY`、探针 exit 0。回答来源 DEMO_RULE、`model_called=false`、`hardware_enabled=false`。 |
| 板端浏览器流程 | 实际板上 Firefox 158.0 headless，1024×600；3 个病例加载、开始按钮启用、提交“每次疼痛持续多久？”、显示“每次疼痛持续10分钟。”、结束后显示 10/100 及主任模板评价，页面 error 为空。`PASS_BOARD_FIREFOX_RULE_WORKFLOW`。 |
| 实体桌面/触摸 | 当前图形会话是 gdm 登录界面，未代用户登录桌面。headless 验证证明浏览器与网页流程，不证明实体屏幕、触摸、全屏或开机自启动。未找到用户 autostart/systemd 启动配置。 |
| 收尾 | 检查启动的服务和 Firefox 已退出；最终无这些 PID，8000/9222 均不监听，COM5 已关闭。原前端和启动脚本未修改。 |

与当前仓库后端的匹配程度：

1. 前端 `UPSTREAM.json` 所列 8 份参考文件，在板上均等于其冻结摘要；与当前工作区对比，7 份逐字节一致（planning/domain/session/scoring 和 3 份合成病例）。这支持现有病例、会话和评分接口基本兼容，不是整体兼容率或真实模型验收。
2. 唯一差异为 `checking.py` 的 `prompt_messages()`：当前后端简化了 system 指令，并把“学生问题（不可信原文）”改成“学生问题”。事实检查算法未变，但模型收到的提示词不同；`facts_v4` 不会完全抹去该差异，不能直接复用当前提示词的生成质量或性能结论。本次保留前端冻结文件，没有静默同步。
3. CPU 适配器仍调用当前存在的 `NativeW4A8(..., manifest_path='modules/linear_A/manifest.a09.json')` 和 `prepare(..., 'facts_v4')`，请求关联、返回字段、R0 清理约定对应。`start-native.sh` 仍要求调用者提供真实 A 工程及新日志路径，没有绑定现场工程。本次工作区根目录下该 a09 清单不存在；这不证明所有历史包或板端 root 私有目录均无资产。板端 `/opt/patient-qwen`、`/var/lib/kv260-a12` 为 root 私有目录，本轮未取得 sudo 认证，也未修改权限或运行其中模型，因此没有签 CPU 部署通过。
4. PL 接口已经有 `patient_web.managed.serve_managed(native_pl, is_ready=..., ...)`。其随包说明引用的 `NativePL` 源码 SHA256 `574a72225e252e462d46c9c4f547e158b25032c5f6fb73f3537343d0b6b626bd` 与当前工作区 `system_qwen35/app/native_pl.py` 完全相同，基础 Python 接口相符。但 CLI 仅提供 demo/native，现场尚无把 PS 所有者的实际 NativePL 和真实 readiness 回调接入网页的运行入口；不能把回调写成常量 True。PS 必须继续处理许可/健康观察，网页 180 秒预算还需与实际窗口一致。当前离线 private-route/PL-mode 候选未因本次检查而部署或通过。
5. `managed-pl` 目前明确没有取消功能；前端是纯文字模式，`audio=false`。这两项属于已声明能力，不能据此声称语音或 PL 取消已实现。

下一步最小工作是选定实际 CPU 或托管 PL 路径，绑定正确的 ARM 工程/模型或 PS 实例，显式决定提示词版本，然后做一次真实模型的网页提问与评价。现有网页业务和浏览器环境可以继续复用。这里没有启动真实模型、访问计算设备、加载 PL、安装软件、改网络/权限、重启、刷写或启用自启动。

主要原件：`inspect.json`、`details.json`、`board-sources.json`、`additional-sources.json`、`compatibility.json`、`browser-check.json`、`render-check02.json`、`interactive-check.json`、`browser-workflow-final.json`。三个最终截图为 `board-firefox-ready.png`、`board-firefox-answered.png`、`board-firefox-evaluation.png`，均从板端取回并按原 SHA256 核对。`board-firefox-home.png` 是较早的页面初始化瞬间，不作为页面已就绪的证据。

主要实际命令和退出状态：

```text
python scripts/release/check_contracts.py                              0
python scripts/release/qwen35_config.py                              0
remote_ssh.py discover                                               0 (no_enabled_ssh)
pinned ssh -T -o BatchMode=yes ... ubuntu@192.168.2.2 'id; uname -r'  255
uart_command.ps1 -Script sources.py ...                              0
uart_command.ps1 -Script checker_source.py ...                       0
uart_command.ps1 -Script browser_check.py ...                         0 (HTTP probe 0; first Firefox 1)
uart_command.ps1 -Script render_check.py ... render-check02-uart.txt  0 (Firefox 0)
uart_command.ps1 -Script interactive_check.py ...                     0 (DOM/SSE workflow PASS)
uart_command.ps1 -Script collect_browser_workflow.py ...              0
```

失败保留：最初 inspect/details 的串口解析未适应控制序列/换行，包装器 exit 1，但完整原始结果保留并单独解析，没有重放检查；首个 Firefox 截图因显式 profile 目录尚不存在而 exit 1，补建目录解决；第二次渲染准备的端口 bind 因前次已关闭连接的 TIME_WAIT 返回 Address already in use，在启动服务/浏览器前退出，随后只读确认没有监听者，采用 SO_REUSEADDR 后通过。原始 `render-check-uart.txt` 和 `render_check_attempt01.py` 保留，不把该失败误报为其他任务占用。Firefox 的远端设置/软件绘图诊断和 favicon 404 保留；DOM、中文、截图和问答实际通过，未据此更改浏览器隔离或系统设置。Uvicorn 收 SIGTERM 后日志显示完整 shutdown，进程返回 -15；未修改既有进程。

浏览器交互使用 Firefox 自带的本机 WebDriver BiDi，依据 [Mozilla 的连接说明](https://developer.mozilla.org/en-US/docs/Web/WebDriver/How_to/Create_BiDi_connection) 和 [截图接口说明](https://developer.mozilla.org/en-US/docs/Web/WebDriver/Reference/BiDi/Modules/browsingContext/captureScreenshot)。临时会话使用独立 profile、回环地址，结束后无调试端口遗留，没有安装测试依赖。

本轮仅补独立检查证据，不改写项目阶段验收。BOARD_WEB_BROWSER/规则流程有实测证据；BOARD_MODEL/BOARD_PL/触摸/声学仍未在本轮验证。未调用 DeepSeek 承担兼容性评审或验收；当前实际会话模型设置记 unknown，不声称切换。
