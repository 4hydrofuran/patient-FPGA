# A 状态

2026-10-23 最新：A11 open错误8已定位并修复。4KiB sx BO落到34507137024高地址而被低2GiB检查拒绝；私有分配对齐改8192，同诊断库单变量板测open0/close0、四IO地址合法、worker/manager正常exit0。独立后验默认PL/GDM恢复、无ZOCL/FD/VMA/持锁/active lease；0计算，A11 NOT_PASSED、A12 NOT_ELIGIBLE。以下旧状态为历史快照。证据`evidence/mlp_board_A/20261023-open-investigation-v1/REPORT.md`。

2026-10-23 最新最终收口：**PASS_CLOSEOUT_ONLY_NOT_A11**。按用户仅收口授权，重新核实8851无设备/子进程/在途命令后，仅一次pidfd定向SIGUSR1交接；新v2工具接管原双锁、原租约原子归档、移除失效私有socket，正常退出0。45.04秒后独立完整读回：默认PL applied、GDM active、无ZOCL、FD0/VMA0、两把锁无人持有、active lease不存在、所有已知等待者退出；没有新内核诊断。6.03秒收口，最高采样31.396°C；本轮0计算/硬件装卸/服务修改/重启/刷写。PC最终16方法及独立审计exit0；v1误用历史日志基线导致exit2、未发信号，原失败保留，独立v2修正并增加真实冻结包组合测试。旧监督器是专项信号退出，不追认为正常worker退出。A11仍0真实MLP提交/NOT_PASSED，A12不具备条件。报告`evidence/mlp_board_A/20261023-final-closeout-v1/REPORT.md`，跨对话入口`docs/handoffs/A11_CROSS_CHAT_HANDOFF_20261023.md`。下方“锁仍保留”等全部是历史快照；未关机，本快照不是持续监控。

2026-10-23 最新v3仅收尾：**默认PL/GDM恢复已确认，但最终锁/租约未收口**。新授权+只读重核后，仅定向交接旧6174；普通remove/rmmod/load-default/GDM-start均exit0。finalize前出现PROCESS_OR_FD_TABLE_CHANGED，v3硬停，未热改/重试。56.176秒后独立完整扫描FD0/VMA0、ZOCL不存在、默认applied/GDM active，最高采样30.153°C；2条已审查default-overlay警告保留、无未审查新诊断。8851无native映射/子进程但仍持双锁/原租约，状态HARD_STOP_RECONCILE_ONLY、无在途管理命令；不能称维护窗口完成。0计算/重启/刷写，A11未过/A12不进入。PC传输10方法+真实停止2方法/离线审计exit0，路径/可选文件/Windows运行域失败已保留并修复或改用WSL；旧88/523/88/31封存不变。报告`evidence/mlp_board_A/20261023-cleanup-board-v3/REPORT.md`。下一步仅审查finalize协议，不重做已成功硬件操作。以下6174/测试overlay仍在等均为历史。

2026-10-23 收尾v3电脑修复：只在PC/WSL新增独立候选，取消跨扫描全局PID集合相等条件但保留原完整FD/VMA/refcount/内核/锁门禁；窄范围proc暂态最多4次只读观察后可查询暂停，同一监督器显式续接、已完成步骤不重放。硬件命令未知/失败硬停止，保留子进程/锁，不强杀；root-only本地控制无TCP/任意命令。30方法PC（含真实WSL锁/socket、冻结原失败及实际adapter模拟组合）exit0，旧88/523/88封存不变。约27KB候选NOT_ACCEPTED/BOARD NOT_TESTED。无新板连接或动作，下方6174/温度仅最后历史读回；默认恢复仍未完成，A11未过。方案`docs/A11_CLEANUP_RECOVERY_PLAN_20261023.md`，报告`evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/REPORT.md`。需要新统一维护授权和实时核验后才交接恢复；不自动A11/A12。

2026-10-23 最新仅收尾覆盖：两次专项授权后，原worker3308/manager3202及首次收尾5322分别定向SIGUSR1退出；原64KiB设备映射消失、ZOCL refcount0。续接接管锁后3次完整扫描因全局进程集合不同未通过，第四次PROCESS_SET_CHANGED，按规则停止，未发出任何卸载/配置恢复命令。最新只读完整扫描无设备FD/VMA，27.083–28.878°C、无新增内核文本；新收尾6174睡眠持双锁/原租约，测试overlay/ZOCL仍在、GDM inactive，默认未恢复。是收尾流程稳定性/续接设计缺口，不称新FPGA故障。6+13方法PC通过、旧88/523项封存不变，A11 NOT_PASSED、A12不具备条件。报告`evidence/mlp_board_A/20261023-recovery-continuation-v1/REPORT.md`。下方“未授权、3308残留VMA”等为历史；不继续终止、重试、强卸载或重启。无提交推送。

2026-10-23 A11执行阻断：同一“缺少专项收尾授权”已连续三轮；安全范围内的故障封存、诊断构建及PC分支检查已完成，不能借持续目标绕过禁止强杀/强卸载。最新仅复核电脑记录，无新板连接；此前PID/VMA/温度仅为最后读回，不称实时状态。停止自动续跑并等待用户决定，A11仍NOT_PASSED、A12不具备条件。阻断审计`evidence/mlp_board_A/20261023-open-failure-review-v1/BLOCKED_AUDIT.json`；恢复后仍须完成真实矩阵、计时和正常退出，目标不缩小。

2026-10-23 A11等待收尾授权期间：新增纯PC打开失败补审，原v1与诊断v2各31场景（30失败+1正常）返回码一致、0模拟计算提交；诊断30失败阶段匹配，2编译/62子进程均exit0，原523项封存不变。没有新板连接或动作；实际失败原因仍UNKNOWN，恢复授权仍待，A11未过、A12不具备条件。证据`evidence/mlp_board_A/20261023-open-failure-review-v1/REPORT.md`。不能把替身释放通过当真实VMA/refcount清零。

本轮PC补充：`backend-diagnostic-v2`打开失败阶段/异常详情日志已完成，30控制场景及6定位检查、ARM64构建exit0；未上板、未重试，真实失败原因仍UNKNOWN。停止状态封存见本轮`stopped_audit_01/`，不等于BOARD恢复或A11通过。

2026-10-23 A11当前覆盖：**NOT_PASSED / OPEN失败后隔离保留**。已完成PC整合、81文件暂存核验、irq2临时冷启动、ARM64/XRT2.18加载及两组原生量化短检查、真实DT与MLP配置/32路IRQ核验。首次worker仅获open许可，`sp_linear_open_v1`返回8，实际计算提交0；未重试。读回worker3308睡眠、无设备FD但残留65536字节renderD128寄存器VMA，ZOCL refcount1；manager3202与双锁/租约保留、GDM inactive、测试PL仍在位，**尚未恢复默认**。末次26.866–29.174°C。现有禁止强杀授权下停止，不自动卸载/重启/恢复；缺少open异常细节需PC诊断修订，后续收尾须专项决定。证据`evidence/mlp_board_A/20261023-integration-v1/REPORT.md`。A12不具备条件；下方“1036、未封装、无PL动作”等为之前快照。旧A10封存和A00—A17不改。

2026-10-23 A11接续：已建立`member-a/a11-preparation-20261023`，保留旧修改和A00—A17。A07/A10哈希核对、XRT2.18静态符号覆盖、真实l00权重/捕获激活冻结完成；6组T1/T8旧独立参考复用，新T3及小例5组PC逐位一致。A11派生后端30场景600断言、数据/实际Linux锁9方法、进程边界9方法exit0，ARM64使用2.18头文件/库交叉构建exit0；不是板上ABI或数值通过。新授权后只读COM5发现当前boot `f4a2ac41-8010-43ee-ad8a-3b89e05034be`、原1036内核、28.163—30.542°C、默认PL applied、无ZOCL，已停止硬件操作并释放串口。计算/BO/PL加载/系统写入均0。A11 NOT_PASSED，A12不具备条件；完整worker/manager及MLP overlay仍待PC接入，临时启动已验收irq2需另行授权。计划23调用、单权重显式BO峰值2154496字节（非物理峰值）；无性能结论/优化。证据`evidence/mlp_board_A/20261023-preparation-v1/REPORT.md`。下方A10“当前仍irq2”等为当时快照，不作为本次启动事实。

2026-10-23 A10最终最小收口：**PASS_MINIMAL_WITH_LIMITATIONS**。用户批准继续后，新单调用进程隔离流程27项Linux/7项host/10项独立证据审计均exit0；真实仅一次N32、32值/4080保护字正确，3×16448字节BO，完整170进程扫描/refcount0后普通卸载并恢复默认PL/GDM。维护15.228秒、最高采样32.624°C，47.174秒后独立内核读回及最终UART锁核验通过。旧计算后失败原样保留，此次验证限定场景已修复；历史空载/身份/原1036恢复证据复用，不重跑1000轮。当前仍irq2，软件reboot可靠性/长稳/最大BO/模型性能不作通过主张，P2安全排除。证据`evidence/board_platform/A10_20261023_isolated_single_v1/REPORT.md`、交接`docs/handoffs/A_A10_MINIMAL_COMPLETE_20261023.md`；原A00—A17保留。COM5/SSH已释放，无本轮重启/刷写/默认启动修改/模型语音数学性能变更/提交推送。下一步仅建议A11电脑准备，未自动开展。下方NOT_PASSED是各旧窗口历史。

2026-10-23 v4真实空载已通过（有已知限制）：新授权一次执行，16.230秒、采样最高32.997°C；XRT独立子进程正常退出，完整FD/VMA扫描与refcount=0后普通卸载，默认PL/GDM恢复。52.468秒后独立内核读回及最终UART证明无遗留manager/ZOCL/active lease/双锁，COM5释放，仍irq2。新增计算/显式计算BO/重启/刷写0；原81项PC证据复用，新13方法+8计划exit0。A10仍NOT_PASSED_POSTCOMPUTE_RELEASE_OPEN，历史N32正确但计算后卸载FAILED不被覆盖；下一次极小单调用释放验证须独立电脑测试与范围授权。报告`evidence/board_platform/A10_20261023_isolated_idle_v4/REPORT.md`。以下“未授权/未部署/空载未完成”按各窗口历史保留；无模型/数学/语音/内核/性能变更，无提交推送。

