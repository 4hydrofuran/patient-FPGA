# 第四任务：纯文字回答交付规则 v1

本文是当前实现的规则，不是将来的页面效果说明。适用范围是纯文字问诊；病例和评分仍为软件测试草案。

## 交付边界

**交付 = 通过业务事实检查的回答，被服务端确认为当前有效请求的正式回答，并提交到该会话的可恢复状态及后续患者上下文。**

本版本使用 `WEB_TEXT_PUBLISHED`。它不证明浏览器已收到、已渲染、用户已读或已听到；不等待浏览器 ACK，不调用音频模块。浏览器断开不自动撤销服务端已经接受的任务。当前可恢复状态只在进程内存中，重启后会话失效。

## 发布前置条件

1. Session 存在且未关闭，业务 epoch 与 pending 对应。
2. 接口操作尚未取消，网页请求 epoch 与活动 Work 对应。
3. 存在由 A02 Session 检查通过的完整回答；未知/不完整候选不得直接发布。
4. 适配器返回文字与 pending、已检查响应逐字符相同；内部 A02 digest 同时匹配。
5. 来源与已检查响应一致。真实调用、规则演示、检查器/策略模板及超时必须分别标记。
6. 回执全部构造、校验成功后才追加一次历史；取消与提交使用同一协调锁确定先后。

参考目录的 A02 文件逐字节保持原样；新增逻辑位于 `PublishedSession`、`Coordinator` 和 `delivery.py`。旧 `_played` 字段仍沿用上游名称，文字条目的含义为“已发布上下文”，`audio_played=false`。

## 时序和竞争结果

| 情况 | 正式文字 | 患者上下文 | 回执/终态 |
|---|---|---|---|
| 正常、完整、检查通过 | 发布 | 追加一次 | `answer.ready` 后 `turn.completed`，有回执 |
| 候选数字/单位/事实不符 | 不发布原候选；可发布检查通过的保守模板 | 只追加最终模板 | 来源 `TEMPLATE` |
| 生成尚未 EOS | 不发布截断候选；可发布检查通过模板 | 只追加最终模板 | 来源 `TEMPLATE` |
| 发布前取消，之后返回有效答案 | 丢弃迟到结果 | 不追加 | `turn.cancelled`，回执 null |
| 发布后再取消该已完成请求 | 已发布记录保持 | 保持 | 409 `NO_MATCHING_OPERATION` |
| 后端 `ERROR`、异常退出、协议畸形 | 无 | 不追加 | `turn.failed`，回执 null |
| 后端 `CANCELLED` | 无 | 不追加 | `turn.cancelled`，回执 null |
| 后端真实超时 | 可发布经过检查的保守回复 | 只追加该回复 | 来源 `TIMEOUT`；原生后端隔离，后续请求 503 |
| 相同 ID/问题重试 | 返回原操作 | 不重复追加 | 原 operation_id、原回执 |
| 相同 ID/不同问题重试 | 无新回答 | 不改动 | 409 `REQUEST_CONFLICT` |
| 浏览器未连接或刷新 | 已发布文字可查询 | 不重复追加 | GET 快照/单轮查询，SSE 续接/快照恢复 |
| 服务重启 | 原会话不再存在 | 重新建立 | 新 instance_id，旧会话 404 |

规则演示 `DEMO_RULE` 从不声明模型调用。`TEMPLATE` 可以来自没有调用模型的策略回复，也可以来自真实模型被检查器拒绝后的回复；以 `model_called` 和 `actual_backend` 区分。超时回退不等于正常模型成功，也不等于 CPU/FPGA 自动切换。

任务 6 的显式 demo-lab 模拟超时仍发布检查后的 `TEMPLATE`，`model_called=false`；超时注入在联调诊断中单独记录，不冒充真实模型超时。默认服务不开放故障接口，详情见 `WORKFLOW_ACCEPTANCE.md`。

## 回执 text-delivery.v1

所有成功发布的轮次在 SSE `answer.ready.data.delivery_receipt`、GET 会话快照的 `turns[].delivery_receipt`、GET `/ui/v1/sessions/{sid}/turns/{request_id}` 返回同一份回执。

| 字段 | 含义 |
|---|---|
| `schema_version` / `delivery_kind` | `text-delivery.v1` / `WEB_TEXT_PUBLISHED` |
| `instance_id, session_id, request_id, operation_id, epoch` | 实例、会话、操作和网页代次 |
| `case_id, case_version, case_sha256` | 实际会话读取的病例身份；不包含病例事实 |
| `answer_sha256` | **最终回答原文 UTF-8 字节 SHA256**；不归一化、不加引号、不加换行 |
| `answer_source` | MODEL / DEMO_RULE / TEMPLATE / TIMEOUT |
| `model_called, actual_backend` | 当前仅允许真实 CPU 调用或 null；不声称 PL |
| `validation_status` | 当前固定 `pass`，表示 A02 关系检查通过，不是临床审核 |
| `validated_monotonic_ns, published_monotonic_ns` | 当前服务主机的单调时钟，十进制字符串；检查不晚于发布 |
| `audio_played, browser_render_verified, user_read_verified` | 当前全部 false，准确限定交付含义 |

回执是程序审计记录及内容一致性证明，不是密码学签名或用户已读证明。上游内部 `digest(text)` 对 JSON 编码文本取摘要，与上述原文 SHA256 不同，不能混用。

网页 epoch 与 A02 业务 Session epoch 分属两层，失败/取消后数值不要求永远相等；转换由接口层完成。跨机器、跨启动的 monotonic 时间不能直接相减。

## 患者上下文与评分

下一轮规划只引用已经发布的患者事实。生成后被拒绝、取消或未发布的候选不能进入上下文。原生模型仍按上游 R0 清空重算，不能依赖未验收的 KV 回滚/前缀缓存。

既有 A02 评分以医生提问事件计算。取消轮次可能保留合格提问的分数；这不代表对应患者回答已交付。第四任务没有修改量表、医学审核或主任讲评逻辑。

## 本机验收与待联调

自动化覆盖正常回执、篡改拦截、重复发布、错误/截断候选、协议错误、真正有效的迟到答案、取消前后边界、SSE/查询/快照一致性、无浏览器恢复及重启失效。

实际模型部署负责人运行 `python -m patient_web.acceptance`。CPU native 模式必须取得真实 MODEL 回答才报告 `PASS_NATIVE_TEXT_DELIVERY`；检查模板会标记 PARTIAL。DEMO 结果只报告 `PASS_DEMO_TEXT_DELIVERY`。真实 CPU/PL/BOARD 和取消后的原生状态静止需要其环境中的联合验收，不能用本机 fixture 代签。

