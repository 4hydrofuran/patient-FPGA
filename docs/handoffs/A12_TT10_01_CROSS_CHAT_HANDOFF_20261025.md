# TT10-01 跨对话交接：无板主体完成，板测隔离现场保留

整理日期：2026-10-25，北京时间。维护者：A。

**结论：TT10-01未完成。source-03无板主体及A53构建通过；source-04复核未收口。首次BOARD在CPU诊断阶段被原余量门禁隔离，新增PL调用0，本轮实板TTFT为null。用户明确要求暂不恢复、保留现场。**

本文依据本机已保存的源码、日志和回执整理。本次没有SSH连接、板端操作、模型运行、测试、构建或恢复。下面的接续步骤是建议，不是新的执行授权；尤其不能将本文视为恢复、终结进程或新板测窗口的授权。

## 1. 接手后先读什么

按以下顺序阅读，避免递归扫描整个工程或重复已通过工作：

1. [AGENTS.md](C:/Patientqwen/AGENTS.md)，以及新对话最新用户指令。本会话用户级策略给出默认`gpt-5.6-sol / High`，不用Terra/Medium，不默认Fast/Ultra；新对话如有更新以最新用户要求为准。实际设置未核实记unknown，不声称已切换、不自动切设置、不启用子代理。
2. [本计划](C:/Patientqwen/docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md)、[PROJECT_STATUS.json](C:/Patientqwen/docs/PROJECT_STATUS.json)中的`a12_ttft10_01_in_progress_20261025`和[A状态](C:/Patientqwen/docs/status/A.md)。A13独立条目保留。
3. 本文，及[停止点进度](C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md)、[机器可读进度](C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.json)。后两份是01:03北京时间的历史记录，不覆盖后来的连接断开事实。
4. [状态设计](C:/Patientqwen/design/qwen35/A12_TT10_01_PREFIX_STATE.md)、[PC主体审计](C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/PC_AUDIT_FINAL.json)、本轮失败日志与只读现场。

路径约定：

| 名称 | 准确位置 |
|---|---|
| 仓库 | `C:/Patientqwen`；不要转到旧`D:/Patientqwen`副本 |
| WSL发行版 | `KV260-A-2204`，仓库映射`/mnt/c/Patientqwen` |
| 本阶段证据根，以下简称E | `C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1` |
| TT10-00冻结对照，简称F | `C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-00-v1` |
| WSL构建根，简称W | `/home/member-a/kv260-build/a12-tt10-01-20261024-v1` |
| 本阶段工具 | `C:/Patientqwen/platform/qwen35/a12/tt10_01_*` |
| 私有运行时头文件 | `C:/Patientqwen/runtime/qwen35_w4a8/a12/tt10_01/` |

E内目录仍使用20261024，是阶段启动日；本轮停止及交接发生于2026-10-25。不要仅按日期判断完成状态。

## 2. 用户目标与仍生效的限制

### 2.1 实际目标

- 以短输入、多轮交互为主，允许精确前缀状态复用；最终目标为模型/服务就绪后，应用接收真实首token的TTFT不超过10秒。
- 当前授权任务是TT10-01：完整状态快照与恢复，先无板一致性，再必要的真实板测；保留原安全检查、失败记录、R0与回退路径。
- TT10-01退出条件是正确命中、完整状态等价、实际少算和TTFT改善。子任务完成也不代表最终10秒验收完成。
- TT10-02尚未开始；A12第11步PENDING。原CPU优化03未在此阶段实施，不改队友01A原件、原03或B核/公共数学。

### 2.2 最新明确指令

1. 用户在恢复提问中选择：**“暂不恢复，保留现场”**。
2. 随后要求：**“现在尽快结束本轮开发任务”**。开发已停止，本地两次新增验证的native均正常exit0。
3. 当前请求仅整理跨对话交接，未撤销上述保留现场要求，也未重新授权开发或恢复。

下个对话如收到“继续开发”，可按其明确范围推进无板工作；**不能据此推断用户已同意原来暂缓的异常监管器终结**。恢复前须确认用户是否明确授权该动作。

### 2.3 工程约束