2026-10-23 历史资源恢复：原始N32日志已含3×16448字节BO、groups3/3/3及3地址、PSS/RSS/CMA采样，PC派生双账保留来源SHA/原始行号。7项恢复测试exit0，未重算/连接板子。原sync计时包含日志fsync，不作为纯性能；释放失败保留。新候选空载及计算后释放仍缺BOARD证据，A10 NOT_PASSED；新维护授权未收到，不能由goal自动续行代替。报告`evidence/board_platform/A10_20261023_resource_recovery_v1/REPORT.md`；原阶段/旧失败及v4包不变，无提交推送。

2026-10-23 收尾后PC增量：新增8项实际日志/租约/双锁/子进程退出/释放编排联调，Linux相关81/81 exit0。首轮夹具排序错误exit1保留，未放宽生产门禁。v4候选已电脑封存，SHA726723f4…，无review/未部署；本增量无COM5/SSH/板动作，不扩张“仅收尾”授权。此前静稳修复现为PC已打包而非未打包；真实空载、计算后释放、原系统返回仍未完成，A10 NOT_PASSED。报告`evidence/board_platform/A10_20261023_controller_integration_pc_v1/REPORT.md`；以下状态按各历史窗口保留，无提交推送。

2026-10-23 最新：本次irq2启动已确认，独立控制器在PL前因日志字段冲突/进程扫描竞争停止，本轮驱动/PL/XRT/计算0。用户批准仅收尾后，核实纯Python等待者无设备并定向终止，GDM恢复/lease归档；最终只读无manager/active/zocl，默认PL applied，irq2仍运行，29.663–32.096°C。PC静稳修复73方法exit0，未部署；空载native及计算后释放仍未通过，A10 NOT_PASSED，原1036回归未做。报告`evidence/board_platform/A10_20261023_isolated_idle_v1/FINAL_REPORT.md`；旧A00—A17/取消回归/失败不变，无提交推送，不在仅收尾授权下再开测试。

2026-10-23 隔离修复进展：新的native空载worker与完整控制器已实现，Linux62测试全通过，Windows50过/4 POSIX跳过；未重放历史N32。新16文件包逐项哈希暂存于板端独立root目录；原1036/irq2 FIT、默认PL、XRT库核对一致，临时IP非持久。用户授权一次人工冷启动irq2和空载窗口，正常关机已实见Power down，冷启动正在捕获；实板空载生命周期、计算后恢复均尚未通过，A10 NOT_PASSED。没有计算/计算BO/刷写/默认启动更改。新交接 `docs/handoffs/A_A10_ISOLATED_IDLE_20261023.md`，原证据与A00—A17保持；以下component-only为上个窗口历史。

2026-10-23 最新接收核验：完整交接包130文件/5处驱动源修改/原始证据哈希已核验，唯一真实N32的32输出与4080保护字正确，空载与正常1036恢复有原始证据；计算后卸载 FAILED 保留，A10 NOT_PASSED。已通过COM5登录仅只读浏览，定位修订执行目录并核哈希取回2份执行源码及actual/golden；当前采集boot549452c7-1381-4d31-b959-b40c66a93343、6.8.0-1036-xilinx、ZOCL absent、gdm active、末次28.770—30.479°C，COM5释放。新重启/PL/驱动/计算动作0；当前租约/锁全审计及overlay applied属性未做，不冒充维护前置完成。电脑新增独立进程退出边界和严格释放门禁组件：Windows16通过/2POSIX跳过，WSL相关44方法全过；首轮启动器PID失败保留并修测试，不放宽身份检查。native无计算worker和新控制器接入仍未实施，未部署/未板验；下条REPORT_ONLY为初次接收历史，已由本段覆盖。收据 `evidence/board_platform/A10_20261023_peer_intake/verified_intake_receipt.json`，详见 `docs/handoffs/A_A10_PEER_INTAKE_20261023.md`。原A00—A17/取消回归/失败保留，无提交推送。

2026-10-23 外部 A10 交接接收：两份说明原字节与哈希已保存，实际工程根仍 `C:/Patientqwen`；对方 `D:/KV260-A10` 不在本机。报告记载 irq2 启动、修订 ZOCL 空载生命周期、唯一 N32 数值、正常 1036 冷恢复通过，但计算后卸载 FAILED（残留设备 VMA 与延迟 OF 错误），整体 A10 未通过。上述 BOARD 结果暂记 REPORT_ONLY/PASS_REPORTED，未取得新源码、原始输出和恢复收据，不重跑 N32、不使用原 1015 启动基线。末次 poweroff 只是报告历史，本轮板状态 unknown、板接触0。旧/新契约 PC 检查各0；状态前件已备份，新分支 `member-a/a10-peer-intake-20261023`，未提交推送。缺件与下一步见 `docs/handoffs/A_A10_PEER_INTAKE_20261023.md`；原 A00—A17、取消1000轮及历史失败保留。

2026-10-21 最新覆盖：用户要求最大精简，锁定一次32元素而非回归；同boot空载加载成功。源码+实际32路DT确认IRQ index32是枚举终止提示后继续原卸载，内核触发SLUB BUG / of_node_release重复释放，执行器exit1且阻止后续操作。计算0、计算BO0、重启0，无长负荷；28.327–33.401°C。**当前没有恢复默认，active隔离保留，6.8.12-a10irq1候选REJECTED，本次Oops启动不可继续验收**。已保存SHA匹配原始日志，定位intc->data悬空二次free；电脑派生补丁、原ASan失败1/新通过0、6方法和ARM64单元编译0；门禁最终20方法、证据3方法0。完整修订内核/FIT未构建未部署，A10仍NOT_PASSED；取消1000轮及P2不改。报告`evidence/board_platform/A10_20261018_intake/MINIMAL_A10_20261021.md`。下一步审阅故障后正常回原系统方案，并电脑构建独立新候选；不得复用旧候选或继续在Oops系统装卸。以下为历史快照。

2026-10-21 A10获准维护窗口已收尾：一次正常重启/同一候选启动，boot751e617d-c003-4b99-be03-bb5c78235d24、6.8.12-a10irq1；默认移除/候选ZOCL加载0，外部模块标记触发日志停止，未加载测试位流。只收尾普通rmmod/恢复默认均0，独立读回default applied、无ZOCL/设备占用、租约归档、原启动SHA不变；恢复新增2条overlay属性告警保留OPEN，不标干净通过。末次29.617–31.738°C，COM5/SSH释放，临时save-no IP保留。raw+color冲突、41CR被text模式转换、收尾SHA录入错误及路径失误均保留，修复后Linux相关37+新收尾5方法、Windows上传4方法通过；30启动断言/35UART动作另列。A10 NOT_PASSED，新IRQ teardown/最小PL/BO未测，计算0次、数值回归取消，无压力/QSPI/默认启动修改。报告`evidence/board_platform/A10_20261018_intake/IDLE_MAINTENANCE_20261021.md`；profile/双账/全原始日志已归档。下一步只做电脑告警分级与属性生命周期审查，当前维护窗口不再次自动重启或加载。以下为历史。

2026-10-21 A10候选空载PC准备：新增固定6.8.12-a10irq1/驱动SHA/新包名的独立入口，默认只打印计划，真正执行须精确包SHA及新boot逐项基线审阅；所有新增告警仍停止。保留旧空载/收尾默认身份。缓存生成导致清单失败的最小复现exit1保留，修复后Windows14、Linux相关34方法全部exit0；旧/新契约和实际电脑包逐文件核验0。新包在`platform/local/a10-candidate-idle-20261021-v1`，未上传，本轮无UART/SSH/板动作。新维护授权未回复，没有真实基线豁免；A10 NOT_PASSED，空载干净恢复/最小PL与BO仍缺，数值回归保持取消。报告`evidence/board_platform/A10_20261018_intake/CANDIDATE_IDLE_PREPARATION_20261021.md`。原A00—A17保留。以下为历史。

2026-10-20 A10候选启动/原系统返回增量：用户专项授权后完成原模块树备份与逐项核验、独立候选暂存（6218模块/6231文件）、一次正常重启和一次真实候选bootm，已登录6.8.12-a10irq1。初次完整日志经串口超时124保留，用户重新上电后按原boot ID只读补回完整历史日志exit0。当前原6.8.0-1015-xilinx/default overlay、原FIT/脚本SHA及候选FIT/ZOCL保留均已只读核验exit0；温度30.052–32.718°C，COM5释放，无IPv4/ZOCL/计算BO。原系统返回由用户上电触发，不冒充主动故障恢复。27项Linux方法、23启动安全断言、归档日志3方法、32动作计划/42重接安全断言通过；路径/过密日志/旧U-Boot解析失败已保留和修复。X509信任/固件pinctrl/默认overlay基线告警仍OPEN，IRQ修复板测/空载恢复/最小PL与BO未过，A10 NOT_PASSED。报告`evidence/board_platform/A10_20261018_intake/CANDIDATE_BOOT_AND_RETURN_20261020.md`。下一次候选启动+空载维护窗口已询问，未执行；原数值回归取消，A00—A17及历史均保留，无提交推送。下方均为历史快照。

2026-10-20候选暂存准备：新增仅并存、不覆盖、不启动的板端暂存器及PC12方法测试，真实包电脑解包/全部回读6218模块6231文件389973937B通过exit0；29 UART动作计划通过。板只读原模块/目标/余量核实exit0，拟议目标均不存在、原模块119104KiB未备份，末次31.2–34.3°C，COM5释放。单次IPv6 SSH探测超时255，无网络修改/重连。候选新增目录与一次试启动已请求准确范围授权，尚待回复；本轮无板写入/重启/PL/计算。报告`evidence/board_platform/A10_20261018_intake/CANDIDATE_STAGING_PREPARATION_20261020.md`。A10仍未通过，数值回归继续取消。

