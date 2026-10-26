# 板端前端接入与一次真实 PL 问答

2026-10-26。**PASS_BOARD_FRONTEND_PL_SINGLE_QA**。按用户“板卡已释放、本任务最高优先级、仅基本功能检查和一次简单运行”的授权，已完成独立板端 Python 接入，并在板上的 Firefox 中完成一次真实模型问答和主任评价。

后续耗时核对：本次只复用了通过后的管理器/模型，**没有接入已验收的前缀预热与命中路径**。既有 NativePL.generate 明确发送 cache_policy=R0；实际 prefix_cache_request 为 hit=false、reused_tokens=0、new_tokens=108。此前报告27.854秒是70token预热后的hit，仅37个新token；其R0为60.711秒。网页问题/回答也不同：本次decode9次、1656次提交；此前decode6次、R01440次、hit792次。网页68.361秒中NativePL记录67.772秒，外围约0.589秒，因此不能把主要差距归为浏览器开销。这里是接入范围的遗漏，不代表已把前缀缓存优化接到网页；未为本次解释额外运行板卡。模型二进制SHA和manager源码SHA与通过版本已从原件比对一致。

| 项目 | 实际结果 |
|---|---|
| 接入目录 | `/var/lib/kv260-a12/web-20261026-v1`；复用 `/home/ubuntu/patient-web-demo-20261026/web_gateway` |
| 板卡 | kria ARM64 / `6.8.12-a10irq2`；boot `b0718166-5c3b-4c4f-b669-4f83d3340d00` |
| 浏览器 | 板上 Firefox 158.0，headless，1024×600 |
| 问题 | 每次疼痛持续多久？ |
| 真实回答 | 每次疼痛持续 10 分钟。 |
| 来源 | `MODEL`，`FPGA_REAL`，`model_called=true`，事实检查通过，EOS=true，R0 状态清理确认 |
| 页面耗时 | 点击提问至页面可读回答 68.361 秒；单次样本，包含网页/SSE/显示等待，不是内部 TTFT，排除此前模型加载 |
| 主任评价 | 10/100，持续时间已覆盖；来源为原有 RULE_TEMPLATE |
| 请求与计算 | 真实模型生成仅1次；72次权重加载；1656次许可提交与1656次后端 host_verified_completions 对应。硬件全局计数保持 null |
| 收尾 | Firefox exit0、worker exit0、网页线程停止。管理器输出正常完成终态且 PID4130 已不存在；独立采集确认默认 PL applied、GDM active、active lease=false、ZOCL=false |

已实际查看 `browser-answer.png`、`browser-evaluation.png`：患者回答可读，网页顶部显示“板端模型已连接 · PL参与计算”，评价页显示10/100。服务端回执自身的 browser_render_verified 仍为 false，未改动回执字段；另存的浏览器DOM与截图构成本次浏览器渲染证据。

本次验收先读取前一任务的真实通过记录 `evidence/model_pl_A/20261026-pl-authfix-board-v2/RESULT.json`，复用其模型二进制、计算核、驱动和平台恢复逻辑。基本板端读取确认内核匹配、无活动租约/ZOCL、前端仍在、端口可用。已有 sudo 会话可用，无需新登录或保存凭据。等待 heartbeat `pl` 已删除，用户直接授权后由本聊天执行。

实现为 `platform/qwen35/web/board_case.py`、`board_entry.py` 与先前的 `system_qwen35/app/web_managed.py`。新窗口仅将原管理器的 run_case 接到网页；原 main 去掉未绑定入口的显式停止后进入用户已授权的新窗口，平台装卸、Owner、每次许可及最终恢复流程原样复用，没有增加另一套硬件验收。NativePL 原字节经独立包命名空间加载，ROOT 指向实际 `/opt/patient-qwen`；前端复用既有 CorrelatedPL、Session、事实检查、发布与评分。原长提示词保留，与刚通过的普通 PL 基线一致。

已部署 NativePL SHA256 `574a72225e252e462d46c9c4f547e158b25032c5f6fb73f3537343d0b6b626bd`；复用 manager SHA256 `a405ff61f5926696ab200e7c3ef836f3785356d718d230766f88f73e2d3db989`。覆盖包8528字节，SHA256 `042e0d91af93c8771796c5334826b91766d8044dfa5f835c3a73dcec3db6e203`。板上克隆小型运行包到独立目录，不复制模型权重，不覆盖旧验收/前端包；已存在的同源临时 firmware 文件保留在本次目录后才由原流程使用。

本轮没有调用 Vivado/Vitis，没有重新分配引脚、仿真、综合或重建位流；没有重启、刷写、语音、压力测试、短提示词候选或 resident 候选实验。只提交上述一个问题，不重跑已通过的规则演示和原R0/warm/hit整套验收。

实际命令记录：

```text
python scripts/release/check_contracts.py                                      exit0
python scripts/release/qwen35_config.py                                       exit0
WSL python3 -B -m unittest discover -s bench/qwen35/web -p 'test_*.py' -v        exit0，10项
python .../prepare_source.py                                                 exit0
uart_payload.ps1 -PayloadPath .../bootstrap.py -ReceiptPath .../setup-uart.json exit0
uart_payload.ps1 -PayloadPath .../start.py -ReceiptPath .../start-uart.json     exit0
uart_payload.ps1 -PayloadPath .../progress.py ...                              exit0，3次短进度读取
uart_payload.ps1 -PayloadPath .../collect.py -ReceiptPath .../collect-uart.json exit0
python .../finalize_local.py                                                 exit0
```

首次本机 python -c 打包因 PowerShell 引号转义发生 SyntaxError，在板卡连接/计算之前；随后改为独立 prepare_source.py，通过后才安装与启动。没有因此重放板端计算。Firefox 日志包含其后台遥测/Remote Settings 上传失败信息，原件保留；浏览器正常exit0，问答DOM、截图与真实回执通过，没有为这些信息更改系统或浏览器设置。

管理器为 detached 子进程，本轮未由父进程 waitpid 取得数值退出码，因此 RESULT.json 的 manager_exit_code 明确为 null；正常终态、进程消失、worker正常退出及最终平台/租约恢复分别有原件，不补造 exit0。未为补该字段再运行一次模型。

原始取回 ZIP 为864685字节，SHA256 `7eb4fc83a57f05f922f17206b5a8fe3f669577a9cc31fea747f82d30274cc9d7`；本地完整核对后解包至 `board-receipt/`。核心文件在 `board-receipt/bundle/run-v1/s2/`：`web-report.json`、`web-turn.json`、`web-evaluation.json`、`native-result.json`、`worker/stdout.jsonl`、三张 browser截图及原最终资源扫描。最终只读板端状态在 `final-board.json`。原始记录重建确认恰好1个native result、回答SHA与回执一致、MODEL/FPGA_REAL、EOS/R0及1656次对应完成。

此次是一次性运行，完成后网页/浏览器/模型均已退出，板子仍上电，默认PL和图形服务正常；本地临时传输服务也已停止，COM5释放。代码与运行记录保留在板上。本次窗口已经消费，不能重放同一目录；今后的运行需分配新的独立运行目录及原Owner窗口。没有把本次演示宣称为常驻产品服务。

物理屏幕/触摸、音频、长稳和医学质量不在本轮；本次确实运行的是板上无头Firefox，不是Windows浏览器。当前实际模型设置unknown；复杂接入和证据复核由主代理完成，未调用DeepSeek承担验收。无提交或推送。
