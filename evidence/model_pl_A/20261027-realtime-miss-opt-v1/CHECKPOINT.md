# 当前继续位置：运行时与部署副本已验实，待归档/上传收口

最新核对：198组原表达及198组最终compact/3线程配对通过；最终408次真实模型请求包含取消/拒绝，正常worker exit0。
新鲜真实浏览器25题中位879.0→618.3ms，23/25低于1秒，答案缓存命中0；部署副本另测622.8ms且25次模型调用、正常退出。
实际197条目录的缺失项触发模型1次，cache/policy/评分/归档通过；43测试和15浏览器协议回归通过。
最终ARM不是下文旧15a2哈希：SDK强制覆盖参数已定位，正确A53构建为arm-v3-a53/qwen35-a12，SHA bb66432dafdcda9d990f08b0c2e766e0c9d3de82070177199183268b069047fc；actual flags.make有-mcpu=cortex-a53。
包内ARM二进制/身份已重绑，294运行时文件和PC二进制/配置未变；新离线preflight通过。
No-space试验因1/11回放、最慢2.282秒未选；部署仍34-prefix/allowed-compact-01/32输出/22320预算。
FINAL_REVIEW.json=PASS_PC_RUNTIME_PACKAGE_SOURCE_VERIFIED，报告/总结/5份治理文档已更新，config-final-command exit0。
本轮受控模型/HTTP/浏览器句柄全部正常关闭。剩余：archive_delivery.py封ZIP与SHA；将明确文件清单复制到干净worktree新codex分支、提交推送并核远端；最终完成审计后update_goal complete。原工作区不要stage all。

以下是较早继续记录，遇到冲突以上述实际新证据为准：

用户目标：缓存未命中必须实时模型，4小时内继续优化完整可用答案显示。原Goal仍active；未执行BOARD。

- 计划：docs/A12_REALTIME_MISS_OPTIMIZATION_4H_PLAN_20261027.md。M0两个保护检查exit0。
- 新native派生脚本platform/qwen35/a12/realtime_draft_derive.py；只改main.cpp，source-v3其余文件与sealed source-04同SHA；实时模型对输入事实草稿每token argmax+EOS验证，不读答案缓存。错草稿全清状态+恢复中性前缀+完整prompt串行重放。
- PC v3：/home/member-a/kv260-build/a12-realtime-draft-20261027-v1/pc-v3/qwen35-a12，SHA64b6ebe583dc6d4f25cb21991548fed6f9816de02140b539ec924268f1efc925。
- ARM v3：同目录arm-v3/qwen35-a12，SHA15a2c55794b8c77e33815fc07c664be4938649757cd26ad958a7c474a2704882；SDK2026.1/A53交叉构建exit0，未上板。
- 新NativePL optional generation_strategy；ready能力及逐token回执校验；manager只附加timing元数据。默认串行路径不改变。
- 原24上限在第39组duration+severity无EOS（保留pairs198-v2失败）；旧目录有3条24输出token，需要另取EOS。新连续候选32输出，1024 context、8 ubatch不变，保守预算22320（两次11160），普通窗口仍原24/4320预算。
- pairs198-t2-32已PASS：198组serial/draft逐token输出一致，403真实请求，6故意错误草稿正确重放。纯native中位serial1346.194→draft1022.916ms（这是198组含双事实，不是25题网页）。worker exit0。
- 11个单事实smoke：2线程原表达draft660.9ms；3线程原表达607.2；3线程compact547.2；2线程compact590.5。均实际模型11/11接受、错草稿2次通过。
- compact_fact_prompt.py只从原forms选择较短完整表达作为模型输入（非答案交付），策略allowed-compact-01；中性SYSTEM/header/prefix仍34；独立live_miss_prompt_policy_sha256。不改checker。
- 43网页tests在compact接入前通过，需最终再跑。新test_realtime_draft.py含能力/伪回执/完整重放/22320预算保护。

当前真实模型执行：functions exec_command session 35435，pairs198-final-command / pairs198-final目录，v3/3线程/compact/32输出/198组、6早期错草稿，加late reject、缺EOS、R0拒绝、验证中SIGUSR1取消与下一问恢复。最新103/198全部接受，取消恢复已过；继续必须poll同handle，不因超时重启。

准备好的新CLI：realtime_draft_prepare.py（尚未执行），基于旧cache包复制独立候选，更新ARM二进制/身份/连续32/预算22320/可选compact与3线程；普通24保持；缓存目录来源仍原facts-only-02，不冒充新生成策略。answer_cache_serve_pc新增--mode realtime、--binary、--pc-prefix-config、--compact，纯realtime不创建缓存；answer_cache_browser新增realtime且强制MODEL/CPU_REFERENCE/model_called及目标验证回执。realtime_browser_compare.py --equivalent-forms独立原checker核验完整事实，允许短表达改变措辞。

后续必须：
1. 等最终198结束，inspect RESULT/actual取消与重放证据。
2. 单独新鲜原v2/live服务+Edge25题，正常stop；单独新v3/realtime/compact/3线程服务+25题，正常stop；比较同问题/事实完整显示。不要并行CPU性能实验。
3. 新部署包准备到release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32；用pairs198-final/prefix-config.json作PC配置。ARM/PC路径如上，--threads3 --compact。跑offline package、真实partial197缓存miss/hit策略会话（answer_cache_checks_pc支持新flags和新profile），部署副本纯realtime真实browser25题与正常关闭。
4. 再跑43测试/相关浏览器回归；记实际结果，生成REPORT/CSV/source pins/失败原样保留，更新5份状态doc+handoff，标准命名独立ZIP+SHA。报告需区分原25网页875ms和本轮新鲜A/B、198底层数据；新的BOARD仍NOT_TESTED/null。
5. 不要只凭intent/绿色JSON标Goal complete。finalizer必须核对真实回执/源码与被测包，全部无板必需项完成才update_goal complete。可按前次用户仓库上传授权上传独立新分支，但先完成实际交付。

已关闭句柄：63990/5941/31486/18707/35371(失败exit1)/73219(PASS)、80204/94592、72429/96555/85656。不要重启这些。原工作区有大量无关改动，不stage all；上次干净发布worktree为C:/Patientqwen_publish/a12_fast_response_cache_20261027（d9ed467，已push原cache交付）。
