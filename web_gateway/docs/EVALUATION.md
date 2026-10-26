# 第五部分：主任评价与提问依据

## 已实现的流程

1. 当前回合收尾后，用户选择“结束问诊”。忙碌时服务拒绝结束。
2. 应用读取 A02 已记录的提问事件，调用原 `recompute_score_for_host()`，按冻结快照整理中文评价。准备失败时不关闭业务/网页会话，可重试。
3. 原分数、中文分项、证据、待复核项、建议与主任总结一次冻结到内存。成功后关闭问诊；后续读取只返回深拷贝。
4. 页面切到主任场景，显示得分、总结、分项及原始提问。用户可在“评阅意见、评分依据、待复核、问诊记录”之间切换，选择下一病例并开始新问诊。

背景与两张主任立绘使用工作区已有 PNG 的原样副本。评价展示使用 `chief-physician-speaking.png`，查阅记录使用 `chief-physician.png`；这是文字阶段的展示姿态，不是实际语音播放状态。患者场景合成与语音播放不在本次第五部分范围。

主适配目标为用户确认的 **7 寸、1024×600 横屏**。横屏评价模式占满浏览器可用高度，主任场景、得分与主要按钮保持可见，总结/分项/证据在右侧独立滚动。主要按钮至少 48 CSS 像素高，正文 16 CSS 像素；查阅问诊记录在同一阅读区域切换，不跳回长页面。浏览器视口模拟不能替代实屏触控、系统缩放和软键盘的板端验收。

界面已按用户选择的“纸质病历、教师评阅记录”方向进行 Hallmark 优化：暖白纸面、少量批注红、18px 宋体类评阅正文、小号分数与四个直接切换的页签。正文省略已在顶部展示的重复分数句，原始 summary_text 和 rule_score 在 API 中完整保留。设计说明见 PAPER_REVIEW_DESIGN.md。

## 评分含义

沿用 `coverage-v1-draft`：疼痛位置、疼痛性质、起病时间、持续时间、疼痛程度、放射部位、诱发或加重因素、缓解因素、呼吸困难、过敏史，共 10 个分项，每项 10 分。没有新增临床评分、及格线或“优秀”等能力等级。A02 五份业务文件及三份病例仍按上游 SHA256 验证。

重复问题可提供多条证据，但同一话题只获得该项分数。双重否定等问题进入待复核列表，不作为已确认得分。零提问为 0 分、全部话题缺失；所有话题覆盖为 100 分，但仍保留草案/待教师审核状态，不能解释为临床能力合格。

原规则按已记录的提问事件计分。回答后来取消、失败或未发布不自动撤销提问得分；证据会标明 `turn_status`、`answer_published`。若请求在进入业务处理前就取消，可能没有评分事件；网页问题序号与业务 turn_id 因此可能不同，代码按 request_id 关联。

## 返回什么

沿用 `GET /ui/v1/sessions/{sid}/evaluation`，尚未结束返回 409。

| 字段 | 含义 |
|---|---|
| schema_version | chief-evaluation.v1 |
| evaluation_id / instance_id / session_id | 冻结评价、当前进程实例与会话身份 |
| case_id / case_version / case_sha256 | 本场病例身份，不包含隐藏病例事实 |
| frozen_at | 服务端冻结时的 UTC 时间，不参与分数计算 |
| frozen_turn_count / scoring_event_count | 网页提问数与业务评分事件数，可能不同 |
| rule_score | A02 原始分数对象，保持不变，包含 rubric 版本/hash/审核状态 |
| topics | 中文名称、得分、满分、覆盖状态及逐条提问证据 |
| covered_topics / missing_topics | 对应话题 ID 列表 |
| review_items | 待复核问题原文、编号、状态及中文原因 |
| summary_text | 由当前分项与待复核项确定生成的主任文字 |
| summary_status / summary_source / summary_version | READY / RULE_TEMPLATE / chief-summary-v1 |
| recommendations | 由缺项/待复核项生成的建议，无额外模型调用 |
| disclaimer / scoring_note | 草案评分含义、提问计分与回答交付的区别 |

`evaluation_id` 是除 ID 字段自身外的整个对象经稳定键排序、紧凑 JSON 编码后的 UTF-8 SHA256。它便于关联和核对，不是签名。会话及评价只保存在内存；重启后实例和会话失效，没有新增数据库或持久化承诺。

## 给后端部署负责人的增量交付

模型运行时继续只负责患者候选回答，本版主任评价由应用按规则结果生成，不增加第二次模型部署要求。应用已经提供评分整理与总结生成代码，接收方不需在模型内部重写量表或生成分数。

接入时保留本接口字段、旧 rule_score 原值和审核标记；如更新 A02 量表，需要明确核对中文分项映射及总结模板。不能把新量表的未知项静默套入当前解释。

联合验收时除第四任务的模型输出外，请验证：结束后评价可查、与原评分一致、证据指向对应提问、刷新/重复结束不变化、新病例不混入旧证据、取消问题仍遵循原计分约定。机器格式在 `contracts/chief-evaluation.schema.json`；本机自动化及页面验收记录在 `VERIFICATION.json`。

现有 HTTP 验收工具可增加 `--include-evaluation`，同时校验评价身份/摘要、评分与提问证据，以及重复结束后的结果稳定性：

```bash
python -m patient_web.acceptance --base-url http://127.0.0.1:8767 \
  --expected-backend demo --include-evaluation --output /actual/new-evaluation-result.json
```

路径需替换为实际新文件，父目录必须存在；服务须无正在使用的问诊会话。真实环境仍使用 `--expected-backend native`，并按 MODEL_HANDOFF.md 补充原生与板端证据。主任总结为规则模板，其正确运行无需再次调用大语言模型。
