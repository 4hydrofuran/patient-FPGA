# A12 无板后续交接（2026-10-25）

本轮完成三项独立无板工作：新短提示词的真实 CPU 验证、完整诊断原件的电脑导出/核对工具、请求级日志 PC 原型。**新短提示词质量仍未验收；新日志没有接入板端；BOARD 与板端时延收益仍为 NOT_TESTED/null。** 已上传的普通 R0/warm/hit 包保持原字节，不加入这些候选。

## 1. 短提示词：数值一致，内容关口未通过

使用既有 source-04 x86 CPU 程序、相同模型/模板，保留冻结的25个模型输入与7个无模型策略输入。重新分词，公共前缀止于动态问题之前，重新绑定提示词、输入、前缀、程序/库身份；旧70-token前缀及旧绑定均被拒绝。只在隔离快照中修改两个实验的提示词构造，不改默认 checker、事实、公共 ABI、B 核或已发布包。

| 方案 | 中性前缀 token | 全输入 token | 命中后新算 token | 模型内容通过 | 不通过 ID |
| --- | ---: | --- | --- | --- | --- |
| 此前冻结25项对照 | 沿用旧证据 | 沿用旧证据 | 沿用旧证据 | 23/25 | V07、V08 |
| 当前用户选定短提示词 | 27 | 62～73 | 35～46 | 20/25 | DEV-002、DEV-005、DEV-011、V07、V08 |
| 问题前逐字输出指令 | 57 | 82～93 | 25～36 | 20/25 | DEV-002、DEV-012、DEV-014、V07、V08 |
| 问题前加强复制指令 | 66 | 91～102 | 25～36 | 21/25 | DEV-002、DEV-012、V02、V08 |

每组25对 R0/hit 的文本/token/EOS、末位置 logits、完整混合状态指纹均一致，7个策略项保持零模型调用，每组两个 worker 正常 exit0，无原始诊断转储。**一致性不等于内容通过**：所有原始拒绝和模板交付来源均保留，模板兜底不算模型成功，checker 和事实门槛未放宽。有限语法检查也不是医学审核。

没有一组达到16～24新算 token；当前不能按该假设承诺“6～10秒首token、11～17秒短回答”。CPU耗时不折算板端收益。三个提示词方案均不生成新的板端候选，第一轮普通探测仍用原107/70/37-token冻结输入。

证据：

- [当前短提示词](C:/Patientqwen/evidence/model_pl_A/20261025-short-prompt-offline-v3/RESULT.json)、[质量原始结果](C:/Patientqwen/evidence/model_pl_A/20261025-short-prompt-offline-v3/QUALITY.json)。
- [逐字输出实验](C:/Patientqwen/evidence/model_pl_A/20261025-short-prompt-copy-before-question-v1/RESULT.json)、[加强复制实验](C:/Patientqwen/evidence/model_pl_A/20261025-short-prompt-verbatim-v1/RESULT.json)。
- 初版准备将 schema.json 当病例而拒绝、第二版以 Python tuple 对 JSON list 比较而拒绝的两次准备失败，保存在 `20261025-short-prompt-offline-v1/FAILURE.json`、`v2/FAILURE.json`。两次均在模型运行前结束；修正为三份病例明确清单及保留类型的规范JSON比较，不改变实际事实。

## 2. 完整原件导出与电脑核对

新增 [offline_diag_handoff.py](C:/Patientqwen/platform/qwen35/a12/offline_diag_handoff.py) 和 [回放工具](C:/Patientqwen/platform/qwen35/a12/offline_diag_replay.py)，独立于暂停中的 CMA 读取候选。导出入口仅允许 Linux x86 PC，ARM/BOARD 绑定没有实现。默认 plan 只读小 manifest 和文件元数据，不执行模型、PL、网络或板端恢复。

导出端按1 MiB块读取全部原始文件，同次读取完成SHA和ZIP写入，输出包SHA在写入时计算；源文件每份只读一次。检查私有目录/文件、无符号链接、文件身份/大小及完整库存；同FD fsync与DONTNEED失败即拒绝，不把建议成功当成缓存/CMA释放。单文件上限32 MiB，原件总量上限3 GiB，文件数上限24576，元数据也有界。

电脑端先校验收到的完整包SHA，再直接从ZIP流式解压核对；每份解压后的原始字节只消费一次，同时计算文件SHA、全部24层 gate/up/down拼接值、全位置logits和完整混合状态比较。外层包校验和解压核对是两个不同读取阶段，未声称整个电脑回放只读一遍。

实际使用既有 PC 完整原件进行独立副本回放：**4542文件、566008080字节**；全部文件SHA与原件一致，全部比较字段与未改动的旧比较器完全相同。ZIP为522136651字节，SHA256 `e38636104669a49da831ec00ee15ed24b382166869d343e4ca40412441a3e78c`，保存在既有WSL的私有工作目录，不纳入Git。

