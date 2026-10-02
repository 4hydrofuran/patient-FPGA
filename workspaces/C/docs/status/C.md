# 成员C状态

2026-10-02 当前 C04：PC_ENGINEERING_PACKAGE_COMPLETE_FINAL_QUALITY_AND_LICENSE_PENDING。工程冻结、103 项回归、30 次新 worker 与 200 次模块循环成功；最终 zip 独立解压、离线安装、49 项工程检查及真实 ASR/流式/TTS 自测通过。三份固定 ARM64 wheel/hash/ELF 检查只是安装准备。候选无模型资源/私人录音，未发布/发 A/替换默认；真人最终质量、许可、物理断网 OS 重启、实际出声和板端待验收。入口 docs/handoffs/C04.md、voice_C/C04_README.md。首轮独立自测的 guard 默认 stderr 冲突已修正，失败包与日志保留。

## C03 历史状态

2026-10-02，北京时间。当前 C03 麦克风补充：PC_ENGINEERING_AND_MICROPHONE_CAPTURE_COMPLETE_HUMAN_QUALITY_PENDING。

已接入 Windows 本地麦克风客户端；真实 Realtek 10 秒、160000 样本、50 块与流式 worker ACK/hash 一致，无溢出，设备已释放、原音频不留存。用户确认没有朗读，最终文字为空，真人质量待自行测试。原环境与新建 .venv_mic 各 99 项回归通过，依赖版本和 wheel hash 不变；前两次失败日志保留。入口 voice_C/MICROPHONE_README.md、docs/handoffs/C03_麦克风补充.md；证据 voice_C/evidence/c03_mic。C02 人工听评、学生 CER、许可证、板测仍待完成。

## 原 C03 无需麦克风阶段的历史状态

2026-10-02，同日较早阶段，PC_ENGINEERING_COMPLETE_MICROPHONE_AND_HUMAN_QUALITY_PENDING。

已实现显式流式 ASR、严格序号与 epoch、partial 仅显示、唯一 final、ACK 后才能删 PCM、单任务/队列 2、半双工、取消/reset 与 15 秒空闲释放。89 项检查通过；42 次加速逐块与 14 次按音频原时长重放成功，56 次最终文字与 C01 相同；21 次端点/合成短否定探针留档。端点仅提示，不自动截断。

用户本次不授权麦克风录音，实际声卡和板卡未打开。授权学生录音、真人语音结束标注、C02 14 条人工盲听、权重外发许可仍待确认。实际首音、整机、ARM64、板端、2 小时稳定性未测，未向 A 发送或替换默认。

首次 C03 回归曾重写两份 C02 自测探针，原摘要保留，原完整内容未恢复；事件如实记录。已改为可配置新测试输出目录。正式 C02 138 次测量、音频、盲听与 C00/C01/旧 C0/C1 测量保持原内容。入口 docs/handoffs/C03.md、voice_C/C03_README.md、PROJECT_STATUS.json。

以下为2026-10-01旧版C0/C1历史状态，保留其完成量和未完成关口；不按编号转记为新C00/C01通过，也尚未实际交付给A。

历史执行日：2026-10-01（北京时间）。旧版任务C1。

状态：C1本地工程交付完成，FROZEN_ENGINEERING_DRAFT；C0教师送审前置与C1独立教师审核未完成，不能称全部验收关口通过。

已完成：C0的三病例/22项规则量表/领域PC证明和API需求提案保留；C1冻结324条唯一测试输入（三病例各108），另建54条开发记录（18个不同脚本），按来源/模板家族隔离并记录hash；冻结事实一致/全问题覆盖、槽位P/R/F1、分教师评分MAE、回退及失败口径；完成评测器、人工分歧比较器与审核包。

真实验证：C1 27项及C0 27项回归通过；8项C0领域输入、13个旧源文件和执行包20项hash匹配。实际命令/退出码/原始日志在bench/e2e/c1/verification.json；当前交付hash在artifact_manifest.json。C0日志及manifest保持历史版本。

测试SHA256：e5cb45b6e8d4a063de03f68526ee4ad350c1456322fc6b9c46e681cfa685a802。病例/量表仍为0.1.0-draft / DRAFT。审核身份、批准依据均空白；每人72题及6份合成会话材料已备，邀请未发送，已审0条。AI工程标签不能称医学真值；字符隔离不能证明临床独立或跨病种泛化。正式审核保留教师原意见、分歧和版本依据。

公共契约：null（只有执行包草案和C提案，未冻结）。源commit/结束commit：null（本地独立C目录，无Git）。没有合main、PR、发布或创建其他聊天。

真实系统评测：NOT_RUN；教师MAE=null/NOT_TESTED；板端/临床验收：NOT_TESTED。3条PC_FIXTURE仅验证评测CLI口径，不能当模型质量成绩。C0意图为可信工程标注，不是自动理解能力验收。未连接KV260、未运行ASR/TTS/LLM/PL。

待提供：C0真实送审记录、医学教师/课程量表及送审渠道；A0/A1交接/冻结API/rootfs/ABI路径；实际设备已有/借用情况；团队报名凭证、完整AMD/校赛规则及AI声明要求。C1已向用户异步请求医学审核参考和送审记录，尚未收到回复。

历史入口：docs/handoffs/C1.md、quality/c1/C1_README.md。教师意见写独立副本；更正冻结数据另建版本，不为提分改测试。旧C2/C3没有执行，后续按新版C00—C07而非旧阶段表推进。C0/C1 manifest与日志保持历史内容，docs/status/C.md的活动更新会使其旧历史hash与当前文件不同，这是本次指导切换的已记录变更。