2026-10-20 单次正常软件重启及原系统返回已实证：U-Boot2020.01/FSBL2020.2，逐级只读核实SD1原启动链后继续原包，重新登录后内核/默认overlay/启动SHA与原件一致，29.9–32.9°C、ZOCL未加载，COM5释放。ANSI提示符识别初失败修复并保留；可选变量未定义、100秒未捕获登录、40秒空捕获均保留，后续单次CR/登录/只读后检exit0，不重复重启。37 PC安全检查exit0。报告`evidence/board_platform/A10_20261018_intake/BOOT_INSPECTION_20261020_REPORT.md`。A10仍未通过：固件pinctrl兼容警告、候选启动/干净恢复/最小PL与BO仍缺；无候选暂存/加载/刷写/计算，数值回归保持取消。以下均为此前快照。

2026-10-20 用户上电登录后只读重接同板成功，新boot `0b6e8bb1-2219-4f67-b4f2-0a3e9718eaa1`、原内核/默认overlay/ZOCL未加载；末次28.6–31.3°C。用户接网线后1Gbps，无IPv4；原FIT/启动脚本SHA与备份一致。NM只读查询超时124保留，后续工具/日志缺件用独立只读步骤补齐exit0，不重试NM。旧/新契约及28 PC计划检查exit0。sudo缓存无，未发密码；未重启/部署/改网/加载PL/计算，COM5已释放。报告 `evidence/board_platform/A10_20261018_intake/RESUME_20261020_REPORT.md`。A10未通过；下一步需专项确认正常软件重启并只读核实实际U-Boot/原系统启动路径，不按复位、不刷写，数值回归继续取消。下方关机状态为上一轮历史。

2026-10-19 用户确认关机后继续电脑准备，取消电脑构建总时限，不取消板端安全限制。完整Image/modules/dtbs exit0，新release配套ZOCL及238 CRC exit0；驱动136候选stub/同套san、81旧缺陷复现、6生成器方法通过。暂存v1 make0但内核模块缺签名，独立复现exit1保留；修电脑私有helper执行位后v2审计6218模块、6127签名通过，91 staging按原策略不签名。模块门禁6+启动归档8方法exit0；FIT首次缺dtc失败保留，v2生成并独立回读通过，1669 initramfs模块配套，非模块原条目/DT不变。完整候选仅在WSL私有目录，未获部署/启动验收。板子OFF，无串口/SSH/PL/BO/上电操作，旧IP/温度均历史。A10仍未通过、数值回归保持取消；报告 `evidence/board_platform/A10_20261018_intake/DRIVER_AND_BOOT_CANDIDATE_PC_REPORT.md`。下一步现场只读核实U-Boot与原系统返回路径，再专项授权短时试启动；不要求现在重新上电。下方均为历史增量。

2026-10-19 A10重接/备份/完整电脑构建增量：新boot只读确认，临时IPv4被原NM DHCP清掉后获单独授权创建save-no内存连接；D-Bus Unsaved=true独立验证exit0，未改电脑VPN/永久网络/网关DNS。完整64.45MB原FIT与8000B原脚本备份SHA匹配、CRC解析8测试通过，原组件/2499行initramfs清单已电脑核对；修正此前遗漏已有成功脚本读取的缺件描述。完整内核Image/modules/dtbs在电脑限45min/-j8构建中，最终结果尚未产生，独立版本6.8.12-a10irq1；匹配驱动构建入口已准备且5元数据测试通过，未运行该重编译。新增5文件源级IRQ上下文风险记录，需计算前解决；未在板复现。末次温度30.8—32.4°C、默认overlay在/ZOCL不在，COM5/SSH关闭；无板重启/内核更换/PL/BO/计算，A10未通过，数值回归仍取消。报告 `evidence/board_platform/A10_20261018_intake/KERNEL_FULL_PREPARATION_REPORT.md`；构建最终状态以 `kernel_full_build_01.json` 为准，候选不得部署。

2026-10-19 A10内核修复电脑候选：三个精确Ubuntu源文件，修补OF临时/映射引用、可变mapcount卸载上界及experimental parent所有权；候选304 stub检查+同套ASan/UBSan、原版308缺陷复现、4生成器方法、补丁正反dry-run与SHA、3个ARM64翻译单元编译通过exit0。最终时间戳警告已消除，SDK GCC13.4与原13.3差异保留；不是完整内核/模块/FIT或板修复。报告 `evidence/board_platform/A10_20261018_intake/KERNEL_REPAIR_PC_REPORT.md`，回退草案 `platform/qwen35/a10/kernel_repair/ROLLBACK_PLAN.md`。无板连接/更改/重启/负载；数值回归仍取消，A10未通过。下一步完整电脑构建及启动回退核实，板写入/试启动单独确认，不覆盖原默认包。

2026-10-19 A10安全修订后接续：内核日志门禁9方法、受影响idle/cleanup11方法、引用模型8方法共28 PC测试exit0；精确Ubuntu6.8.0-1015.16源码9断言通过，找到extended IRQ引用路径及mapcount缩减卸载上界风险。板上只读配置grep exit0确认experimental实现启用，SSH关闭；未重载PL/分配BO/运行计算/改内核。最新派生profile与资源双账 `evidence/board_platform/A10_20261018_intake/board_profile.safe_v2.json`，总报告 `SAFE_ACCEPTANCE_PROGRESS.md`。数值回归已取消，不是待补跑项；A10仍未通过，下一步先电脑制定匹配内核修复及回退方案，不能忽略错误强行加载。

2026-10-19 用户明确修订A10：取消数值回归20长度/累计1000及重复数值循环，记CANCELLED_BY_USER，不记PASS、不自动安排其他阶段补跑。保留单次最小PL通路核对、受控小额BO/同步、实际资源账、正常恢复和平台证据；禁止长压测/极限分配/故意在途故障注入。政策 `docs/A10_ACCEPTANCE_SAFE_20261019.md` 覆盖旧A10门槛；最小通路0次、IRQ引用泄漏未决，A10仍未通过。先继续PC定位，板子保留默认配置。

2026-10-19 A10专项仅收尾授权完成：普通remove/rmmod/load原k26均exit0，独立读回测试overlay/ZOCL/render/card消失、默认overlay applied、FPGA operating。温度28.824—30.122°C、CmaFree814444KiB，active租约归档，SSH关闭，无计算/计算BO/复位/刷写/测试重新加载。完整dmesg事后复核发现中断控制器节点expected refcount1实际65错误，恢复状态成功但不能标干净恢复通过；下一步PC定位引用释放与日志门禁，禁止循环装卸定位。报告 `evidence/board_platform/A10_20261018_intake/IDLE_CLEANUP_REPORT.md`；A10未通过、真实比较0。下方待收尾为历史。

2026-10-19 A10收尾待确认期间：新增仅收尾独立入口，固定失败来源/boot/租约、双锁、恢复哈希、无占用检查，命令白名单拒绝重新测试加载及强卸载；补legacy DRM card占用及严格refcount检查。11 PC方法exit0，`idle_cleanup_only_tests_v1.json`；未上传/连接板子/执行恢复，末次观察仍为测试配置加载、默认未恢复。见 `evidence/board_platform/A10_20261018_intake/IDLE_TRIAL_REPORT.md` 后续段。A10未通过，等待已发出的仅收尾确认，不重问宽泛权限、不更改旧结果。

2026-10-19 A10一次空载授权执行：默认overlay卸载、固定ZOCL加载、测试位流加载均exit0；renderD128出现。检查脚本误要求ZOCL总绑定数为1，实际主设备+中断子设备共2项，遂exit1停止，无计算/计算BO。确切源码与父子sysfs验证后只修电脑检查，3方法exit0，未重跑加载。当前测试overlay和ZOCL仍在、默认未恢复、active租约保留、执行器已退出；等待用户仅收尾恢复确认。报告 `evidence/board_platform/A10_20261018_intake/IDLE_TRIAL_REPORT.md`，失败原始JSONL/源码快照保留。A10未通过，真实比较0；无长测/复位/刷写/提交推送。下方待首次PL授权均为历史。

2026-10-19 A10恢复审查增量：从真板只下载67512B libdfx、SHA匹配后电脑反汇编，确认overlay删除返回值被忽略；以后不以卸载exit0判定成功。只读DFX列表已确认默认k26槽0->0（执行前重验），源包后缀差异/DSC签名未验不隐瞒。板端只读采集0.09379s、31.008—33.697°C，无PL/BO操作；权限拒绝255与认证提示缓冲取消1保留，明确提示后只读查询0。短主机v4补初始化取消/健康/软时限与逐步trace，72原生+同72san+4信号及A53链接exit0；v4未上板，不借v3的链接PASS。空载配置包/4 PC测试完成，不含host/xclbin；待用户单次空载加载-卸载-恢复授权，未获计算权限。见`evidence/board_platform/A10_20261018_intake/PL_IDLE_PREPARATION_REPORT.md`。A10 NOT_PASSED、真比较0；保留全范围及历史，无commit/push。

2026-10-19 A10授权增量：用户登录后只读确认新boot；单独授权的277KB A53程序传输及一次动态链接检查通过（exit0，0.03148s，无FPGA设备打开）。临时eth0 192.168.2.2/24添加成功，默认路由空，电脑网络/配置文件不改；固定UART所见SSH公钥后Windows SSH通过，WSL连接超时保留。只读平台采集0.11435s、温度32.096—35.655°C，原默认overlay仍在。XRT两库代码/符号/重定位等节一致，但rodata差异未完全解释，不认定整体兼容。9 ELF+4传输+5摘要PC方法与22动作计划通过，原失败保留。详见`evidence/board_platform/A10_20261018_intake/LINKAGE_NETWORK_REPORT.md`及源SHA机器摘要。PL/BO/vadd/恢复NOT_TESTED、真比较0，A10未通过；未加载位流/复位/刷写/长测，COM5与SSH均释放，无提交推送。下一步审查恢复与最小PL方案后专项授权；以下无shell/无IP/ARM未跑均为历史快照。