回放进程峰值RSS为33888 KiB（约33.1 MiB），仅为本次PC进程观测；不包含系统页缓存，也不证明板端CMA峰值或恢复。回放还执行了PC副本建立和旧比较器参考读取，其额外I/O明确留在电脑侧。板端采集、释放后导出绑定、真实传输与背压仍未测试/启用。

最终16项 Linux PC 测试通过，涵盖损坏、缺件、重复ZIP条目、路径越界/链接、错误摘要、缺层/形状、重复读取、文件替换及缓存建议失败。测试构造重复条目时的ZipFile警告是预期负例。

详见 [完整回放结果](C:/Patientqwen/evidence/model_pl_A/20261025-offline-followup-v1/full-raw-replay-01/RESULT.json)、[最终16项测试](C:/Patientqwen/evidence/model_pl_A/20261025-offline-followup-v1/unit-tests-02/RESULT.json)。

## 3. 请求级日志原型：保留每次新鲜检查

新增 [request_journal_candidate.py](C:/Patientqwen/platform/qwen35/a12/request_journal_candidate.py)，只作为PC控制实验的 mixin；真实设备或ARM在创建进程前拒绝。原冻结许可循环、双序号、顺序、所有权/健康检查及5000总提交硬上限不变，不增加许可复用或批许可。

实验改变的是日志持久化粒度：请求BEGIN先成功持久化，才允许有界提交；逐提交只维护固定64条环和累计SHA/计数；调用者独立核验结果、累计完成、零在途和状态清理后，才持久化END。最多三个不同请求ID。启动、权重、关闭、拒绝与故障继续立即持久化。BEGIN无成功END表示未知，必须保留所有权，不自动重放、退款提交预算或释放。这里的累计完成参数只是可信调用者断言，**不构成硬件完成证明**；板端接入必须连接既有结果/meta/状态核验。

真实子进程/socket + 原许可循环的PC对照：1000次模拟提交，两版所有权检查均1005次、健康检查均1004次；持久化记录由1005条降到7条，其中1000条逐提交记录变为BEGIN/END两条，其他生命周期记录保留；环最多64条，覆盖936条旧细节。此为结构变化，未把模拟许可计为真实PL调用，也没有把记录减少比例当成时延减少比例。

最终14项测试通过，包含三请求、无活动请求、预算越界、重用ID/嵌套请求、旧序号、原所有权/健康失败、取消、无效完成、日志append边界故障及ARM/真实设备拒绝。日志故障用append边界注入，未声称实际磁盘断电/损坏测试。原10/14项较早测试和记录保留，不重复累计为独立验收。

本原型尚无板端绑定、异常控制端集成、真实本地持久化故障/崩溃恢复或板端A/B计时；持续日志设备失效时保持隔离，不保证能继续写出关闭记录。因此它不能替代原严格管理器，也不进入普通探测包。详见 [最终测试](C:/Patientqwen/evidence/model_pl_A/20261025-offline-followup-v1/request-journal-tests-03/RESULT.json)、[结构对照与两版原始日志](C:/Patientqwen/evidence/model_pl_A/20261025-offline-followup-v1/request-journal-tests-03/STRUCTURAL_COMPARISON.json)。

## 4. 顺序与未完成项

1. 继续保留现有故障与安全门槛。不得把当前PC通过当作板端故障恢复或独立释放。第一轮计算仍需当前故障恢复、独立安全释放、新鲜前置审查和独立计算窗口绑定；本轮未连接板卡，不更新释放结论。
2. 先单独运行已冻结的普通R0/warm/hit资源探测包，取得资源、输入到有效回答、正常关闭和独立释放证据，不掺入这三个提示词或日志候选。
3. 内容问题继续在PC隔离修复；只有25项全部通过既有内容/EOS门槛且身份重新冻结后，才考虑新短提示词的独立包。不得筛掉失败输入或依赖模板兜底宣布模型通过。
4. 如需推进日志候选，先补真实结果核验/异常控制端绑定与崩溃持久性审查；随后另包做同输入、同工作量的单变量板端A/B。检查位置和批许可仍是后续独立工作，未实现/启用。
5. 完整数值采集/回传、TT10最终时延、A12第11步、长时间资源稳定和医学/教师审核仍有独立未通过项；不能称“整个项目只剩上板”。

原包ZIP SHA256仍应为 `acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`。本轮只新增本地代码/证据/文档，未提交推送、部署、恢复、加载/卸载平台、刷写或改B/公共ABI。历史契约保护及新版配置检查exit0，旧契约DRAFT及runtime/BOARD NOT_TESTED保留。复杂设计、调试及证据验收未委派DeepSeek或子代理；实际模型设置unknown。

命令、退出码、源码快照、哈希和最终保持性复核在 [本轮证据目录](C:/Patientqwen/evidence/model_pl_A/20261025-offline-followup-v1/)；主入口为 `FINAL_REVIEW.json` 和 `COMMANDS.json`。