- 固定现有2026.1 SDK、cortex-a53与依赖；不重装、不全局升级、不使用开发机`-march=native`交叉构建。
- 保留逐次新鲜健康检查、绑定许可、确认回复前逐条fsync、完整输出/meta检查、必要BO同步、单在途和未知DMA隔离。
- 不删除隔离租约、不以换目录宣称设备已恢复，不自动强杀、卸载模块、重启或刷写。
- 既有父包/队友交付/已封存证据保持只读；新修订用独立版本。保留所有失败、不放宽阈值、不删慢例或质量失败样本。
- 源码工作树原本有大量既存修改；不能`git reset/clean`、大范围覆盖、擅自commit/push。共享文档按最新字节合并并保存修改前快照。
- 凭据不写入本文、脚本、argv或日志。已存在隐藏输入传输方案；认证能力不等于恢复授权。

## 3. 完成度总表：严格区分版本

| 项目 | source-03 | source-04 |
|---|---|---|
| 完整前缀状态/独立logits实现 | 已实现 | 沿用，计算及状态逻辑未修改 |
| C++组件 | 15项通过 | 沿用03；另有诊断I/O 7项通过 |
| 完整模型PC验证 | 89项通过 | 未完整重跑89项，不能转记为04通过 |
| 25对真实输入R0/hit一致性 | 通过 | 新的普通应用对照未执行到 |
| 取消/版本错误/损坏等 | PC通过 | 对应逻辑未改；未完整重新执行全部用例 |
| PC构建 | 通过 | 通过 |
| 新诊断内部R0/前缀恢复数值 | 通过 | 已保存gate为equal=true：144条投影流、108个完整logits、混合状态一致 |
| 新诊断与03所有流的最终交叉复核 | 已有03内部证据 | 脚本提前失败，尚未完成 |
| A53交叉构建 | 通过 | 未运行，仅备有构建脚本 |
| 实际部署 | 独立板测包bundle-v2 | 未组新包、未部署 |
| BOARD | CPU诊断阶段隔离，未验收 | NOT_TESTED |
| 实板TTFT | null | null |

### 3.1 source-03实现及已通过验证

- 快照包含固定运行时的attention KV、递归/卷积状态、位置/序列元数据，另外保存完整248320维最后位置logits。
- **关键发现：实际链接版本的`llama_state_get_data`只写架构与memory，不包含logits。** 公共头文件说明不能代替实际源码；审计见`E/STATE_API_AUDIT.json`。独立seq状态导出SHA用于核对恢复完整性。
- 零后缀使用保存的logits和相同的fresh greedy sampler；请求结束清空工作状态，保留受控快照。没有从生成终态删除KV来假定递归状态已回滚。
- 无`SP_TT10_CONFIG`默认原R0；`TT10_PFX_V1`失效后明确记录并R0；`TT10_REQUIRE_HIT`未命中报错。R1/R2未启用。
- 以完整真实分词结果逐token匹配前缀，绑定模型、程序、实际关键库、revision/commit、sidecar、tensor map、模板、契约、布局和运行配置；CPU/PL来源分别绑定。
- 公共中性与病例/case SHA/session/epoch所有者隔离；首个板包仅预计算已审计的中性70token前缀，没有启用病例事实快照。
- 上限2槽、每槽64MiB、另64MiB scratch，合计192MiB规划预留。替换先移除旧槽，失败不保留半新快照。不是完整系统物理峰值证明。
- bridge epoch、job、许可、BO和设备所有权不进入模型快照。PC损坏接口仅在测试编译宏中存在，正式ARM不含该接口。
- 89项模型检查覆盖：旧R0二进制诊断一致；70token恢复的全投影/logits/混合状态；后缀0/1/8/9/16/17/24/32/48；重复恢复；损坏及部分恢复失败；版本/前缀失配；病例/session/epoch隔离；第三槽拒绝；1022/1023长上下文尾块；空输入/越界；25对真实应用输入。另有合作取消、错误程序身份拒绝证据。
- PC与BOARD、不同ISA逐位结果不能混用。长后缀边界通过不等于启用超过128token的前缀快照。

### 3.2 质量限制

25条真实输入全部保留：23条模型候选通过原检查；**V07、V08在R0和hit两侧都被原内容检查拒绝，最终走TEMPLATE回退**。这证明缓存没有改变其结果，不能写成25条模型回答质量均通过。医学教师审核仍PENDING。

原始记录：`E/PC.json`的quality，及`E/pc-run-04/pc-new/V07_*`、`V08_*`。它们必须进入后续质量回归，不能归入原先7条策略输入以规避失败。

### 3.3 source-04本地诊断修订