2026-10-18 A10返宿舍接续：COM5/6原USB标识存在，COM5单次CR后3秒无shell提示，未发密码/板端命令、已释放；当前boot/温度待重新确认，不复用暂停前读数。电脑完成暂停前2×1024B FRU独立审计：SOM/载板身份区校验通过，扩展链137/122处错误保留；AMD已有同类问题，不写EEPROM。10项新PC测试exit0；旧/新契约exit0、17动作计划通过。暂停前短vadd已60控制+同60san+4信号与真实A53链接通过，v1/v2失败保留，v3候选尚未板跑/授权；旧1000入口禁用。FIT与安装内核摘要一致，XRT同版本不同构建哈希仍待核验。详见`evidence/board_platform/A10_20261018_intake/RESUME_AND_SHORT_HOST_REPORT.md`；原始捕获/机器摘要/命令退出码齐备。无PL/BO/计算/复位/刷写/持久安装，A10仍NOT_PASSED，无commit/push；保留原A00—A17。

2026-10-18 A10短时驱动实测增量：用户认证并关闭COM5后，固定SHA的ZOCL2.18（464752B）UART传输167/167 ACK、真板普通insmod/readback/rmmod及收尾均exit0。九类驱动绑定门禁确认无候选，加载后引用0、卸载后模块不存在；不等于PL/BO/DMA恢复通过。最后温度31.140/34.272/32.640°C、CmaFree814444KiB，串口已释放，网络传输服务已结束。原taint8704已有证书/签名告警，此次外部模块后12800，卸载不清历史标记；固件功能警告和FRU multirecord校验exit1独立待核实。HTTP失败、UART CR边界首失败保留，修复后传输通过；PC传输6/计划12/温度17/证据解析4及CR复现通过。未加载PL/DTBO、分配BO、运行CPU小样或模型、刷写、复位、持久安装/网络更改。报告`evidence/board_platform/A10_20261018_intake/DRIVER_BOARD_CHECK_REPORT.md`，15份捕获SHA及机器摘要`driver_board_check.json`；A10仍NOT_PASSED。下一步电脑审查启动组合和旧vadd超时生命周期，再单独申请有界PL短测；原A00—A17状态保留，无commit/push。下条“尚未暂存/加载”为历史。

2026-10-18 A10加载授权预检：用户批准独立目录暂存与一次短时驱动加载（不含PL）。真板只读预检温度31.435—34.023°C、lockdown none、modules_disabled0、ZOCL未加载；已有taint8704待特权日志解释。sudo -n true退出1需认证；用户授权代验后，串口未确认shell即停止，未发送密码/变更命令，COM5释放。电脑去调试信息候选238CRC再验通过，5动作安全计划测试exit0；暂存/网络服务/insmod/rmmod均未执行。报告`evidence/board_platform/A10_20261018_intake/DRIVER_AUTH_PREFLIGHT.md`。下一步用户确认终端提示与sudo认证，不自动扩大到PL或长测，A10未通过。

2026-10-18 A10电脑预编译增量：准确6.8.0-1015.16头文件经Ubuntu官方快照签名/索引/DEB哈希校验，config/Module.symvers与真板一致；SDK PPA2.18签名密钥与Xilinx官方源码固定指纹一致。现有SDK13.4编译器-j2预编译ZOCL2.18成功（内核原13.3警告保留），ARM64模块238导入CRC匹配；8项PC回归通过。用户再授权COM5只读，确认123 compatible无ZOCL节点；1638属性快照在PC重建、1411非name属性逐字节复核，既有vadd overlay静态合并通过且memory/bootargs不变。最新温度30.744—33.448°C；DT快照传输9.89s、串口释放。源脚本未改数学；宿主include及Ubuntu变长modversion解析失败均保留并修复。驱动仅电脑暂存，未安装/加载/位流/计算/重启/刷写。报告`evidence/board_platform/A10_20261018_intake/DRIVER_PRECOMPILE_REPORT.md`；下一步需用户单独授权短时驱动加载范围，不包括PL。A10整体未通过，未提交推送。

2026-10-18 A10用户授权COM5只读接管：3份真实串口原始JSON、10组短时只读命令已完成，端口均关闭；Ubuntu24.04.2/aarch64/6.8.0-1015-xilinx、DT KV260 revB、XRT2.18、缺ZOCL直接确认。hwmon温度30.798/32.065/33.246°C；MemTotal3996396KiB、CMA819200KiB，DT低/高内存区仅为描述，不代表BO可达。新平台profile含来源SHA256，9项PC解析单测及3阶段计划检查通过；传感器门禁新增hwmon路径，只作电脑测试未重跑已有效采集。未安装/加载/复位/刷写，ARM程序、BO、vector-add和恢复NOT_TESTED，A10未通过。准确头文件在板上已装但电脑来源包尚未取得，签名链/交叉编译/DT与现有XRT2.23 SDK兼容性仍待验证。报告`evidence/board_platform/A10_20261018_intake/READONLY_COLLECTION_REPORT.md`。既有各阶段/旧板证据保留，无提交推送。

2026-10-18 A10驱动来源增量：实际电脑查询ubuntu-xilinx/sdk PPA的noble ARM64索引找到同源xrt/xrt-dkms 2.18.0-0ubuntu1；已下载159044字节驱动包并与索引SHA256匹配，未安装、未编译、未改板端源。静态审查发现安装会操作现有模块/调用DKMS及modprobe，make -j未限并行数；DKMS名称差异待隔离核验，禁止直接板端安装。准确内核6.8.0-1015-xilinx编译与2026.1工程兼容性未测，A10计算仍阻断。证据`evidence/board_platform/A10_20261018_intake/XRT_218_CANDIDATE_AUDIT.md`。不再以找不到同版本包为阻断，下一步为电脑隔离验证；未完成GPG签名链，未推送。

2026-10-18 A10后续只读结果（用户串口截图/文本，退出码未采集）：已进入`ubuntu@kria:~$`；Ubuntu24.04.2、aarch64、内核6.8.0-1015-xilinx，DT model为ZynqMP KV260 revB，FRU独立核验仍未做。MemTotal3996396kB、MemAvailable3591720kB、CMA819200kB，CMA不与总内存重复相加。XRT2.18.0已装，但modinfo找不到zocl；当前modules与/usr/src查找为空，card0为显示驱动；APT缓存仅有xrt-dkms2.8.743候选，未确认匹配驱动获取路线。A10状态为LINUX_SHELL_CONFIRMED_XRT_ZOCL_DEPLOYMENT_BLOCKED，PL/BO/vector-add/ARM程序与兼容性未验收；无安装、升级、内核/DT变更、复位、刷写或负载测试。证据`evidence/board_platform/A10_20261018_intake/LINUX_XRT_OBSERVATIONS.md`。下条等待登录状态为历史观察。

2026-10-18 A10新板接续：COM5单次CR实际返回`kria login:`，用户需手动登录；尚未确认OS版本/板号/DT/XRT/温度/IP，不能复用旧板身份。未改板端配置、未复位、未刷写、未运行计算。PC旧/新契约校验退出0；pyserial缺失退出1保留，使用.NET手动终端替代且不记录密码。报告 `evidence/board_platform/A10_20261018_intake/REPORT.md`。A10未通过，后续仅短时只读采集，旧1000次与模型测试不自动执行。

2026-10-16 新购板短时验收准备：已分离刷机委托与机主验收，发布 `release/kv260_user_acceptance_20261016_v1/`。给专业人士目录包含实际官方候选镜像/固件副本与校验值；用户ZIP含Python只读采集、Windows连接入口及2026.1 SDK真实A53小程序。PC 11项测试/原生4MiB单次小样/ZIP核验通过，ARM64动态交叉构建通过；首次静态链接缺libc失败保留。CPU显式启用、单线程、3秒上限，无刷写/复位/PL/模型调用。新板BOARD、FPGA与完整问诊均NOT_TESTED；现有DT匹配和PL安全生命周期未闭环，完整功能短测包未交付，不追认A10。报告 `evidence/board_platform/newboard_short_20261016_v1/REPORT.md`；旧板证据和原进度保留，未commit/push。

2026-10-04 A09增量：`PASS_PC_PREBOARD_REHEARSAL_DEPLOYMENT_PENDING_BOARD`。报告`eval/qwen35/a09/refresh-20261004-v1/REPORT.md`，交接`docs/handoffs/A_A09_CLOSEOUT_20261004.md`，独立候选`release/default_preboard/20261004-v2/`。新干净Python83+5+4、真实隔离WAV和实际启停/健康/配置回滚/日志通过；修复SIGINT遗留RUNNING，原失败保留、补测CANCELLED。145导出文件/6原生二进制/68更新源码连续性核验，复用原干净C++构建与A06/A07，不重跑200或额外长测。新增BO门禁和真实A53编译、9包ARM cp312依赖/146ELF静态审计/离线解析与拒绝错误目标安装。旧包不变，目标执行/启动组合/实际rootfs音频/内存/声学/功率/医学仍NOT_TESTED或待审；P2不实现，广泛质量和可靠性待办不伪称全部通过。无commit/push、刷写、录音或板调用；下文旧A09缺BO入口/目标依赖材料描述已被本条替代。

2026-10-04 A08增量：当前入口 `eval/qwen35/a08/closeout-20261004-v1/REPORT.md`，交接 `docs/handoffs/A_A08_CLOSEOUT_20261004.md`。复用原200轮及A09定向修复；本轮补资源缺失null、配置/病例追溯和83项PC测试、两轮真实断网闭环。最终通过范围/退出码见报告，不重跑长测、不新录音、不推送。新确认UI真人操作、声学/医学与BOARD独立未测；下面A08待接线/待no_hardware描述是历史。

