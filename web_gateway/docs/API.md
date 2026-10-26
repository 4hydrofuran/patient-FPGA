# 网页接口 ui.v1

2026-10-27：新增 `POST /ui/v1/backend`（`{request_id,backend}`，202）和状态中的 `backend_options`。只有启动时已配置的模式可选择，回答进行中返回 BUSY。切换过程 phase 为 SWITCHING，ready 为 false；加载完成后返回 READY。历史回答的 actual_backend 不随当前模式改变。详见[模式切换](MODE_SWITCH.md)。

2026-10-26最小适配补充：状态新增 `capabilities.generation_timeout_s`（默认180秒）、`capabilities.cancel_turn`；`backend.execution_kind` 按实际返回 `DEMO_RULE/CPU_REFERENCE/FPGA_REAL`，托管PL未初始化时为null。`actual_backend` 的回执/单轮Schema扩展接受 `FPGA_REAL`。既有PS托管入口的configured为 `managed-pl`，本轮不开放该模式的取消操作。单次演示详见 `BOARD_DEMO_QUICKSTART.md`。

所有请求/响应为 UTF-8 JSON；SSE 使用 `text/event-stream`。网页接口独立于上游旧 `contracts/runtime_api_v1.yaml`，不修改计算或语音冻结契约。

## 操作接口

| 方法 | 路径 | 输入与行为 |
|---|---|---|
| GET | `/ui/v1/status` | 无输入；加载中/失败也可查询；ready 与 busy 分开 |
| GET | `/ui/v1/cases` | 返回 3 个病例的编号、标题、版本、审核状态；不返回事实 |
| POST | `/ui/v1/sessions` | `{request_id,case_id}`；201，返回会话 UUID |
| GET | `/ui/v1/sessions/{sid}` | 当前阶段、活动任务、公开问答、epoch、事件 cursor |
| POST | `/ui/v1/sessions/{sid}/turns` | `{request_id,text}`；202 仅代表接收 |
| GET | `/ui/v1/sessions/{sid}/turns/{request_id}` | 单轮结果及 text-delivery.v1 回执；未发布时回执 null |
| POST | `/ui/v1/sessions/{sid}/cancel` | `{request_id,target_request_id}`；202 `cancel_pending` |
| POST | `/ui/v1/sessions/{sid}/finish` | `{request_id}`；200，冻结记录和原规则分数 |
| GET | `/ui/v1/sessions/{sid}/evaluation` | 已结束后返回冻结的原规则分数、中文分项、提问依据及主任模板总结 |
| GET | `/ui/v1/events?session_id={sid}` | SSE 通知；支持 `after` 或 `Last-Event-ID` |

编号为 1–64 个字母/数字及 `_.:-` 字符，首字符须为字母或数字。文字为 1–1000 字符，不接受全空白和非法控制字符。未知字段拒绝，不能提交自定义病例事实、prompt、模型路径、source、confidence、score 或 FPGA 模式。

开始会话需当前问诊已经结束；忙碌时拒绝新回合、结束与新会话。单个实例内同开始 ID/病例重试返回原会话。同提问 ID/文字重试返回原 operation_id，即使已完成也不会再次执行。使用新 ID 才表示新提问。

错误结构：

```json
{"error":{"code":"BUSY","message":"当前回合尚未收尾，请等待完成或取消。","retryable":true}}
```

主要状态码：400 字段或 cursor 错误；404 病例/会话不存在；409 忙碌、内容冲突、会话已结束或容量上限；503 模型未就绪/缺失/不可用。错误不返回内部绝对路径或原始模型输出。

## 一次文字回合

1. POST 问题返回 `accepted`、`operation_id`、`epoch`。
2. 消费事件，或 GET 快照查询。生成的原始 token 和被拒绝的 candidate 永远不出现在公开接口。
3. `answer.ready` 携带检查通过的正式回答；`turn.completed` 表示历史更新和收尾已经完成。
4. 取消时等待 `turn.cancelled`；收到 `cancel_pending` 后仍不能提交下一轮。

`answer.ready` 的 data、快照轮次和单轮结果都包含相同 `delivery_receipt`。其 answer_sha256 绑定正式回答原文、实例/会话/请求/操作及病例版本；不证明浏览器已渲染、用户已读或已播放。字段与发布规则见 [TEXT_DELIVERY.md](TEXT_DELIVERY.md)，给模型部署负责人的接入步骤见 [MODEL_HANDOFF.md](MODEL_HANDOFF.md)。

请求示例：

```json
{"request_id":"question-001","text":"每次疼痛持续多久？"}
```

回答来源：`MODEL` 真实模型检查通过；`DEMO_RULE` 显式规则演示；`TEMPLATE` 策略或检查器回退；`TIMEOUT` 原生截止后的显式保守回复。`actual_backend` 仅在实际调用模型时为 `CPU_REFERENCE`，其余为 null。模式身份另见 status；没有硬件自动回退。

## 状态事件

事件有 `schema_version, instance_id, seq, event, session_id, request_id, epoch, data`。SSE 的 `id` 为 `instance_id:seq`，`event` 为具名事件。