- 由`E/source-03`独立派生为`E/source-04`；`DERIVATION-04.json`和`diagnostic-resource-04.patch`保留差异。
- 新增`diagnostic_io.hpp`；只改`main.cpp`/`bridge.cpp`的原始诊断文件写入：独占创建、完整写入、fsync后对本文件执行`POSIX_FADV_DONTNEED`。未改模型数学、状态逻辑、许可日志或PL代码。
- 新诊断候选将`prefill_chunk`设为8，减少同时输出的logits数量；普通应用请求仍维持原配置。源代码I/O修订和请求参数修订必须分别说明。
- PC构建及7项真实文件I/O检查通过；`E/pc-diagnostic-04/NUMERICAL.json`保存内部恢复一致gate。
- **DONTNEED是建议，不是CMA回收成功证明。大量诊断页、logits缓冲和分配器压力是待验证的来源，不能将CMA问题宣布已解决。**

## 4. 尚未解决的问题

### P0-A：板端隔离与恢复未获授权

详见第5节。恢复提案存在，但从未执行。连接已断开，现时进程/锁/租约/桌面状态未重新核验。先维持限制，不能直接开新窗口。

### P0-B：CPU阶段失败缺少正常终结通道

失败发生于CPU阶段：父级只在PL启动路径登记`_owned_worker`，CPU worker没有登记。既有finalize-only IPC要求已登记worker正常关闭，因此本次不能直接收口。

还存在健康锁存与关闭路径的问题：`HealthSchedule`在失败后保持blocked，原`Owner.health(closing=True)`仍走同一锁存调度；未来设计须区分“禁止新增计算”和“已证明worker正常退出后的新鲜关闭检查”。**不能简单清除blocked、放宽计算门槛或绕过未知DMA隔离。**

上述CPU正常收口修复尚未实现/验证/部署。需要在新派生版本补合作取消、正常退出、准确失败观察、终结入口与异常分支证据；不能修改当前停泊现场的旧管理器来追认正常退出。

### P0-C：source-04复核脚本两次失败

| 回执 | 真实失败位置 | 状态 |
|---|---|---|
| `E/logs/diagnostic_pc_01.json`，exit1 | 读取`E/BOUNDARY_70.json`，实际位于`E/pc-run-04/BOUNDARY_70.json` | 源码路径已改；失败原件保留 |
| `E/logs/diagnostic_pc_02.json`，exit1 | `tt10_01_diagnostic_pc.py`中`assert j(base/'NUMERICAL.json') == gate` | 未修复；worker正常exit0 |

优先静态排查点：`tt10_01_numeric.concatenated()`以整数position作为logits字典键，JSON落盘后对象键变字符串。保存JSON与内存gate直接比较会出现类型差异；随后与旧JSON中的logits map比较也有同类风险。**尚未重新离线计算证明它是唯一差异，不可仅删断言或强行写PASS。** 应规范化序列化边界，逐项保留全部键和值比较，先复核现存原始数据，再补必要模型用例。

重跑陷阱：`pc-diagnostic-04`、`worker`、`worker-resume`、`rewarm_resume`及诊断目录都已存在，使用独占创建。**修一行后直接再次执行原命令或`--resume`仍可能因目录存在失败。** 先设计新的run/worker/请求ID或只读复核入口，保留旧目录和两次日志；不要删除旧证据重跑。

最终`PC_DIAGNOSTIC_04.json`尚不存在。source-04普通应用对照、与03完整流交叉复核、最终PC汇总及A53构建仍待完成。

### P1：最终验收工具与证据收口

`tt10_01_analyze.py`、`tt10_01_closeout.py`、`tt10_01_final_check.py`是此前准备的未执行草稿，写死了失败的`board_02`、bundle-v2、source-03及正常完成假设。必须在真实新窗口完成后按实际新版本重审；不能直接运行或将旧失败改为exit0。

本阶段没有`BOARD_AUDIT.json`、`SUMMARY.json`、`SEAL.json`。`LOCAL_STOP_CHECK.json`只是停止点检查，不是完整验收封存。不要反复直接运行独占写出的`tt10_01_checkpoint.py`覆盖历史。

## 5. 板端保留现场：历史事实与当前未知

### 5.1 已保存的最后一次只读现场

证据：`E/scene_01/stdout.txt`，回执`E/scene_01/receipt.json`为exit0。以下为历史观察值，**不是现在仍有效的实时断言**。