2026-10-04 A07无板正式收口：`PASS_A07_OFFLINE`。B04 commit9a75600已核验，B double冻结XO不改；实际2026.1/kv260_base目标链接/布局布线成功，WNS+0.809ns、WHS+0.010ns、未约束端点/布线错误0，CDC safely timed；保留93 DSP警告、18建议和2平台clock建议。PC970规则、66meta/396篡改/4build、完整C ABI控制29场景554检查及相同sanitizer通过，真实A53库/host6导出9依赖、干净包重建通过，旧完整S1 A53证据按hash复用。正式目录`release/a07_b04_v3`，1101文件最终hash检查通过；报告`evidence/A07_closeout/20261004-v1/REPORT.md`，交接`docs/handoffs/A_A07_CLOSEOUT_20261004.md`。原失败/v1/v2保留，不代B04联合签核；BOARD/ARM执行/BO预算/恢复/G1/A12均未通过。生产profile禁用，内存null。无新commit/push、刷写、模型长测或WSL/MAC更改。下面A07未通过描述为历史。

2026-10-04 A06最终离线接收：`PASS_A06_OFFLINE_KERNEL_ACCEPTANCE`。用户提供匹配当前WSL Host ID的官方许可证，独立安装0600，原件/旧许可不变，正文不入库。e227297 double当前实际源码以Linux Vitis2026.1、原A04参考运行Csim：61案例/2800022检查exit0，FP32所测max_abs=0且逐位一致；两真实shape T1..8、K129/N33、错误/保留码/重复调用与顺序反例覆盖。复核原1923payload、实际XO/17参数/40Bmeta、必需同版T1/T8 Cosim及382严格向量hash，正式冻结`hw/linear_A/KERNEL_SOURCE.json`。最终证据`evidence/A06_acceptance/final-20261004-v1/`，交接`docs/handoffs/A_A06_ACCEPTED_20261004.md`。只解除A07离线链接前置，不等于B04/实现/BOARD通过；HLS负slack及65 native PASS+1历史恢复、WDB/FIFO边界保留。发现既有A07队列失败已结束，仅将其marker归档，未改失败或代跑修复。原A07—A09和脏工作树保留，无新commit/push/板调用。下方许可阻断均为历史。

2026-10-03 A接手A06剩余修复：`PARTIAL_TOOLING_COMPLETE_LOCAL_CSIM_BLOCKED`。不再等待B。A生成独立序列化补丁，只改两个派生testbench的JSON流模式/换行；B原件1923项不变。干净Linux目录重编译PC50、真实权重/合成激活4例、归档RTL66回放通过，382向量文件全部与原清单SHA一致；Windows/Linux各3方法及归档11方法通过。实际Windows2026.1备选Csim也尝试，K26 part支持/许可检查exit1；Linux当前许可失配，不能撤销原本地Csim必要项。accepted=false/frozen=false，只有当前主机官方许可恢复后的新版Csim待补。已交A07接口说明、实际XML与工具manifest。报告`evidence/A06_acceptance/a-owned-closeout-v1/REPORT.md`；交接`docs/handoffs/A_A06_OWNED_CLOSEOUT_20261003.md`。原单位测试反向补丁断言失败与WSL interop禁用失败保留，修复后实测。共享队列空且失败marker归档；未改模型/数学/容差、未重跑A05长测、无commit/push/BOARD。下条B反馈要求是历史，由本条A修复取代。

2026-10-03 A06补交增量：`PARTIAL_LOCAL_CSIM_LICENSE_BLOCKED`。实际收到B03 supplement的double及XO（SHA 96ca2a58…），1925归档文件、14精确来源收据、270TV、382固定文件。新版A04独立PC61/2800022通过，66笔归档RTL经B独立dense与A04参考复核，641472参考INT32和Y/meta负例通过。B同版Csim50已审计；本机新版Csim因WSL MAC再次变化exit1，未执行数值，不能继承旧版三Csim成功。B严格Linux自测在42个JSON换行差异处exit1，340文件字节一致；5WDB未附、1笔最大K原Cosim失败后恢复均保留限定。报告`evidence/A06_acceptance/supplement-v1/REPORT.md`、交接`docs/handoffs/A_A06_SUPPLEMENT_20261003.md`；accepted=false/frozen=false，本轮未做A07链接/BOARD。实际核缺件已解除，下一步仅许可稳定后补新版Csim及B交付工具反馈，不重新执行长测。A07—A09及已封存包保持原样。

A09继续：源码/依赖候选包已封存并独立校验，3792文件、85,415,371字节；hash/命令见`release/default_preboard/package.json`及`eval/qwen35/a09/package-verification.json`。旧中断记录保留；无编译/导出/推理重跑，硬件与系统/ARM语音准备仍缺，A09总体PARTIAL。以下“封存中断”是历史状态。

A09封存中断补充：已完成构建/导出/测试保留；包进程已退出、队列空。`release/default_preboard/source-bundle/`未封存，无最终压缩包/hash，不能交付。接续点见`eval/qwen35/a09/INTERRUPTED.json`，不重跑已过工作。

2026-10-03 A09：`PARTIAL_PC_REPRODUCTION_PASS_DEPLOYMENT_NOT_READY`。干净源码构建、72矩阵145文件复现、新venv9wheel断网安装、75+5测试及两组6反例通过；真实WAV/无硬件模式小样与一次检查器修复复测，保留模板失败。不重跑200/两小时、不新增录音。交付`release/default_preboard`，报告`eval/qwen35/a09/REPORT.md`。硬件配套/BO执行入口/系统与ARM语音安装闭包尚缺，BOARD全部NOT_TESTED，A09不签整体通过；无新commit/push。下方是历史。

2026-10-03 A08当前交接：`PARTIAL_PC_CORE200_COMPLETE_TARGETED_FIXES_PENDING`。固定200轮电脑断网任务全部闭环（133 MODEL/67 TEMPLATE），9项故障/策略用例符合预期；这不是模型准确率100%。额外424轮后用户认为重复过多，已SIGINT停止，仅相关进程退出；最后1条未完成记录不计通过，约69分钟不冒充两小时。默认脚本取消额外时长循环，已有效200轮不重跑。`REPORT.md`在`eval/qwen35/a08/`，交接`docs/handoffs/A_A08_20261003.md`。检查器肯定句、普通WAV人工确认接线、资源采样竞态及独立no_hardware单例仍待定向收口；A06/A07/BOARD与医学审核不升级。无新commit/push/录音。以下“执行中”为此前历史状态。

2026-10-03 A08 执行中（不是 PASS）：默认入口 `system_qwen35/app/default_e2e` 已接真实 S1/ASR/TTS/Pulse、病例评分与终端界面。69 项规则/历史测试通过；优化算子 2/3 线程与保留 A05 的输出/logits 一致；短提示质量失败保留，采用不改事实的 v4 双事实成句修复。正式断网 200 轮及两小时真实工作正在 `eval/qwen35/a08/regression-v2` 运行；v1 因会话关联缺口主动停止并保留。不得把进行中、模板闭环或安全拒绝写成模型质量/板测通过。A06/A07 硬件阻断与原有效证据均保留；无新 commit/push 或录音。

2026-10-03 用户授权先做不依赖B实物的工作：`PASS_INDEPENDENT_SCOPE_A06_AND_A07_NOT_PASSED`。新增`modules/linear_A/xrt/`六函数候选、主机校验/meta/POISONED门禁，PC969断言与相同ASan/UBSan通过；ZIP/XO只读收件8方法通过。现有SDK实际交叉构建完整S1/CPU库/XRT候选/自测及llama库，136编译单元A53选项核验、10个Common rootfs库逐字节匹配。不是ARM执行、板测或已可启动。默认CPU/模型/契约不变，KERNEL_SOURCE继续未接收，设备访问默认禁用；B实际核包、平台链接、启动/DT/BO/恢复仍待闭环。报告`evidence/A07_independent/preboard-v1/REPORT.md`，交接`docs/handoffs/A_A07_INDEPENDENT_20261003.md`。缺libuuid、绝对RPATH及收集目录命名问题均保留并修复；无新commit/push。以下历史不覆盖本条范围。

2026-10-03 A06许可恢复增量：`NOT_ACCEPTED_B_DELIVERY_BLOCKED`。用户提供官方重新绑定许可，当前Host ID匹配；安装到WSL独立文件（旧文件和下载原件未修改，未提交凭据）。三版Vitis2026.1 Csim实际各61案例/2,800,022检查、exit0，共183案例/8,400,066检查通过。原PC不重跑。第一次重试因Windows清单路径分隔符KeyError exit1，完整保留；新增v2兼容路径表示后核验全部旧输入hash，未改B核/数学/容差。最新证据`evidence/A06_acceptance/license-rehost-v1/REPORT.json`和`csim-retry-rehost-20261003-v2/`，交接`docs/handoffs/A_A06_LICENSE_RECOVERY_20261003.md`。许可阻断解除，B未定最终版/XO/RTL原始证据缺件仍阻断验收；accepted=false，BOARD/Cosim/综合/实现/交叉构建未新增测试。以下为当时历史状态，不覆盖本条增量。

2026-10-03 A06 接收验收：`NOT_ACCEPTED_DELIVERY_AND_LOCAL_LICENSE_BLOCKED`。按用户本轮重定义从 GitHub B 分支固定 commit `fdd1d656290b9cd94152a6525c8be4e083dbd928` 独立接收244文件，未合并B整仓。三版源码本地PC各61例/2,800,022检查通过，INT32及FP32与既有A04独立参考逐位一致；新模型两形状T1..8、真实l00 gate/down权重（合成激活）、尾块/错误均覆盖。不能写成Csim/BOARD通过。

本地2026.1 Csim三版均在许可检查阶段exit1，当前WSL Host ID不匹配原官方许可证；未改MAC/许可或安装工具。B阶段快照未选择最终核，实际XO缺失；五组baseline Cosim各缺27原始tv文件；部分历史testbench/runner哈希与当前快照不同。B报告的34笔RTL成功保留为提供方证据，A不能完整重放。`hw/linear_A/KERNEL_SOURCE.json`明确accepted=false/frozen=false，A07接口候选已交，不能据此链接/部署。

