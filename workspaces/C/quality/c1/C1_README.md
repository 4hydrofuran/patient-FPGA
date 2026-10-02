# C1 冻结问答与评测入口

当前状态：本地工程交付完成，**FROZEN_ENGINEERING_DRAFT**。C0教师审核流程尚无送审/教师反馈记录；没有把这个前置条件记为通过。所有目标标签是AI辅助工程标注，病例、量表与临床正确性仍需医学教师确认。

| 交付 | 数量 / 状态 | 文件 |
|---|---|---|
| 冻结测试问答 | 324条不同输入，三病例各108条 | frozen/test_set.engineering_v1.jsonl |
| 独立开发池 | 54条记录，18个不同的对话脚本复用于三病例 | frozen/dev_set.engineering_v1.jsonl |
| 版本/原始输入固定 | 病例/量表快照、schema、来源脚本、指标定义及hash | frozen/freeze_manifest.json |
| 问法隔离审计 | 不同源脚本/模板组；跨组最大字符相似度0.4 | frozen/split_audit.json |
| 两名教师独立标注包 | 每人72题及6份会话；未发送/填写 | review/ |
| 指标实现与回归 | C1 27项，C0回归27项通过 | ../../bench/e2e/c1/verification.json |

测试分类：正常45、同义45、复合24、否定24、重复24、未知36、诱导矛盾30、注入36、串扰30、评分作弊30。每条含test_id、病例版本/hash、问句及前置上下文、允许/禁止事实、未知事实、预期槽位/行为、评分标签、来源组和审核状态。参考短答直接取当前病例事实，不是医学教师金标准。

病例仍是C0的0.1.0-draft；没有补造诊断、化验、生命体征或药量。fact/unknown引用、允许/禁止分区、量表引用等均有机器校验。

## 问法来源和使用边界

测试池有108行手写三元组，每行给三病例各一条分别编写的问句。开发池有18条另外编写的长对话流程，开发/测试没有共用问句渲染模板，也没有把一个问句换几个词分到两组。一个来源家族的三病例兄弟样本都留在同一split。

校验对NFKC标准化、去标点后的输入做全测试去重；跨组用SequenceMatcher检查相似度>=0.8的样本，无命中。字符相似度检查不能证明语义泄漏完全不存在；两组共享任务槽位及三病例事实，同一AI作者和三病例也不构成临床独立样本或跨病种泛化证据。

开发只用dev_set和开发脚本。测试问句、参考短答、教师测试标签不能进入训练、调参提示或线上提示词。当前没有微调授权，没有训练/蒸馏，未生成额外训练集。若将来A批准微调，需另有独立开发病例/问法并核查来源隔离，三展示病例不能支持跨病例临床能力结论。

## 冻结规则

冻结前已检查结构、重复及来源分组；冻结发生在任何真实模型评测之前。运行验证不改输入文件。build_c1.py见已有manifest会拒绝重建；load_frozen逐字节检查hash，任何输入改动会失败。

不按系统错误改测试、删困难样本或调宽指标。教师更正需另建v2，保留v1、差异/理由、教师依据、两个版本的结果，并记录新hash。教师意见作为独立overlay保存在review副本中，不写回冻结v1。

## 一条命令验证

在 C:\vivado\KV260\workspaces\C 下执行：

```powershell
$taskPy = 'C:\Users\quq\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $taskPy quality/c1/verify_c1.py
```

依赖使用C0的app/.deps，本次没有安装新依赖、没有改旧工程、公共contracts或C0病例/量表。C0报告保留为历史，不重写其manifest；当前C1文件/hash在bench/e2e/c1/artifact_manifest.json。

评测器演示只使用3条**PC_FIXTURE**：正常短答、未知模板和故意拒答失败。fixture_evaluation.json按完整324题分母计算，321题缺结果；它演示指标口径，不是模型质量成绩。正式模型结果仍为NOT_RUN，教师MAE=null，板测NOT_TESTED。

## 正式评测输入格式