| 项目 | 观察值 |
|---|---|
| 固定目标 | 本机绑定192.168.2.1 → `ubuntu@192.168.2.2`，固定host key |
| 内核 | `6.8.12-a10irq2`，aarch64 |
| boot_id | `86e4938b-0f65-4166-9237-c547b67e1451` |
| 独立板包 | `/var/lib/kv260-a12/tt10-01-20261024-v1` |
| 窗口ID | `a12-tt10-01-20261024-v1` |
| 监管器 | PID167484，start_ticks5216275，S/`hrtimer_nanosleep` |
| CPU worker | PID167575，父PID167484，start_ticks5223443，S/`pipe_read` |
| 失败标记 | `run-v1/s2/ISOLATED.json`：`HealthBlocked: full-model live extra reserve gate` |
| 内存后测 | MemAvailable 2987932 KiB；CmaFree 52816 KiB |
| 原计算阈值 | MemAvailable≥1114112 KiB，CmaFree≥98304 KiB |
| 精确拒绝瞬间数值 | 未保存，null；不能把上述后测值冒充原瞬间采样 |
| 运行阶段 | `s1/diag_exact`完成；CPU日志已产生成功的`cache_created`，工作状态清空后等stdin；未进入PL路径 |
| 新增真实PL调用 | 0；未启动`s2/worker`，无本轮PL数值/TTFT结果 |
| 退出/释放 | 监管器停泊、租约保持；没有证明正常释放或桌面服务恢复完成 |

中央租约：`/var/lock/kv260-a1/active/lease.json`。规范锁：`/var/lock/kv260-a1/deployment.lock`与`/run/lock/patient-qwen-linear.lock`。不能删除文件、抢占或手动“解锁”来跳过持有者。

### 5.2 本次整理发现的新本机回执

停止点01:03记录中的“外层监测可能仍等待”已不能作为最新连接状态：

- `board_01/receipt.json`：exit255，连接等待认证时关闭，`payload_sent=false`。
- **`board_02/receipt.json`现为exit255，`payload_sent=true`，stderr为`client_loop: send disconnect: Connection reset`（另含sudo提示标记）。** `board_host_exit02.txt`也为255。
- 本机stdout最后仍只有完成`s1/diag_exact`的PROGRESS；没有`WINDOW_NORMAL_RESTORED`、`ALL_WINDOWS_NORMAL_EXIT`或最终READBACK。

**SSH断开不是worker正常退出、租约释放、板卡重启或桌面恢复的证据。** 未确定连接重置原因；本次没有连接板卡，不推断当前boot/PID是否仍存在。旧PID和旧恢复脚本必须重新核对身份，不能直接使用。

### 5.3 恢复提案的授权和风险边界

[恢复提案](C:/Patientqwen/evidence/model_pl_A/20261024-ttft10-01-v1/RECOVERY_PROPOSAL.md)与`platform/qwen35/a12/tt10_01_recover.py`都**未执行**。脚本直接运行默认inspect，但本文也不授权现在连接执行。

提案执行模式并非全程“正常退出”：先只向CPU worker发送一次stdin shutdown，证明exit0；核实无设备/XRT/活动计算、默认overlay及原租约身份后，**对已停泊监管器进行一次受身份约束的pidfd SIGKILL，记录真实异常退出-9**，再接管自然释放的锁并归档原租约。不是杀worker，也不是正常manager退出。该异常动作正是专项确认内容，用户已经暂缓。

脚本固定旧boot/PID/包和现场假设，尚未在本次现场执行验证。以后即使获得授权，也须先重新审查、只读核验当前状态并更新绑定；不得对PID变化、重启后新进程或身份不明者发信号。没有授权时仅推进被允许的无板工作，继续保留现场。

## 6. 关键产物与身份

### 6.1 文件索引

以下均以E或仓库根为基准：