报告`evidence/A06_acceptance/REPORT.md`、集中缺件`B_MISSING_AND_DEFECTS.md`、交接`docs/handoffs/A_A06_RECEIPT_20261003.md`。A04/A05相关11项身份复核通过，旧代码/sidecar/报告/失败保留；无新commit/push、B/C代签或板调用。下一步官方许可恢复及B补选定核交付，A复测后再接A07。以下A05为有效历史，不因本阶段阻断撤销。

2026-10-02 A05续作收口：`PASS_PC_A05_FULL_MODEL_PHYSICAL_T8`。最终v8固定提交/原sidecar，真实72个MLP批量CPU；T1/2/4/8及尾块的72投影、23位置logits和48混合状态数组逐位一致，scalar/optimized一致。17状态检查+74新增断言（含1025token原失败样本）、dev24/80断言及两条断网合成音频通过。17MODEL/7策略模板，0非预期回退。CPU算子库hash未变，旧103 ABI与48独立SIMD样例有效。

报告`eval/qwen35/a05/batch-fix-v1/REPORT.md`；交接`docs/handoffs/A_A05_CLOSEOUT_20261002.md`。旧seal12523项开工全部匹配，改动前before保留；原报告和v6/v7失败不删。没有新commit/push、录音或板调用。A06前置已具备，未执行A06；ARM/PL/BOARD、医学审核/最终300题/声学计时仍未验收，R1/R2可选禁用。以下A05 PARTIAL为历史。

2026-10-02 A05：`PARTIAL_PC_S1_WORKING_PHYSICAL_T2_T4_T8_NOT_ACCEPTED`。完整72个真实MLP经C++图节点走SP_LINEAR同数学CPU；103 ABI、48真实SIMD整数/FP32投影、scalar/optimized全图、canonical T1混合状态、取消/reset/病例切换、dev24条、两条断网合成WAV闭环通过。dev17MODEL/7策略TEMPLATE、0非预期回退；修复前2/17回退及检查器反例保留。sidecar140378112字节不变，GGUF目标页实际RSS0；未commit/push/录音/板调用。

**未全通过**：较大物理batch状态/logits等价性失败，F16非MLP诊断仍有T1差异。当前physical_ubatch=1，外部1/2/4/8/256调度通过不能写为物理T8通过。R1可选未验收禁用，R0明确清空重算。报告`eval/qwen35/a05/REPORT.md`，交接`docs/handoffs/A_A05_20261002.md`，封存`eval/qwen35/a05/files.sha256.json`。下一步修复物理batch或取得明确T1范围验收；不自行宣布A05全通过或进入A06/BOARD。以下为历史。

2026-10-02 A04：`PASS_PC_A04_NUMERICS_FULL_GRAPH_PENDING_A05`。从锁定Qwen3.5原始BF16导出72个W4/Sw，140,378,112字节；两次导出manifest同SHA，独立C++重新从BF16逐字节核对72矩阵全部一致。210断言及同套ASan/UBSan通过、6个加载器测试方法通过；0/3/4/23层在F16和Q4各采prefill T8/decode T1共48投影，Python标量/C++标量/优化整数及FP32均逐位相同。原浮点→W4A8的NRMSE非零（H0输入6.27%—17.14%），不能写成量化无损或全图S1已通过。原库11项身份不变，A03原seal292项在开始核验通过；状态文档修改前备份保留。

报告`eval/qwen35/a04/REPORT.md`及`REPORT.v2.json`，交接`docs/handoffs/A_A04_20261002.md`。导出峰值105720 KiB（rusage），全部sidecar映射并触达后的最大观测173516 KiB；后者包含Python/NumPy，非板预算。首次测试启动模块名冲突exit1及内存采样v1均保留，修复后独立新日志/文件。仅A04 PC数值验收；Csim/Cosim/综合/实现/ARM64/BOARD仍NOT_TESTED，硬件误差null。SP_LINEAR ABI、全图S1和GGUF/sidecar常驻策略留A05；不继续越阶段、无新commit/push、无B/C扫描或录音。以下为历史时点。

2026-10-02 A03收口：`PASS_PC_ENGINEERING_BASELINE_QUALITY_PENDING`。按当前措辞精简版A03逐项核验，49项证据/输入检查通过：A03 19项（复核原213项seal、录音修复15项seal、44项语音资源及原始结果）和A04输入30项。有效62单测、32真模型协议、6拒绝、4轮断网WAV与授权第一/第四轮实录证据沿用，不重复执行模型，不恢复用户撤销的第三轮。原始第二轮失败、端点截断和医学词错误保留。已修正当前主提示词路径及过时“未录音”状态；源码/权重/公共契约未改。最新报告`eval/qwen35/a03/closeout-v1/REPORT.md`，交接`docs/handoffs/A_A03_CLOSEOUT_20261002.md`。

A04仅前置核验`PASS_INPUTS_READY`：官方原始文件、72个真实tensor形状/偏移/hash、固定运行库源码、手算fixture完整性通过；140378112字节是理论W4+Sw数据量，不是导出产物。未开始导出、参考实现或新激活采集。本轮按用户要求停止，等待A04执行授权。广泛语音质量/教师审核/300题、A08长测及音频设备故障边界、A13声学时延、ARM/BOARD均未通过；断网实录组合为补充待办，不能覆盖已有断网WAV证据。无新录音、commit、push或B/C读取。以下PARTIAL状态均为当时历史，不覆盖本条收口范围。

2026-10-02 A03第四轮电脑实录闭环通过（单例范围）：3.8秒/16k单声道，“你的胸痛每次持续多久”准确转录，终端YES确认；真实CPU Qwen调用1次、MODEL/OK/eos，回答“每次疼痛持续10分钟。”，病例duration事实检查通过，无模板回退。TTS22.05k固定音色/语速，播放完成，用户反馈“转录准确 播放清晰”；CLI与worker退出0，结束后只读检查未发现sp_voice_A临时目录。报告`eval/qwen35/a03/mic-round4-20261002/REVIEW.json`。第二轮失败保留，用户撤销的第三轮不计入验收。整体仍PARTIAL：广泛质量、断网实录组合、声学起点、医学审核及BOARD未完成；一次成功不证明旧误识根因，无新增录音/自动调增益/commit/push。

2026-10-02 按用户明确要求撤销第三轮：仅第三轮测试目录的12个文件移入Windows回收站，并删除此处的该轮转录/结果摘要；不计入通过证据。前两轮原始成功/失败及代码修复证据保留。第四轮使用新目录，仍由用户按键启动，整体A03保持PARTIAL。此条只记撤销动作，不保留被撤销转录内容。

2026-10-02 A03录音时序修复：改为收到第一块PCM后才提示说话（首块保留），移除可能跨15秒上限抢占YES的后台读键线程；新增限量原PCM保存及ASR前数值采集诊断。11项新控制单测+51项回归共62项通过，契约/配置检查退出0。无录音、无模型替换，不声称第二轮识别错误根因已证实或质量已改善；待用户按键用同一句话第三轮复测。见`eval/qwen35/a03/capture-fix-v1/REPORT.md`，旧源码/状态在before保留，原失败和原日志不覆盖。A03仍PARTIAL，BOARD和声学起点仍NOT_TESTED，无commit/push。

2026-10-02 A03真人第二轮：程序正常退出0不等于识别通过。指定问题为“你的胸痛每次持续多久？”，实际ASR为“凸痛每四持续多久”，用户确认识别有误；未输入YES，系统按asr_review_required给出明确TEMPLATE澄清，LLM调用0。2.6秒/16k单声道，播放API完成，用户反馈听清；ASR质量FAIL，原因未定，整体PARTIAL。源码发现录音提示先于设备打开，属于需排查的起始录音风险，不认定已证实为根因。原日志和错误保留，未替换预设文句；证据`eval/qwen35/a03/mic-round2-20261002/REVIEW.json`。本次未再录音、未修改运行代码、未代填声学时延或BOARD结果。

2026-10-02 A03真人首轮增量：用户已明确授权本人朗读合成句。16k单声道5.8秒录音，转录与指定句去标点后一致，“没有气短/两小时前/三十分钟”均保留；用户在终端YES确认，随后反馈“听到，清楚”。CLI及voice worker退出0，确切tmpfs spool已核查不存在，原音频按既有流程清理。此轮多主题测试陈述触发too_many_topics，回复来源TEMPLATE，LLM调用0，不称真人Qwen问答已测。单轮听辨不替代完整质量评估，无声学起点、BOARD仍NOT_TESTED；整体PARTIAL。新增证据`eval/qwen35/a03/mic-round1-20261002/REVIEW.json`，之前报告/213项seal为录音前历史，不覆盖其原件；本次有意更新的状态文件原件存首轮before目录。下一轮需单一问诊问题并由用户按键开始，不自动录音。

2026-10-02 A03：真实离线语音软件链路已实现，但完整阶段仍PARTIAL。sherpa-onnx 1.12.40、Zipformer-small-CTC INT8、Matcha/Baker+Vocos固定版本/hash；独立venv及私有Pulse依赖，不改旧库。51项单测（含36项A02回归）、32项真实模型协议检查、6项拒绝检查通过；12条合成WAV CER=9.09%，医学词替换错误保留，不当真人准确率。9项端点比较中三个阈值都截断构造停顿样本，默认PTT。断外网进程树冷启动4轮全部完成播放API，2条MODEL、2条显式TEMPLATE；播放中取消未提交已播历史。首次ready约15.344秒；提交/ready不同于实际出声，声学起点null。麦克风未获授权未开，人工可懂度/教师审核未测；Matcha非商业限制、shei2警告保留。报告`eval/qwen35/a03/REPORT.json`，交接`docs/handoffs/A_A03_20261002.md`。Csim/Cosim/综合/实现/交叉构建/BOARD均NOT_TESTED；没有commit/push/B/C扫描。下一步完成授权录音、人工听辨及已实现转录确认流程的真人验证，不宣称全A03通过。