```text
id: <instance>:12
event: answer.ready
data: {"schema_version":"ui.v1","instance_id":"<instance>","seq":12,"event":"answer.ready","session_id":"<sid>","request_id":"question-001","epoch":0,"data":{"text":"每次疼痛持续10分钟。","answer_source":"DEMO_RULE","actual_backend":null,"delivery_kind":"WEB_TEXT_PUBLISHED"}}

```

| 事件 | 含义 |
|---|---|
| `service.ready` / `service.failed` | 初始化结果 |
| `session.created` | 新问诊建立 |
| `turn.accepted` | 原子占用活动回合 |
| `generation.started` | 真正开始调用模型；demo 不发送 |
| `response.preparing` | 显式规则演示准备回答 |
| `validation.started` | 模型/演示输出即将进入 Session 检查器 |
| `answer.ready` | 最终回答通过检查并发布 |
| `turn.completed` | 收尾完成，ready 字段表明后端是否仍可用 |
| `cancel.pending` | 请求作废，仍在等待原工作收尾 |
| `turn.cancelled` / `turn.failed` | 终止状态；没有未检查的回答 |
| `session.finished` | 问诊记录与原始规则分数冻结 |
| `evaluation.ready` | 主任模板总结已与本场记录一起冻结；携带 evaluation_id |
| `session.snapshot` | 新连接或重同步的权威状态快照 |

事件是条件性的：策略拒绝/澄清不调用模型，可能直接出现 `answer.ready`，不伪造生成/检查阶段的耗时。代码在真实调用/检查边界同步发布，SSE 从事件日志读取，不通过定时器编造推理阶段。

## 刷新与重连

首次无 cursor 连接先得到 `session.snapshot`，然后继续增量。断线后浏览器 EventSource 带回 `Last-Event-ID`；同实例会续接尚在缓冲中的事件。测试/自定义客户端可用 `after=<seq>`。

缓冲仅保留 256 条；cursor 过期时发送完整 `session.snapshot` 并注明 `resync_reason=EVENT_BUFFER_EXPIRED`。不同实例的 Last-Event-ID 触发快照重同步；旧实例的会话编号不存在时返回 404，客户端应重新建立会话。

前端按实例、会话、request_id、epoch 检查消息；忽略旧 epoch。SSE 的全局 seq 可能因过滤其他会话而不连续，不应把每个缺号都理解为丢包。刷新只查询快照，不重发问题。断线不自动取消后台回合。

## 存储和就绪语义

服务端保存公开问题、已发布回答和操作结果的有界内存状态。没有持久化数据库；服务重启后内容清除。原生模式会把模型诊断写入启动时明确指定的 output 目录，按上游约定管理。

`ready=true` 表示当前配置的后端可用，`busy=true` 表示回合仍在运行；不代表板卡、音频、PL 或医学审核通过。原生超时导致 worker 被隔离时，后续提问返回 503，仍可结束现有问诊并取回记录/规则分数。

## 主任评价 chief-evaluation.v1

结束问诊在同一协调锁内整理并冻结评价，然后依次发送 `session.finished`、`evaluation.ready`。仅查询、刷新、重新连接和重复结束不会重新计分或改写总结。问诊未结束时查询返回 409。

响应保留原来的 `rule_score`；`summary_status` 现为 `READY`，新增 `summary_source=RULE_TEMPLATE`、`summary_version=chief-summary-v1`。完整字段见 [EVALUATION.md](EVALUATION.md) 与 [contracts/chief-evaluation.schema.json](contracts/chief-evaluation.schema.json)。

`topics` 给出 10 个中文分项及其 `points/max_points/covered/evidence`；`covered_topics`、`missing_topics` 用分项 ID 表示。`review_items` 单独记录原始问题与复核原因，不作为已确认得分。`recommendations` 为依据缺项与复核项生成的固定结构建议。`evaluation_id`、实例、病例身份和 `frozen_at` 用于关联本场冻结结果。

每条证据带 `request_id`、业务 `turn_id`、网页 `question_number`、问题原文、终态及 `answer_published`。两种轮次编号可能不同，前端用 `question_number` 展示，用 request_id 关联；不能拿业务轮次直接索引网页问答列表。问题已计分但回答取消/失败时，证据明确标注这一状态。

`capabilities.chief_narration=true` 表示纯文字主任模板评价可用，`chief_summary_kind=RULE_TEMPLATE`；音频仍为 false，不表示真实模型或主任语音已执行。评价页只从同源 `/display/` 读取固定打包素材，不访问外部字体/CDN。

# 任务 6 联调补充

仅以 `--backend demo --demo-lab` 启动时存在 `GET /lab`、`GET /lab.js` 及 `GET/POST /ui/v1/demo-lab`；默认及 native 环境均不提供这些接口。`GET /ui/v1/status` 新增布尔字段 `demo_lab`。

POST 联调设置体为 `{ "scenario": "normal|delayed|wrong_fact|timeout|failure", "delay_s": 3.0 }`，delay_s 范围 0.2–10 秒，省略默认 3 秒；其他字段拒绝。只作用于下一次接受的提问，忙碌时 409。选择不属于正式提问协议，不得将该字段放入 `/turns`。GET 只提供模拟诊断，不代表交付成功；最终以正常快照、回执和 SSE 为准。详情见 `WORKFLOW_ACCEPTANCE.md`。