| 产物 | 用途 |
|---|---|
| `E/source-03/`，`DERIVATION-03.json`，`worker-prefix-03.patch` | 已验证的完整状态实现及可追溯差异 |
| `runtime/qwen35_w4a8/a12/tt10_01/prefix_cache.hpp` | 快照存储、身份、namespace与资源约束 |
| `E/source-04/`，`DERIVATION-04.json`，`diagnostic-resource-04.patch` | 尚未板验的诊断资源修订 |
| `runtime/qwen35_w4a8/a12/tt10_01/diagnostic_io.hpp` | 诊断文件同步与缓存建议 |
| `tt10_01_derive.py`、`tt10_01_diagnostic_fix.py` | 两级源码派生工具；现有目录独占写出，不盲目重跑 |
| `tt10_01_pc.py`、`E/pc-run-04/`、`E/PC.json` | source-03最终89项与25对请求原始证据 |
| `E/pc-run-03/`、`PC_PAUSE_REQUEST.json` | 用户曾暂停导致的中断；随后完整pc-run-04通过；不删除、不记成模型失败 |
| `E/CANCEL.json`、`BAD_CONFIG.json` | 实际PC合作取消、错误程序身份拒绝 |
| `tt10_01_diagnostic_pc.py`、`tt10_01_numeric.py` | source-04待修复的复核与严格数值比较 |
| `E/pc-diagnostic-04/` | 04的原始诊断、NUMERICAL与两次正常退出记录 |
| `E/build-arm/`、`logs/build_arm_01.json` | source-03正式A53构建；`build-arm04`尚不存在 |
| `tt10_01_build_arm04.sh` | 已准备、未运行；前置要求真实`PC_DIAGNOSTIC_04.json`存在 |
| `E/candidate/bundle-v2/`、`PACKAGE-02.json` | 已发送的source-03旧包，不能当作04包 |
| `tt10_01_case.py`、`tt10_01_app.py` | 有界用例与实际Session计时适配器 |
| `E/board_driver_reviewed02.py`、`board_02/` | 精确上传脚本、本机传输日志/回执 |
| `E/scene_01/`、`tt10_01_scene.py` | 已保存的只读现场及采集源码 |
| `E/RECOVERY_PROPOSAL.md`、`tt10_01_recover.py` | 暂缓的恢复提案；不是获批/已验证动作 |
| `E/FAILURES_PROGRESS.json`、`PROTECTED_BEFORE.json` | 失败索引与历史保护基线 |

上表`tt10_01_*`均在`C:/Patientqwen/platform/qwen35/a12/`。所有相对证据路径均在E，不要误读同名历史目录。

### 6.2 二进制与父包SHA256

| 对象 | SHA256 |
|---|---|
| source-03 PC：`W/pc/qwen35-a12` | `95c2cafe130510b6b5724ad6d623b7d0a548c2e7673683142892561449d02164` |
| source-03 A53：`E/build-arm/qwen35-a12` | `b620bd89f278fa332cf4dc8a32ddebc817c5879b32dfe366d5022d4bf7a449b6` |
| source-04 PC：`W/pc04/qwen35-a12`，由配置保存的身份 | `e4836476012f64aa0164079b8c7529c5e587517c5914ca8a6886a7f1c29d38f3` |
| 已发送脚本`board_driver_reviewed02.py` | `8447a3e67234589221ba46b3191ce507ef6dfe4b7c54e0f7e32afed71748f70a` |
| TT10-00 CPU02实际部署父manifest | `5f1585015cc0805466b2b39e6be79f4ea5c210f6b69d4aaca9ba08def5f865b0` |

父包为`/var/lib/kv260-a12/tt10-00-cpu02-20261024-v2`。其实际manifest含新鲜preflight刷新，不能拿原模板manifest不同就认定其他文件已漂移；逐项核实，保存实际身份。

模型固定Qwen3.5-0.8B、文本非思考，revision `2fc06364715b967f1860aea9cf38778875588b17`；运行时基准commit `81e39ad34368329b5db77620721510fd91107e80`，含已有A05/A12派生修订。模型/库的完整哈希以配置、manifest和实际装载证据为准。

## 7. 下个开发对话的推荐顺序

### 第一步：明确接续范围，先不碰板

阅读本文与最新用户指令，报告：阶段未完成、连接已重置、板端现况未知、恢复仍暂缓。先获得实际开发指令；不自动恢复或执行旧脚本。

### 第二步：完成无板脚本与故障路径

用户明确继续无板开发后：

1. 按AGENTS阶段要求依次运行历史`check_contracts.py`、新版`qwen35_config.py`，用新的日志名称保留命令与退出码。
2. 为source-04创建新的run/worker/请求命名，先只读复核现有原始诊断；修复对照路径和JSON键类型规范化，保留精确比较和两次失败。
3. 补普通实际Session的R0/hit一致性、EOS/原内容检查、零后缀/必要取消回归与最终PC汇总。按实际源码/版本记录，不自动把89项都重新标到04。
4. 实现CPU故障正常关闭及终结通道；用故障替身/实际CPU验证：计算锁存不解除、合作取消、关闭失败仍保留owner、正常关闭后才新鲜检查/归档、失败值能保存、无未确认DMA时才允许释放。没有相应证据不能进板。
5. 无板门槛满足后再用原2026.1 SDK做新A53构建，保存flags/link/ELF和二进制SHA。构建脚本的独占目录已存在时也要采用新版本，不能覆盖旧产物。

### 第三步：有明确授权后重新核查/恢复现场