2026-10-02 A02：无板工程验收通过，医学/正式教学审核未通过（未审核）。新增A自有`system_qwen35/cases`三份合成草案、Schema与`app`病例/状态/AnswerPlan/检查器/规则评分/真实CPU适配器/本地CLI。36项单测Windows与WSL通过；真实开发集24题，17条应答和7条策略回复，另测实际超时/隔离错误/跨会话，80项集成断言通过。首轮64.7%及第二轮35.3%回退警报完整保留，修复后开发集0%；不代表最终质量。300项heldout仅独立编写计划（0题已写），教师表待填，正式使用禁用。证据见`eval/qwen35/a02/REPORT.json`及`docs/handoffs/A_A02_20261002.md`。模型/契约/历史有效证据保留，无C工程读取，无提交/推送。下一项A03无板实现；不代替真实审核。以下A01“下一步A02”为历史。

2026-10-02 A-DESIGN-1.0 导入和 A01 增量完成：唯一阶段入口已切为增强03，差距见 `docs/DESIGN_GAP.md`。原 A00/A01 PASS 保留；新增 final logits、有界 all 诊断、逐节点 CPU 剖面、明确 R0 单 slot / 零快照。F16/Q4_K_M 两套原基线及两套增量测试实际通过。见 `eval/qwen35/design_import/REPORT.json`、`docs/handoffs/A_DESIGN_IMPORT_20261002.md`。下一项 A02（High），不等板或 B/C。BOARD/Csim/Cosim/新核实现/交叉构建仍 NOT_TESTED；无新 commit、未推送，历史脏树保留。

以下为历史状态，当前状态以 `docs/PROJECT_STATUS.json` 为准。

2026-10-02 新版Qwen3.5 A00入口：见 `docs/PROJECT_STATUS.json`、`docs/MIGRATION_QWEN35.md`。新版A负责默认全系统，B/C候选缺失不再阻断；旧RA03状态以下原样留存，仅适用于旧方案。已保存恢复快照并创建 `member-a/qwen35-a00-20261002`，新契约/配置PC检查通过，模型与BOARD均未验证。下一步A01，不等候选。

2026-10-01 RA03 前置核查受阻：普通契约检查退出0，但require-frozen实际退出1；当前DRAFT，RB01冻结数学、RB02完整独立向量、RC02 sidecar首包在已提供材料中仍缺。实际重验原B输入哈希并通过A中心队列编译/执行B C++手算参考，与已有预期JSON精确MATCH（0x97/0x2F，890/-891）；仅收件复核，不是A S1或C格式验收。未猜sidecar格式、未写生产导出器、未代签，也没有板调用。

详见 `docs/handoffs/A_RA03_PREFLIGHT_20261001.md`、`platform/ra03/status.json`。正式sidecar加载/A8/S1标量及优化后端/RC03调用入口尚未实现，RA03未通过。下一步提供B/C交付文件或准确路径；若尚未交付，须明确允许未冻结CPU原型范围再推进。未新commit/合并main，原脏树保留；冻结失败日志未删除。

2026-10-01 RA02 本地准备完成：核对官方KV260专用资料和B2真实源码/XML；新增ARM64签名/meta布局编译检查、逻辑长度与null部署profile核查、A主机唯一构建队列及独立工作目录。11项新PC测试+4项只读计划回归+12项RA01交付回归通过；实际Cortex-A53编译对象未执行。B核没有由A代链接或代做XRT。

RA02候选包 `platform/build/ra02-platform-20261001-v1.zip`，5,074,776字节，SHA256 `59313952f12a5cc85fd0418f9029fb633ee5e937821e4885f99b55074d927137`；复制平台由platforminfo复核成功，99项payload在全新解压目录核验通过。Windows解压模块失败及后续缺文件失败保留，WSL重试成功。最新结果见 `docs/handoffs/A_RA02_RESULT_20261001.md`，候选manifest在解压包根目录。

RA02未完成外部闭环：BOOT01官方完整启动组合尚待确认；MEM01实际DT/CMA/BO仍null；ABI01正式RB01和B/C同哈希签核未收到；SAFE01旧A-vadd超时BO隔离须在上线前处理。已提前给出10月3日所需阻断/同路线材料清单和到板只读/恢复检查单。逻辑候选可继续评审，不单方FROZEN，G1仍NOT_PASSED。没有板调用、刷写、安装、迁移、新commit或main合并；B/C收件路径/回执仍null。

2026-10-01 RA01 本地实施完成、跨成员验收等待回执：用户重排包已按来源哈希原样归档 `docs/replan_20261001/`；AGENTS/目录检查正式将生产sidecar与应用发布交C，将算子级XRT/本核链接/独立板测交B。A保留平台/S1 CPU/激活量化/图接入及main最终合并，不再包办。当前模型要求Astra/High/Standard，实际设置unknown，未切换。

用户本阶段补交B2 ZIP，已核验28文件、B manifest的7项及XO内嵌C++；XML原字节不同但结构属性一致，首次失败保留。B核meta40的PC sizeof/offsetof已实际编译执行；与旧meta64/magic/done/build位宽不兼容，契约仍DRAFT、三方签核为空。B golden完整反例/真shape及RTL布局证据仍待补，不认定B核通过或已上板。C尚未交付。

可转发包 `platform/build/ra01-handoff-20261001-v1.zip`（29,198,892字节，SHA256 `d1e8a1933b2532aa3e87f0aa86b5bf5110111b757f2555a2827fd8e25a8241d6`）含72映射、9组原始激活、比较器、契约/平台/B2快照；192项完整性检查通过，另在新解压目录验证与logits诊断自检通过。12项新PC测试及17项A0回归通过。不是C/B收件、量化或板测通过；B/C实际可访问路径与回执仍null。

详见 `docs/handoffs/A_TO_BC_20261001.md`、`A_RUNTIME_TO_C_20261001.md`、`A_B_REQUEST_20261001.md`、`A_RA01_RESULT_20261001.md`。下一步用户转发包/摘要；B先回ABI与独立反例，C先回服务入口与首个sidecar小包，A做RA02平台核查。未新建commit/合并main，原分支和脏树保留；不重装、不迁移、不刷写、不做板调用。10月1—7日无板、最早10月8日为新计划，历史9月30日G1未通过仍保留。

以下为重排前历史快照；旧职责由上方RA01覆盖，证据本身不改写。

2026-09-28 A2格式无关准备完成：用户授权先做不依赖冻结件的部分。已重新审计72张量与固定llama图映射、共享head/bias，实际捕获3层9组原始FP32激活及8位置logits；方向/SiLU复算最大误差0，仅诊断。新增18项PC测试、A3对比入口和内存清单，详见 `docs/handoffs/A2_PREPARATION_20260928.md`。正式sidecar/C++ W4A8路径/独立B交叉验收仍未实施，quant_v1未冻结，A2未通过。

2026-09-28 A2启动检查：用户要求依据冻结quant_v1执行A2，但本地仍为draft.2，A/B/C签核均null；`--require-frozen`实际退出1。未收到B独立冻结向量，未开始正式sidecar/CPU路径实现，未把共同样例当独立golden。状态 `BLOCKED_MISSING_FROZEN_INPUTS`，详见 `docs/handoffs/A2_PREFLIGHT_20260928.md`。需提供冻结件/独立向量路径，或另行授权明确标识的草案原型；不因板卡未到而禁止A2软件工作。

2026-09-28板前收口：103项PC回归通过；新增有哈希/配对校验的板前材料打包器及8个测试。Common RPM数据库只读导出后，隔离事务预演因x86/ARM架构不同退出5，保留失败且未绕过。启动路线冲突已整理为明确待确认问题；尚不能生成已验证部署包。见 `docs/handoffs/A1_PREBOARD_20260928.md` 和 `platform/a1/preboard_readiness.json`。只读/离线准备与板测分开；G1仍未通过，预算null。

2026-09-28中断审查增量：已追踪固定XRT的ZOCL→CU INTC和对应内核AXI INTC源码；生成flag差异不手改，源码路径可解释但运行时待测。采集器补充中断/模块快照、xrt-smi实际报告和RPM查询；95项PC回归通过。见 `docs/handoffs/A1_IRQ_AUDIT_20260928.md`。Common Image无需重复下载；启动/内存不一致仍阻断，G1未通过。

2026-09-28后续：实测v++ package对Kria返回0但明确不生成文件，已记录而非计作打包通过。由真实链接工程导出XSA、生成候选PL overlay与bit.bin，位流与xclbin段逐字节相同；对两种候选基础DT离线合并均成功，内存/bootargs原样不变。中断flag差异待驱动审查，未部署。91项PC回归通过，详见 `docs/handoffs/A1_OVERLAY_AUDIT_20260928.md`。G1未通过，启动/实际内存仍阻断。

最新增量（2026-09-28，硬件链接）：A-vadd已完成真实v++ hardware link并生成xclbin；约150MHz布线WNS+2.242ns/TNS0，DRC违规0、路由错误0，2条方法学Advisory保留。拓扑a/b/c均HP0低地址2GiB；host加执行前BO检查并重新ARM64链接。87项PC回归通过，同版本原生构建RPM已缓存未安装。见 `docs/handoffs/A1_OFFLINE_LINK_20260928.md`。**仅离线构建，非可部署套件；G1 NOT_PASSED、Linux/PL预算null**。下文“xclbin未生成/77项测试”为历史快照。