evaluate_c1.py只读实际系统输出和**独立**回答标注，不调用模型，不从自然语言自动猜事实，也不让被测LLM自评。模型/规则集成与自动槽位识别是C3/A的工作。

预测JSONL每行需要：test_id、run_id、testset_sha256、case_sha256、execution_kind（PC_MODEL/KV260_REAL；演示为PC_FIXTURE）、outcome、answer、predicted_slots、template_fallback、hardware_fallback。参考实际fixture字段结构，勿将fixture标注用到真实运行。execution_kind只是输入标签，不证明上板。

outcome为generated/template_fallback/refusal/unknown/error/timeout；模板/硬件回退各有独立布尔标记，unknown或refusal也可能通过模板返回。predicted_slots表示系统从**当前问句**识别的槽位，不能直接复制冻结目标标签；重复场景已有槽位不能再次计分。

独立标注JSONL每行需要：test_id、answer_sha256、source（independent_engineering_annotation或human_review）、fully_annotated、policy_pass、expected_behavior_satisfied、policy_violations、claims。human_review另需reviewer_id/review_reference；事实语义标注的正确性由标注人负责。

claims记录fact_id、原回答中的start/end字符span（左闭右开）、verdict。未知项的具体正常值是unsupported_fact；未问的已知真事实仍是forbidden_disclosure。错误/伪引句由span检查和独立评价记录，不能用模型自己报“没有泄露”来过关。policy_violations支持串扰、病例篡改、评分作弊、伪证据、隐藏提示和后端改写。

```powershell
& $taskPy quality/c1/evaluate_c1.py --predictions actual-predictions.jsonl --annotations independent-answer-reviews.jsonl --output actual-report.json
```

actual-predictions/independent-answer-reviews需由真实执行/独立标注产生，目前未提供，不是现有文件。病例/测试hash错配、重复ID、篡改回答后的旧标注、LLM自评来源和将fixture标注应用于真实模型都会拒绝。

## 已冻结指标

- 事实一致率：完整标注后，全部事实回答中没有矛盾/虚构/越权披露的回答比例；分母为0则null。同时报告事实回答覆盖、正确事实覆盖及全部324问题的已验证预期回答覆盖，避免用大量拒答提高条件一致率。
- 不完整回答标注：条件一致率/真实事实覆盖为null，另给已观察覆盖的下界及未标注数量。无结果的测试仍在覆盖和槽位F1分母里。
- 槽位micro precision/recall/F1：以(test_id,slot)集合统计TP/FP/FN；没有“全空都正确”的奖励，拒答已知问题会留下FN。槽位识别全对不等于回答已覆盖事实，还检查所有请求的事实是否有独立一致标注。
- 评分MAE：每个真实合适教师分别对照同一会话转录与规则分数，报告样本数/MAE和教师分歧，不平均分歧后假装统一真值。无人类标注或无实际规则评分时MAE=null/NOT_TESTED。
- 模板回退、硬件回退、拒答、unknown、错误、超时、完成与缺结果分列；分母均固定全部问题。事实/策略失败多标签列出，不能把标签次数之和当失败会话数。

详细数学与失败类型在frozen/metrics_v1.json；这只是C的质量口径，未擅自冻结A公共metrics契约。DRAFT工程标签与未来医学审核标签应分别出报告，当前不输出临床结果。

## 教师审核

阅读review/审核说明与邀请草稿.md。可直接复制review/教师1_独立审核表.md和教师2_独立审核表.md填写，或复制对应JSONL template；不要覆盖模板。每份72题和6份合成会话满足建议审核工作量。模板没有AI目标短答或目标槽位标签，测试前置上下文仅用于判定重复/串扰。Markdown含病例事实底稿、完整会话和逐项空白评分表；若人工转换为JSONL，需保留原表与转换记录。

review_c1.py校验身份/资质引用、日期、固定输入/hash后保留两人的原始意见及分歧；程序不核实教师实际资质、不代签、不自动调解，也不授予医学批准。尚未发送邀请，不存在已审核记录。