只读重新核实准确设备、machine/boot、监管器与worker启动身份、实际包、内核日志、规范锁、租约、设备FD/VMA、ZOCL/overlay、GDM及现有任务。认证和异常终结授权分开处理。

- 若现场与旧观察不同，按真实状态另审恢复方案，不猜PID、不直接执行固定旧脚本。
- 若用户仍暂不恢复，则保持不操作；无板可独立完成，BOARD继续未完成。
- 获批恢复后保留真实异常退出和原租约字节，取得完整释放/恢复证据；不能将旧失败窗口追认为正常完成。

### 第四步：新的独立有界窗口

正常释放/默认平台恢复且身份复核通过后，另建新remote目录、window ID、manifest、源码/二进制pin、请求清单和预算，不重用失败v1。

原冻结预算仅供对照：5000真实PL调用硬上限、预计4608/最坏4752、6请求/后端、1800秒租约、2100秒外层等待、72权重、148显式BO/140591104字节、192MiB快照/scratch规划预留。新方案须按实际工作重新计算、冻结和审查，不能事后扩大旧额度。

PL prefill理论调用为`72 × ceil(新增token/8)`；70token预计算648，107token R0为1008，命中后37token为360。它们是工作量推导，**本阶段实际PL调用仍为0**。预计算、decode、诊断与必要重复都计入新窗口总预算。

重诊断与普通计时分开：先同ISA S1/S2与R0/精确恢复的投影、完整logits、混合/最终状态，再普通真实Session TTFT。每条真实许可都核对新鲜观察、fsync/计数/BO/meta/输出与正常退出；任何余量失败保存精确值并停止新增计算。

### 第五步：达到退出条件才收口

- 25条真实输入/原17条与8变体、7条策略输入分账，V07/V08不移除。
- `TTFT_app`从Session.submit接收文本前到本轮真实首token，包括路由、模板、完整分词、缓存检查与恢复；模型加载/前缀预计算单列，完成预计算才宣布service ready。
- 同一完整输入与同期R0比较，记录真实少算token、PL调用、恢复时间、快照字节、RSS/CMA与普通TTFT。旧52.624秒/50.701秒是不同历史worker口径，不能替代新应用口径。
- 原最小计划每后端只有1对普通R0/hit、固定先R0后hit，不能宣称p95、显著性或最终100请求验收。10秒未达到就记录NOT_MET，并保留下一项路径。
- 完整worker/manager退出、独立/延时无用户检查、锁/租约释放、默认overlay与GDM恢复均有证据后，才写最终BOARD_AUDIT、SUMMARY、REPORT和SEAL。
- 大诊断原件可保留板端、选择回读，但必须写明完整原件位置、每文件/流摘要和回读范围。原包readback_filter设计不等于此次已成功回读；本次只有只读scene，没有最终READBACK。
- 更新共享状态时追加新实际结果，保留本次失败与A13条目；之后才进入TT10-02。

## 8. 回退和历史基线

原默认选择未修改，回退包未覆盖：

1. CPU02：`/var/lib/kv260-a12/cpu02-candidate-20261024-v1`。
2. CPU01组合：`/var/lib/kv260-a12/cpu01-integrated-20261024-v1`。
3. 原健康/00包：依原封存manifest和回退清单，不凭名称猜路径。

回退必须先证明退出、资源和平台状态；当前租约/现场未释放时，不能直接切目录启动回退包。

TT10-00已完成并封存25条真实输入、70token中性前缀和35—46token变化后缀；它没有实现缓存。不能因为TT10-01新失败抹掉TT10-00 PASS。此前原计划00/01/02和队友01A均保留；新缓存没有改原03或默认生产后端。

## 9. 可复制到下个对话的开场说明

> 请先阅读 `C:/Patientqwen/docs/handoffs/A12_TT10_01_CROSS_CHAT_HANDOFF_20261025.md`，核对本地进度、失败回执和最新用户授权，概述TT10-01的准确停止点及下一步。source-03无板主体/A53通过，source-04仍有汇总断言失败；BOARD在CPU阶段余量门禁隔离，无新PL/TTFT结果。本机最新SSH回执是Connection reset，板端当前状态未经重新核验。用户此前明确暂不恢复、保留现场，请不要自动连接恢复、终结进程、释放租约或执行旧脚本。先提出可独立完成的无板接续工作；等我明确指定本轮开发/恢复范围。

本文及伴随receipt仅封存交接内容和本次读取的本机证据身份，不是TT10-01完成封存。不得据此签核BOARD或10秒目标。