最新增量（2026-09-28）：ZynqMP Common Image 已收到并通过 gzip/只读 ext4 检查，不再等待重复下载。其 PetaLinux 2026.1 SDK 已在独立 WSL 目录安装，GCC13.4 成功编译/链接 A-vadd ARM64 host；首次缺 -luuid 的失败保留，修复后成功。10 个核心运行库/加载器与 rootfs 逐字节一致；77 项 PC 单元测试通过。Common rootfs 尚缺 g++/CMake，原生 S0 未测；KV260 启动链和内存差异未消除，xclbin/真实板测仍未完成、G1 NOT_PASSED。见 `docs/handoffs/A1_COMMON_IMAGE_20260928.md`。下方“等 Common Image/SDK 未安装/host 仅语法检查”为历史状态。

证据保护增量（2026-09-27）：修正vadd host重复CSV覆盖、record.py先执行后占用日志路径竞争窗口、lease.py来源记录覆盖问题。设备调用前独占CSV，日志独占预留，写入失败不返回成功；新增11项回归，WSL总计71项通过，XRT host仅语法检查。见`docs/handoffs/A1_EVIDENCE_SAFETY_20260927.md`。本轮项目与Downloads顶层仍无Common Image，等待用户登录下载；未动B/C和HLS核，未上板。

最新路径复核（2026-09-27）：UG1701明确kv260_base仍是PetaLinux例外，UG1742列PetaLinux/Ubuntu，与下载总页EDF清单有冲突；安装SPFM/BIF和固定platform.mk支持继续核查Zynq MP Common Image。实际pl.dtbo含zocl但仍有占位firmware-name/AXI VIP，不能直接部署。固定zocl源码证明DT no-map与xclbin银行范围会影响CMA/range allocator分支。下一输入为官方`xilinx-zynqmp-common-v2026.1_06092129.tar.gz`，需用户AMD登录下载至C:\Patientqwen，不安装PetaLinux整套工具。见`docs/handoffs/A1_PLATFORM_ROUTE_20260927.md`；未更换运行路径、未削弱门禁、内存预算仍null。

最新固件增量（2026-09-27）：已收到并用Bootgen2026.1只读解析KV260 1.07固件；内部版本与官方条目对应，SHA和DTB证据已保存。发现bootfw的800MiB CMA与工具kv260_base的cma=1536M/高地址2GiB no-map配置不同，列为平台阻断，未擅自合并DTB或按4GB预算。见`docs/handoffs/A1_BOOTFW_AUDIT_20260927.md`。固件不再需要重新下载；实际板上版本未知，未刷写，G1仍NOT_PASSED。下文下载请求和不同测试数量是历史快照。

更新日：2026-09-27。阶段 A1，状态 **Linux AMD工具和依赖已安装，官方kv260_base可读取；Vivado官方BASIC许可与K26器件查询已通过，匹配启动镜像和真实G1仍阻断**。

镜像最新增量：用户下载的Kria2026.1 WIC.xz已通过压缩CRC、GPT、FAT及新版e2fsck只读检查；XRT2.23.0与zocl源码commit均匹配固定f6629bdc，驱动vermagic与镜像内核6.18.10匹配。58项主机测试通过。镜像未找到cmake及常用XRT头文件，匹配SDK仍缺；下一份需用户下载KV260专用1.07 bootfw用于离线核验，不能据此认定板上固件版本。详见`docs/handoffs/A1_IMAGE_AUDIT_20260927.md`，G1仍NOT_PASSED。

本轮G1准备：A自有vadd Csim、真实HLS综合和修正版RTL cosim通过（20长度/1000交易及C输出复核），XO静态接口核验通过；54项主机回归及ASan/UBSan的1000次C++比较通过。首轮cosim因测试缓冲区小于声明深度失败，失败日志保留；最终结果和产物哈希见`platform/a1/g1_status.json`及原始日志。最终DTB高地址2GiB no-map保留区已确认，Linux/PL预算仍null。定位到官方2026.1 Kria WIC及KV260 01.07 bootfw要求，WIC需用户登录下载。未削弱link门禁、未刷写、未操作B/C模块。详见`docs/handoffs/A1_G1_PREBOARD_20260927.md`。

最新许可增量：用户提供官方许可证，临时指定路径与默认搜索路径两次Vivado batch均退出0。已配置到member-a的`.Xilinx/kv260-a-2026.1.lic`，权限600，未修改shell启动文件。工具报告BASIC有效期至2027-09-27，列出`xck26-sfvc784-2LV-c`及KV260 SOM 2.0等定义。许可证被Git忽略；证据`platform/installer/evidence/linux-license-default-search.json`不含正文。HLS实际综合、硬件链接和板测未因此获得PASS；下方无有效许可证的描述为此前失败历史。

最新安装验证：Vivado/v++/vitis-run Linux 2026.1横幅build均为6511674。完整检查AMD的installLibs.sh后，默认APT预演会卸载ARM64交叉编译器，已禁止删除并改为不安装推荐包；150个所需/依赖包安装成功，补齐en_US.UTF-8，交叉编译器保留，47项回归通过。platforminfo读出K26、默认clock index 0/149.9985MHz及HP/HPC/LPD标签；不代表已验证内存容量。Vivado batch启动因无有效许可证退出42，不能执行get_parts或声称综合通过。见 `docs/handoffs/A1_LINUX_TOOLS_INSTALLED.md`；以下此前“尚未安装”段落均为历史快照，不代表当前安装状态。

存储迁移增量：用户授权整体迁移，当前项目 `C:\Patientqwen`，WSL实际位置 `C:\WSL\KV260-A-2204`。全部49,531个源文件已逐文件SHA256核对；冷VHD备份保留，WSL move退出0。D盘旧项目仅回退。第一次VHD复制期间源文件在停止后改变，校验失败已记录；完整shutdown后重新冷复制及全量校验通过，不隐藏失败。迁移后检查与运行入口见 `docs/handoffs/A1_C_DRIVE_MIGRATION.md`。Linux AMD工具尚未安装，G1仍NOT_PASSED/NOT_TESTED。

安装准备增量：`member-a/a1-installer`。用户提供2026.1 Linux安装器，已对官方SHA256校验、只解压、运行help/ConfigGen；候选Kria/Edge/ZynqMP配置与用户启动入口见 `platform/installer/README.md`。用户已操作GUI到目标目录页，尚未安装工具、尚未改WSL资源；已获授权重启WSL修复图形显示并迁移至C盘。明确只使用用户当前32GB电脑继续分阶段尝试，不再以必须提供另一台电脑作为前置条件；资源/WSL风险仍保留。

最新增量：`member-a/a1-b0`，见 `docs/handoffs/A1_B0.md`。已按指定B0对齐 `0.1.0-draft.2`，核对72个真实MLP张量并准备XO收件校验；47项Linux测试通过，XRT源码头文件语法编译通过（未库链接/板测）。
需用户完成的安装/构建机/账号事项见 `docs/handoffs/A1_需要你操作.md`。没有收到B/C独立签核，不冻结契约、不合并main。

此前Linux准备分支 `member-a/a1-linux`；交接见 `docs/handoffs/A1_LINUX.md`。
用户授权后已安装 WSL 2.7.14.0 / Ubuntu 22.04.5，未重启、未写SD/QSPI、未接受AMD新许可。
完整权重与F16 GGUF哈希已验证，Linux x86真实运行256-token提示，1/2/4线程均生成23-token回答；不加载ASR/TTS。
ARM64交叉编译通过，尚非板端原生构建/执行，也不是匹配rootfs的发布产物。
Linux回归33项通过；vadd CPU另完成20长度×50次比较及5类参数拒绝，均不计G1。
未安装Linux版AMD工具；现有Windows K26支持、匹配XPFM/镜像/SDK及实际内存范围仍阻断。
Linux与PL板端预算保持null；9月30日G1 **NOT_PASSED（NOT_TESTED）**。

以下为 A1 Linux 准备之前的历史快照；其中“权重不可用、无Linux、旧MinGW失败”已由上方新证据更新，旧失败日志保留：

A1 当前分支 member-a/a1；完整证据见 docs/handoffs/A1.md、platform/a1/README.md。
新增：vadd PC 20长度×50次比较、5类参数拒绝；12项A1测试与17项A0回归通过。
实际失败：K26 HLS目标拒绝；本机get_parts为空；模型权重两次hash失败隔离；旧MinGW编译S0失败。
未执行：.xo/.xclbin、真实板XRT/内存/恢复、ARM64原生S0。Linux/PL预算均null，不能按4GB假定。
租约/部署锁和只读板采集器已准备，仅本机核心语义验证；真实中央锁/跨机排他未测。
B/C交接入口A1_to_B/A1_to_C已准备，未声称rootfs已验证，未向未知任务发送。

以下保留 A0 历史状态：

已做：新建 Git 仓库与 main 基线，工作分支 member-a/a0；目录所有权、PR 模板、四份契约 DRAFT、共同样例、Python/C++ 本机验证、只读工具/旧工程审计。
未做：B/C 模块、模型下载/量化导出器、正式推理服务、HLS W4A8 核、xclbin 链接、远程访问、刷写或真实板测。

## 关口

| 关口 | 状态 | 原因 |
| --- | --- | --- |
| A0 本地仓库与样例 | PC_TEST | 命令与日志在 bench/runtime/results |
| 9/28 契约冻结 | REVIEW_PENDING | B/C 联系/工作目录未提供，未获得独立签核 |
| 平台版本锁定 | PARTIAL | 本机版本 banner 已记录，Linux/xpfm/rootfs/XRT/许可证未闭环 |
| 9/30 G1 | NOT_TESTED，原日期不可达 | 用户明确板卡 10 月 7 日以后才到 |
| G3/G4/G5 | NOT_TESTED | 依赖真实 G1 与 B/C 交付，不能用 PC 样例解锁 |

下一步：补齐官方匹配平台/镜像/SDK、Linux AMD工具与K26器件支持，评估硬件链接主机内存；到板后登记身份并真实执行A1。A2/A3仍需各自前置关口。
目前无 remote、无 B/C 工作区、无有效板卡租约；不代表共享协作和远程权限已配置。
实际 Codex model/effort 当前工具无法独立读取，记录 unknown，未宣称切换。代码遵守用户路由和 A 所有权。
