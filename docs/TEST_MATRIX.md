## 20261027_1446_BJT_v2 A12 实时模型长尾无板收口

三次独立真实Edge窗口75/75完整核验答案低于1秒，中位610.8ms、最慢920.2ms；冻结副本另25/25通过。每问真实CPU模型，答案缓存命中0。34/43通用前缀、连续4线程，原checker/评分/native不变；198组同输入串行/草稿396请求逐token/EOS通过，48项网页和15项浏览器回归、真实severity未命中/评分/归档通过。BOARD仍NOT_TESTED/null。详见[A12_REALTIME_TAIL_NOBOARD_SUMMARY_20261027_1446_BJT_v2.md](A12_REALTIME_TAIL_NOBOARD_SUMMARY_20261027_1446_BJT_v2.md)。

## 2026-10-27 A12 实时模型未命中优化

真实Edge同题25对，完整核验答案879.0→618.3ms中位，23/25低于1秒；两组各25次真实CPU模型，答案缓存命中0。短表达由原checker已有forms选择，目标模型逐token贪心及EOS验证，失败全清并重放。最终198组合与同输入串行逐token一致；43网页、15浏览器回归、真实197目录未命中/评分/归档及部署副本25题通过。普通24保持，新连续32/22320预算覆盖完整重放。新A53交叉构建完成；BOARD仍NOT_TESTED/null。
证据：evidence/model_pl_A/20261027-realtime-miss-opt-v1/。

## 2026-10-27 A12 核验答案复用无板验证

三个病例198键全部真实CPU生成、EOS/原checker通过；198个来源SHA与当前计划复验通过。
真实HTTP/SSE+Edge同题同输出25对：实时模型中位875.0ms、复用中位42.3ms，逐题减少中位835.8ms，25/25复用低于1秒。
实际移除一个条目后发生1次真实CPU未命中生成；7策略零模型、缓存命中零生成、同场20分冻结、10场归档与幂等通过。
39项网页测试及15项浏览器协议替身回归通过；部署副本另经真实浏览器25题与正常关闭验证。
缓存来源为MODEL_CACHE/原CPU_REFERENCE，本轮不冒称FPGA_REAL；新BOARD仍NOT_TESTED/null。
证据 `evidence/model_pl_A/20261027-verified-answer-cache-v1/`；前一轮v2与失败原样保留。

## 2026-10-27 A12 fast response 无板验证

最终部署副本实际 CPU 网页后端：25/25 固定输入 MODEL/原 checker/EOS 通过；7 策略零模型；3 组 R0/hit
普通输出与最后 prefill logits 摘要一致；同场两问、20 分冻结、旧 prefix/binding 拒绝、worker exit0 通过。
最终套件 33 次真实 CPU 生成。网页/接线 34、原绑定回归 6、真实本地 Edge 的 HTTP/SSE 协议替身 15 项通过；
三个 profile 的两类窗口均完成离线导入/预算检查。3 线程没有新的模型生成结论。
证据 `evidence/model_pl_A/20261027-fast-response-v1/`。新 BOARD、实际硬件释放及可见 10 秒仍 NOT_TESTED/null。

## 2026-10-26 A13 快速板前PC/交叉构建完成

五原生1036模块AArch64/vermagic/136项CRC通过；默认启动FIT提取DTB后两DT编译与合并
通过，关键资源与原属性保持。小总线/全零PCM交叉构建完成，8项针对结束/错误/控制及
实际PC flock检查通过；默认PLAN_ONLY与封装通过。ABI/DT首次审查失败保留，修正后通过。
复用封存RTL/CDC/STA，不重跑；无板端/音频/SDK重建，BOARD=NOT_TESTED、实测=null。
见 `docs/handoffs/A_A13_FAST_PREBOARD_COMPLETE_20261026.md` 与对应evidence目录。

## 2026-10-26 A13 厂家参考源码静态核对（非BOARD）

21份选定原始文件的Git blob/长度/SHA256及关键BD/XCI/C/DTS断言通过；PLL K量化算术
单独核对，不执行厂家代码。新增B1a/b、B2a/b与实测清单；无新RTL仿真/综合实现/CDC或
实板测试，无声学/电气PASS。维护包与实际路径兼容/停止核验未完成，BOARD=NOT_TESTED、
测量=null；按用户时间要求，dummy DT/无绑定装卸/完整控制重构/全量故障注入不再必跑。
见 `evidence/a13_A/20261026-example-based-plan-v1/source-audit-01.json` 与增补方案。

## 2026-10-26 A13 下次上板计划（仅设计，不是BOARD结果）

设计拆为A0-A3（只读/控制闭环/无资源dummy DT/无绑定模块）和B0-B4（另获恢复出口许可
后单次音频PL配置/IIC静音/仅时钟/全零TX DMA/安全停流保留所有权）。正常与异常清理
均禁自动热回载默认PL；dummy DT通过不代表真实IIC/PL通过，B4通过不代表默认恢复释放。
当前仅文档一致性核对；v2控制、DT分层、ABI复核及新BOARD均未完成。不重启、不试音。
见 `docs/handoffs/A_A13_NEXT_BOARD_PLAN_20261026.md` 与 `design/qwen35/a13_next_board/PLAN.json`。

## 2026-10-25 A13 冷启动只读BOARD观察（非音频验收）

实际UART登录/双只读载荷完成：新boot身份、五文件SHA、默认PL/GDM、191进程严格FD/VMA
扫描均取得证据；无PL用户。日志两轮不变，WARN/taint等OPEN。旧租约仍在，safe_release=false，
不归档、不重启；实际IIC/PCM/DMA/试音仍NOT_TESTED。新取得旧四正常rmmod exit0，原最终
回滚退出码null。PC解析回归3项通过（修正mtdoops词内误匹配），首版判读保留；五套历史
封存及契约/配置exit0。见 `evidence/a13_A/20261025-coldboot-postcheck-v1/REPORT.md`。

## 2026-10-25 A13 合作控制与取证准备PC增量

最终19项控制/回滚PC测试和14项本地解码测试通过。真实PC进程/UDS/flock证明模拟扫描
阻塞时仍可status/close，关闭不提前释放；硬件/扫描/回滚为替身，不证明全局内核卡死时
仍可调度。原helpers/获取门槛/工作主体AST保留，派生02无BOARD入口。
匹配内核真实BTF布局核对通过；只接受稳定、finalized、有正确ID/长度/序号的本地组件。
首次符号名拒绝及归档标记拒绝保留；无新板端访问，后端不停核证明与BOARD恢复仍未通过。
报告 `evidence/a13_A/20261025-muted-control-repair-v1/REPORT.md`。

## 2026-10-25 A13 USB/JTAG仅枚举

BOARD调试通道：固定FTDI通道A、xck26/arm_dap及四个Running A53真实可见；
第一次序列号后缀保护失败保留（wrapper exit0不作PASS），第二次明确完成标记且stderr空。
两次回环临时服务均自然退出、无残留监听。无停核、复位、内存访问、编程或音频；
Linux恢复/默认平台/safe_release未通过，不能用目标Running代替健康验收。
报告 `evidence/a13_A/20261025-jtag-enumeration-v2/REPORT.md`。

## 2026-10-25 A13 正常重启恢复测试增量

PC：Linux重启谓词5项、归档身份/原子碰撞4项通过；原Windows及UTF-8准备失败保留。
BOARD恢复：一次正常重启返回0、一次已有FIT RAM引导至登录，五件原件不变；UART/SSH
58,556字节内核raw互认。归档前207/208进程及归档后独立191进程完整扫描无FD/VMA，
三锁空、active空、默认PL/GDM正常。告警未修复，恢复专用基线不批准计算/音频。
BOARD音频、PLL/IIC边沿/DMA IRQ/低音量TTS及供电电压电流仍NOT_TESTED/null。
报告 `evidence/a13_A/20261025-normal-reboot-for-audio-v1/REPORT.md`。

# TT10-01 v3 独立板测实际结果（2026-10-25）

用户授权“现在按照精简后流程执行实板验证”，仅执行本次唯一v3窗口。原v2失败及所有原件保持。

实际状态：V3_FAILED_CMA_AFTER_PREFIX_GATES_PL_OWNER_RETAINED。TT10-01 complete=False；实际PL调用=2376；独立恢复后检=NOT_PERFORMED_OWNER_RETAINED。
原始管理器结果：{"status": "ISOLATED_PL_FAILURE", "original_failure": "AssertionError: policy response is not a model baseline", "root_refusal": "CmaFree below unchanged 98304 KiB gate", "observed_CmaFree_kib": 47392, "required_CmaFree_kib": 98304, "worker_exit_code": null, "lease_retained": true}。


详见 `docs/handoffs/A12_TT10_01_WINDOW03_BOARD_20261025.md` 与对应 execution-01/REPORT.md。全部失败保留、无自动重跑；普通应用数值/计时未完成的项保持未测，≤10秒最终验收仍未证明。

## 2026-10-25 TT10-01 v2 CPU旧格式断言失败，实板CPU关闭及独立后检通过

用户授权v2执行；新鲜基线/资源/真实双锁探测通过，唯一新窗口已消费。source-04 CPU首个diag_exact结果OK，444原始文件与旧对照全同；旧结果缺新增logits SHA和终态SHA，严格same_result拒绝，原失败保留。CPU worker合作关闭exit0，manager自然exit1、外层exit2；计算锁存不重置，租约归档。完整扫描先因进程变化不完整、后按原有有界规则完整通过，额外独立后检证实双锁空/无活动租约/默认平台与GDM正常。没有PL、重启或强杀。

旧终态SHA没有原始终态字节，不能从prefill状态补造；缺口保持NOT_AVAILABLE。独立v3旧格式桥接14项PC检查通过，旧必需字段/FNV与444原件仍严格比对，新R0/hit完整SHA比较原样保留。v3包未部署/执行，须另行授权并新鲜检查；不能重跑已消费v2。PL/CMA后续点、普通应用R0-hit和TTFT未执行到，TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v2/execution-01/REPORT.md`，后续具体计划 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v3/PLAN.md`。本轮无DeepSeek调试/验收委派，模型设置unknown；原PC通过/失败与A13条目保留。认证按用户指示仅用会话内存自动传递，不保存密码或修改SSH服务器认证。

## 2026-10-25 TT10-01恢复完成，独立窗口PC包准备完成，计算BOARD未验收

专项一次正常重启+临时irq2启动完成，当前boot1d0499ab-f1f9-438c-969a-3e701a0d806f/6.8.12-a10irq2。旧失败租约原样归档，旧进程退出码仍null；独立后检证实活动租约空、规范双锁无主、完整FD/VMA扫描通过、默认overlay/GDM正常、ZOCL不在。启动告警对照旧基线后仅按精确原始哈希审查为恢复基线，已知限制仍OPEN、后续新增诊断不豁免。UART文本模式41个CR转换及一次本地UTF-8误读导致的首次归档拒绝保留；已用二进制base64/长度/SHA与SSH原始58363字节完全互认，严格门禁未放宽。

新window-20261025-v2/bundle-v3包含source-04 A53和最终CPU关闭通道，PC隔离导入/清单哈希/默认PLAN_ONLY通过；未部署、未执行，需新鲜计算审查及明确独立计算授权。原24/14项source-04、普通R0/hit/零后缀、A53和26项CPU关闭PC通过保留；source-03未重跑。TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收，TT10-02未开始、A12第11步PENDING、A13保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/REPORT-RECOVERY.md`，新窗口 `evidence/model_pl_A/20261024-ttft10-01-v1/window-20261025-v2/PLAN.md`。本次调试/恢复/验收未委派DeepSeek，实际模型设置unknown。

## 2026-10-25 TT10-01串口/临时网络恢复，启动变化与内核告警阻断

同板身份与固定SSH复核成功；仅驻内存的192.168.2.2/24连接Unsaved=true。当前boot d6d3b16f-f78c-4efa-acaa-14fc8b076fe8、6.8.0-1036-xilinx，旧PID已不在且退出码未知，旧租约原字节保留；未执行旧恢复/信号。两次完整FD/VMA扫描通过，默认overlay/GDM正常、ZOCL不在，但内核有X.509 WARNING/调用栈等195行严格诊断匹配，未批准为计算基线，严格释放尚未证明。三件启动原件只读备份大小/SHA一致；一次正常重启+已有irq2临时启动的具体维护方案已备，未获专项确认、未执行。本次无模型/测试PL/重启/刷写/租约改写，新窗口未准备。TT10-01未完成、新增PL=0、实板TTFT=null、≤10秒未验收；原PC通过、历史失败及A13条目保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/PROGRESS-02.md`，计划同级 `BOOT_PLAN.md`。本次调试与验收未委派DeepSeek，实际模型设置unknown。

## 2026-10-25 TT10-01 CPU关闭通道PC通过，未部署且不恢复板端

独立管理器源码修订evidence/model_pl_A/20261024-ttft10-01-v1/cpu-close-20261025-v1/manager-source-03完成CPU登记、合作关闭、正常退出后新鲜关闭检查，计算锁存不解除，原完整扫描/默认平台/GDM/归档/双锁规则保留。最终26项PC测试通过，含2项真实source-04 CPU模型关闭/取消，以及派生失败入口在PC进程内exit1、失败结果与租约归档；原失败不改为计算PASS。超时、坏退出、身份/设备/租约/内核/扫描/GDM异常与关闭时quarantine仍保留owner。原余量阈值不变，拒绝前保存准确样本。平台/GDM/内核/设备状态仅PC夹具，BOARD未测试。

原204个保护文件SHA/长度不变；旧包新增15个测试字节码已归档，清理被自动审批拒绝（blocked by policy）而留在原位，原源码/manifest/证据未变。DeepSeek仅排版25个固定测试名称，主代理核验，核心实现与验收未委派；实际模型设置unknown。首次DrvFS检查及第二次测试失败保留。无SSH/板端更新/恢复/终结/租约操作，无新板包或独立窗口准备。TT10-01未完成，PL新增0、实板TTFT=null、≤10秒未验收，TT10-02未开始、A12第11步PENDING，A13条目保留。用户另行授权恢复并证明释放后才准备独立新板测窗口。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/cpu-close-20261025-v1/REPORT_PC.md`，接续 `docs/handoffs/A12_TT10_01_CPU_CLOSE_PC_20261025.md`。

## 2026-10-25 TT10-01 source-04无板复核通过，阶段仍未完成

已修复对照路径、JSON logits位置键类型和重复运行目录问题；旧BOUNDARY摘要缺完整哈希字段，改从source-03已有原始文件只读重算，未重跑source-03模型。保留两次原始失败及本轮文件总数检查失败（443个二进制文件+1个manifest=444，逐文件哈希相同）。source-04共24项检查和14项脚本回归通过：144条完整投影流、108个完整logits、混合状态与R0/恢复及source-03逐字节摘要相同；普通应用DEV-001的1对R0/hit、原内容检查、自然EOS、零后缀及worker正常exit0通过。命中复用70、新算37 token。固定2026.1 SDK/cortex-a53交叉构建通过，未部署或板端运行。

5044个本轮保护文件长度/SHA不变，原source-03的89项及25对结果不重记到04；V07/V08质量拒绝和教师审核PENDING保留。BOARD旧窗口仍仅有CPU阶段隔离记录，当前现场未重查；本轮无SSH/恢复/终结进程/租约操作，新增PL调用0、实板TTFT=null，不宣称10秒达标。下一步先补CPU故障合作关闭/正常终结及独立新鲜关闭检查，保持计算锁存/未知DMA隔离；用户另行授权恢复后再审查独立板测窗口。TT10-01未完成、TT10-02未开始、A12第11步PENDING、默认后端不变；A13条目保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/SOURCE04_NO_BOARD_REPORT.md`；最新接续 `docs/handoffs/A12_TT10_01_SOURCE04_NO_BOARD_20261025.md`。


## 2026-10-24 TT10-00输入、计时与R0对照冻结完成

25条真实问题与7条策略响应分账，原17条提示词/token字节不变；确认中性前缀70token、变化后缀35—46token。最终27项PC检查及两轮4次真实PC请求；健康版/02版独立BOARD窗口9360真实PL调用，443份投影/logits/混合状态逐位一致、应用事实检查和正常释放/独立延时恢复通过。TTFT_app包含实际路由、模板与原生分词，普通/剖面分开；基线R0未达10秒，缓存仍NOT_IMPLEMENTED。CROSS_BUILD为NOT_REQUIRED_UNCHANGED_A53，下一项TT10-01；默认后端不改、A12第11步PENDING、A13既有条目保留。报告 `evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md`，输入/计时/对照与预算均已封存。

健康版首次独立后检失败及02首次创建租约前扫描拒绝均保留；精确初始子条件未保存，记UNKNOWN，不追认为已知瞬态。只读复核后分别追加后检、独立v2窗口，未放宽门槛或强制清理。


## 2026-10-24 A13 不改线时钟算术与TTS文件候选

21项PC测试PASS，含精确320/147转换、时长、镜像抑制/增益/满幅、格式/截断/
链接/覆盖负例、16/32槽PLL、双驱动及独立节拍拒绝、36组假设预算和慢时钟负例。
两次真实PC Matcha+Vocos合成exit0，不播放；最新v2从保存的22050单声道PCM16
精确生成48k双声道，独立复算字节相同。ARM包4wheel RECORD校验、19资源、144
ELF架构核验完成，未安装；x86调用ARM启动器预期exit2且无输出目录，不能记成
ARM执行通过。PC RSS303776KiB，A53值null。新RTL仿真/综合实现/BOARD均未跑；
原CDC三条、IIC物理时序与回滚仍待测，3.3V总100mA、电流null、试音0。证据
`evidence/a13_A/20261024-audio-nowire-tts-v1/`，原918封存与TT10成果不改。

## 2026-10-24 A13 CDC/IIC/模块时钟无板核验

新增19项PC：跨位采样正/负例、冷启动反例、2kΩ/300ns RC预算、匹配内核IIC
整数计时、PLL因子、名义频差示例和新禁流参数入口。两个Vivado2026.1只读
a06作业真实exit0；5条既有FIFO bus-skew MET、最差slack9.841ns。3条配置
CDC警告未豁免；IIC引脚路径实际提取，inf明确为未约束、外部NOT_TESTED。
2个AArch64禁流模块6.8.12-a10irq2交叉构建/readelf/modinfo通过，未安装。
汇总脚本2次空白匹配失败保留，v3实际exit0。新RTL仿真/COSIM/BOARD未测；
未重综合/实现、不变更a06。电流/电源轨/IIC边沿/共源时钟/实板回滚仍无测量。
3.3V总100mA、null、不试音，旧760封存不改。证据
`evidence/a13_A/20261024-audio-offline-signoff-v1/`，实测清单独立列顺序和原因。

## 2026-10-24 A12 短输入TTFT10计划：文档与既有数据分析

当前入口 `docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md`；旧CPU计划暂停推进。
本轮仅本地封存token数组前缀审计及文档入口同步，前缀快照、应用新计时、模板
候选、CPU/PL新性能均未实现或运行。新PC运行测试/CROSS_BUILD/BOARD为NOT_TESTED，
新TTFT=null。后续须比较同提示词R0与完整状态恢复、验证质量/混合状态/生命周期，
并在冻结短输入支持集记录每条10秒违例。旧PASS/失败不变；证据
`evidence/model_pl_A/20261024-ttft10-plan-v1/`。

## 2026-10-24 A13 补装与真实离线构建

官方Add retry02、完整安装后审计、准确K26/11类IP目录检查exit0；旧失败保留。
25项PC安全/核验测试通过；473旧封存文件哈希不变。a04真实综合/布局布线到达，
但XDC foreach失效导致NSTD-1/UCIO-1拒绝bitgen，exit1；并发现重复PS主时钟
TIMING-4/27，不接受该正时序为签核。a06独立No_buffer修订已真实综合/实现并生成
bit/XSA/DCP/9报告，原生/队列/核对exit0；WNS5.460/WHS0.010ns、TNS/THS0，
17702网络全布通、routing errors0、DRC Error/Critical0。CDC-6×3与IIC delay×4
仍开放，正时序仅覆盖声明约束，候选不部署。新disabled DT IRQ104/105/106无警告本地合并
通过，9节点disabled，实际HWH地址/IRQ已核对；不是板上DMA递送。Csim/Cosim、
BOARD音频/电流/声卡/实际回滚NOT_TESTED，0本轮板写和录放音。详见
`evidence/a13_A/20261024-audio-pl-build-v2/REPORT.md`；下方历史结果不追改。

## 2026-10-24 CPU02管理路径优化

02无板及BOARD有界工作完成，决定ACCEPTED_BOUNDED_SAMPLE_CPU02。35项PC故障/协议验证；两个新窗口9792真实PL调用，旧/新数值逐位一致、逐次持久许可与正常恢复通过。不可变日志表示/摘要复用、逐次锁FD直查及同schema紧凑持久日志已实现，每次fsync和新鲜安全检查保留。普通自然回答2次配对，最终08更多重复仍待做；报告 `evidence/model_pl_A/20261024-cpu-opt-02-v1/REPORT.md`。01A/03/数学/默认FPGA/启动未改，A12第11步PENDING，A13保留。实际模型设置unknown，无子代理。


## 2026-10-24 CPU01兼容与板上更新

01A共享输出头缺口在A独立派生版修复，旧格式/V2读取器与01B兼容，PC/A53/BOARD通过，CPU计划01完成。两个新窗口7632真实PL调用；旧/新同板全部投影、logits及混合状态逐位相同，正常关闭并独立/延迟恢复通过。候选部署于`/var/lib/kv260-a12/cpu01-integrated-20261024-v1`，原基线与失败保留；扰动仅单样本描述，不宣称低扰动/加速，02/03未实施，默认FPGA不变，第11步PENDING。报告 `evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/REPORT.md`。实际模型设置unknown，无子代理。

2026-10-24 A12 CPU队友01A回交核查：REVIEWED_CHANGES_REQUIRED_TIED_OUTPUT_HEAD。446 payload/396原日志及基底/补丁hash匹配；Linux OpenMP实际6旧检查、126投影、157分类断言、60图/1308断言和ELF入口通过，1/2线程40性能样本完成。发现当前模型token_embd共享输出头漏识别，独立反例exit1；需修订，classification_accepted=false。V2旧读取器适配待A实施；本机合成图观察开销约23.4%/34.0%，不作低扰动或板速结论。未改原交付、01B/03、默认选择或旧失败；无板连接，ARM/BOARD未测。证据 `evidence/model_pl_A/20261024-cpu-peer01a-review-v1/REPORT.md`。 下方历史保留。

2026-10-24 A12 CPU优化01B完成：PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS。13项Linux PC控制路径、8文件观测去除AST等价核对通过；两个独立顺序BOARD窗口共6480真实PL调用，manager/worker正常exit0，独立及延时恢复检查通过。实际prefill/decode逐条归属和管理/健康/持久记录/通道余额、观察扰动已分账；同程序/库/位流，输出摘要匹配。01A/03未改，02未实施；全01仍待队友01A。A12第11步与默认FPGA关闭保持。证据 `evidence/model_pl_A/20261024-cpu-opt-01b-v1/REPORT.md`。 下方保留历史。

2026-10-24 A12 CPU优化00（LOCAL_FILES_NO_MODEL）：契约/配置/冻结/独立审计exit0；125包文件、71回读文件、154资产、308原封存文件、476副本、5组请求、6行原始配对计时核对通过。已有输出重用exit1为预期拒绝。新PC模型/交叉构建/BOARD均NOT_TESTED，新优化结果null；没有复跑17条开发样本或状态用例。 证据 `evidence/model_pl_A/20261024-cpu-opt-00-v1/REPORT.md`。下方保留历史。

2026-10-24 WM8960候选：历史/新版校验exit0，8个PC安全测试exit0、匹配GCC13.4两模块AArch64交叉构建exit0、DT v6无警告编译/离线合并exit0。14实例IP静态名检查不是BD验证；Windows BASIC有效但K26/xczu0，WSL启动42。BD/Csim/Cosim/综合/实现/BOARD绑定/DMA/电流/声学/回滚均未测，无新板连接。GCC11/已有pahole路径/静态动态端口与中间DT警告失败均保留。证据 `evidence/a13_A/20261024-audio-pl-v1/REPORT.md`。

2026-10-24 A13 03：BOARD_READONLY_ENV_AUDIO_INVENTORY完成，功能音频NOT_READY。3次SSH exit0，身份/boot/ABI、root与普通用户ALSA、实际/proc/config.gz、驱动文件、DT/I2C注册、磁盘/温度/内存及独立状态读回已保存。PC5个只读保护测试与独立实际日志显示差异比较通过；首次汇总exit1等原件保留。WM8960 capture/playback/格式、音量设定、电流/声学、ASR/TTS/200轮/2小时仍NOT_TESTED。证据 `evidence/a13_A/20261024-step03-v1/REPORT.md`；本轮0 stream/0 I2C探测/0PL装卸，不扩写Csim/综合/交叉构建PASS。

2026-10-24 A13 01—02：PC_STATIC_LOCAL_ONLY。契约/配置、6类审计工具保护、44语音锁项、9 wheel/146 AArch64 ELF、模型与144 sidecar payload、14 A12参照、33 Python源码解析与3病例审核状态核验exit0；原200轮六份材料hash复用，无模型重跑。v1许可证字段失败、v2复制表不存在入口失败均保留，独立v3通过。数据/日志见 `evidence/a13_A/20261024-steps01-02-v3/REPORT.md`。ARM64安装/import、BOARD语音、录放音/声学、200轮/2小时均NOT_TESTED；未新增Csim/Cosim/综合/实现/交叉构建结果。

2026-10-24 A12健康检查专项：PASS_HEALTH_ONLY_BOARD_BOUNDED。统一主线程/许可线程检查调度、只读常驻kmsg增量读取、复用温度路径；每次许可仍新鲜观察并fsync。3240真实PL调用、3样本同板CPU/PL及旧PL的token/文本/EOS/prefill摘要匹配；自然普通回答PL124.340→64.304秒，同轮CPU73.987秒；健康剖面69.202→11.789秒。短样本PL仍慢，长上下文未复测，危险故障/性能统计限制保留。两worker/manager exit0，正常默认恢复及独立/延时后验通过，旧2547封存文件不变。原ARM/位流/数学/契约不变，默认FPGA关闭，11未做。报告 `evidence/model_pl_A/20261024-health-opt-v1/REPORT.md`。

2026-10-24 A12第10步完成：同板CPU/PL公平小样本普通模式与轻量分项、完整病例回答及128/1022输入通过独立审计；真实PL 17856次，重复完成报告/健康日志已按基线定位并在新窗口验证修复，输出token/文本/EOS和prefill摘要匹配。任务09与历史FAIL/24691文件保持；两窗口正常恢复并独立/延时复核。速度、瓶颈和样本时间比见 `evidence/model_pl_A/20261024-step10-v1/REPORT.md`；无p95/统计显著、物理总峰值/功耗/硬件周期/AXI字节仍null。默认FPGA关闭，R0长输入成本保留，A12任务11未完成。下方为历史快照。

2026-10-24 A12第09步完成（PC/BOARD分域、保留限制）：T1/2/4/8及尾块、连续decode、R0/reset、两份合成病例切换重放、R1/R2拒绝通过；同板CPU/PL短logits和原始混合状态逐位一致。默认1024上下文以1022输入+2输出预算验证chunk8/256，状态/最终prefill指纹匹配，进程内全词表差异0。真实PL共24192次；完成边界取消后禁止新submit、丢弃迟到结果、旧worker不可复用，正常恢复后新窗口匹配基线。实际ARM两项启动拒绝exit2、无设备打开许可/静默回退；策略7条为PC无模型。两窗口正常exit0并独立/延时复核释放恢复；旧FAIL及16202历史文件保留。2048、危险BOARD在途超时/POISONED/拔除未测，默认FPGA关闭，R0长输入交互延迟风险待10实测，性能/物理总峰值null；10/11未做。报告 `evidence/model_pl_A/20261024-step09-v1/REPORT.md`。下方为历史快照。

2026-10-24 A12第08步完成（有限范围、保留限制）：24层72投影完整诊断，216次真实PL返回Y及消费者核验通过；逐层输入输出、节点、10行logits和混合状态与同板S1逐位一致。冻结开发集17条同板CPU/PL自然生成配对通过，PL实际25776次；7条策略模板单列为PC无模型，原始语言检查{'pass': 17}，医学审核未完成。每窗口72份权重只加载一次、148BO共140591104B复用；两窗口worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。一次正常重启仅FSBL的失败保留，专项授权冷启动恢复irq2，默认启动文件不变；直连使用未保存NM配置。06旧FAIL保留；正常生成关闭逐调用Y诊断账，216次重诊断证明单列。默认FPGA未启用，物理峰值/硬件全局计数/加速比null；09未启动。报告 `evidence/model_pl_A/20261024-step08-v1/REPORT.md`。下方为历史快照。

# Qwen3.5 分域测试矩阵

2026-10-24 第06步两项遗留失败复核完成：跨PC/ARM整图FAIL复现并保留，17组同输入独立标量复算（含9次真实PL输出）逐位一致，同板S1/S2为第08步唯一硬件数值基准，该跨ISA限制不阻断08。新独立窗口实际驻留72份权重、148个BO共140591104B，group3/低2GiB/不重叠/8192分配对齐均通过；驻留CmaFree263136KiB，高于98304KiB门槛，首次容量FAIL不追改。精确7份归档哈希核对后fsync/fadvise，文件保留，无全局清缓存。管理端禁止所有submit，本轮模型核提交0；worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。两项均不再阻断受控进入08，但下一窗口须新鲜身份/内核/完整BO/资源门禁并验证全范围真实消费；08尚未启动，物理峰值/加速比null。报告 `evidence/model_pl_A/20261024-step06-review-v1/REPORT.md`。下方为历史快照。


2026-10-24 A12第07步完成：l00 gate/up/down共9次真实PL调用，T8/1/1，3份权重仅加载一次、10个BO共6062080B复用。实际Y分别被GLU/残差ADD消费；同板S1/S2的10行logits、36份投影输入输出、72诊断节点和混合状态逐位一致。两worker及manager正常exit0；v2首轮扫描短暂进程变化保留，第二次完整扫描通过后自行归档租约和释放双锁，未发强制信号。独立及延时复核默认PL/GDM恢复、无ZOCL/设备用户/active lease/相关进程。第06步两项FAIL及旧单投影收口FAIL/-9保留，第08步未启动，默认FPGA未开启、加速比null。报告 `evidence/model_pl_A/20261024-step07-mlp-v1/REPORT.md`。下方内容为历史快照。


2026-10-24 A12专项收口已完成：新鲜证实旧27132仅持锁等待且无子进程/XRT/设备后，一次pidfd定向SIGKILL结束（真实-9保留）；新finalizer正常exit0，旧租约原字节归档、双锁释放，独立及延时复核默认PL/GDM正常、无设备用户/ZOCL/active lease/相关进程。新增计算/PL装卸/服务改变/重启0。单投影既有PASS保留，三个投影/08未执行；首次收口FAIL与06两项FAIL保留。新增Window v2完成7项PC恢复测试，BOARD未测。报告 `evidence/model_pl_A/20261024-step07-finalize-v1/REPORT.md`。下方STOPPED/持锁等为历史快照。

2026-10-24 A12第07步单投影：l00 gate 3次真实PL调用T8/1/1，job1/73/145，Y被GLU真实消费；同板S1/S2的10行logits、36份抽样投影、72诊断节点、混合状态逐位一致。两worker正常exit0，默认PL/GDM恢复、ZOCL无/设备FD-VMA无；最终扫描拒绝后manager27132/startticks2110722保留双锁/active lease，无受控恢复入口。本轮STOPPED，07整体未完成，三个MLP投影/08未执行；后续先安全收口管理器，不能复用旧许可。两个06历史FAIL按用户指示保留待评估。报告 `evidence/model_pl_A/20261023-step07-single-v1/REPORT.md`。以下均为历史快照。

2026-10-23 A12 第06步：真实ARM64同板S1通过（有限范围）；T8/T1 logits及混合状态逐位一致、12组抽样投影通过、自然合成输入正常EOS。HWM770636 KiB，最高33.604°C；CPU-only两窗口正常退出，独立后验默认PL/GDM保持、无设备用户/ZOCL/锁/active lease。跨PC/ARM整图FAIL保留并定位到A8边界，同输入8组独立标量参考逐位一致；首次全模型资源附加余量FAIL保留，归档缓存定向释放后v2容量观察通过，实际PL BO/address/物理峰值仍未测。PL提交0、加速比null；07未开始。详见 `evidence/model_pl_A/20261023-step06-v1/REPORT.md`；以下旧阶段状态为历史快照。

2026-10-23 A12 01—05：PC 实现与交叉构建完成，BOARD NOT_TESTED。原 A11 PASS_WITH_LIMITATIONS 保留；下文 A12 未开始等为历史快照。8 个模型图场景与原 A05 v8 对照的 logits/混合状态逐位一致，丢弃输出被拒绝；31 控制场景/764 检查、Linux/应用/窗口/包门禁通过，最终 ARM64 候选和静态包完成。完整模型 BO 140591104B 仅推导；硬件数值、物理峰值、速度仍 null。失败保留，默认配置未启用；下一步 06。报告 `evidence/model_pl_A/20261023-preboard-v1/REPORT.md`。

## A11 实板数值与性能（2026-10-23）

PC：契约各0，引擎14、恢复编排11、最终扫描1方法通过，包/标准入口/独立审计0；旧事件名断言失败保留。BOARD：T0非法调用返回1无消费/提交；23有效调用逐文件独立复核bit-exact，job/build/guards/低地址及BO复用检查通过；完整正常退出/恢复/74.899秒独立后验通过。v2缺manifest在硬件前失败保留，v3正式包SHA64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde。整数debug接口/硬件计数器/长稳/故意超时BOARD仍未测。2026-10-23 最新：A11 PASS_WITH_LIMITATIONS。冻结23次实际调用/5次权重加载，11形状（含真实gate/up/down T1/T8/T3）FP32输出逐字节等于独立参考，最大误差0；T1服务中位数5.109–5.268ms、T8 15.257–16.764ms，均含量化/同步/复制。worker/manager正常退出，独立后验默认PL/GDM恢复，无FD/VMA/ZOCL/锁/active lease。A12未开始；下方NOT_PASSED是历史快照。见`evidence/mlp_board_A/20261023-compute-acceptance-v1/REPORT.md`。

## A11 open修复验证（2026-10-23）

PC：契约各0；诊断31场景一致/ARM64构建0；open-only17方法、量化引擎12方法、完整管理器10方法通过；新候选manifest0。BOARD v4 open8定位sx高地址；v5 open0 close0、4IO检查通过、0提交、waitpid与manager各0；68.89秒后独立资源清零/默认恢复，最高32.438°C，已有advisories保留，后验无新诊断。旧88/523/70文件封存未变。失败候选、串口超时、Windows路径/审计换行错误均保留。2026-10-23 最新：A11 open错误8已定位并修复。4KiB sx BO落到34507137024高地址而被低2GiB检查拒绝；私有分配对齐改8192，同诊断库单变量板测open0/close0、四IO地址合法、worker/manager正常exit0。独立后验默认PL/GDM恢复、无ZOCL/FD/VMA/持锁/active lease；0计算，A11 NOT_PASSED、A12 NOT_ELIGIBLE。以下旧状态为历史快照。证据`evidence/mlp_board_A/20261023-open-investigation-v1/REPORT.md`。

## A11 最终仅收口（2026-10-23）

PC：旧/新契约exit0；最终v2 WSL单元16方法exit0，包含真实冻结包与kernel baseline衔接。离线独立审计exit0，旧A10/集成/PC-v3/BOARD-v3封存88/523/31/103项未变。BOARD：preflight只读exit0；首次v1远端exit2/主机1、信号前停止（baseline differs），原失败保留；独立v2一次收口远端/主机exit0；45.04秒后独立读回exit0，默认PL/GDM、无ZOCL、完整FD0/VMA0、双锁无人持有、租约归档、等待者退出通过。收口约6.03秒、峰值采样31.396°C，0计算/硬件装卸/服务变更/重启/刷写。正常MLP worker退出仍未通过，A11 NOT_PASSED/A12 NOT_ELIGIBLE。完整命令/结果见final-closeout-v1报告与收据。

## A11 v3仅收尾BOARD（2026-10-23，最后归档未完成）

PC：历史/新版契约exit0，传输最终10方法exit0；真实finalize停止2方法、离线状态/内核/封存审计在WSL exit0。误用Windows的Linux门禁测试/审计exit1保留，未修改门禁。BOARD：stage/独立读回/status exit0；普通remove/rmmod/default-load/GDM-start各一次且exit0。首次启动路径及可选文件采集exit1发生在恢复前，修正后重新只读确认未执行再推进。最终真实扫描不完整触发硬停；56.176秒后独立完整FD0/VMA0、无ZOCL、默认PL/GDM已恢复，双锁与租约仍由8851保留，监督器退出码null。0计算/计算BO/重启/刷写；A11 NOT_PASSED，不将默认恢复等同A11通过。完整原始/缺陷与命令见`evidence/mlp_board_A/20261023-cleanup-board-v3/`。

## A11 收尾v3（2026-10-23，仅PC）

最终`tests_04.json`：30方法exit0，冻结原4次扫描准确复现旧NO_TWO_COMPLETE、v3完整扫描门禁通过；六阶段逐点暂停/新授权续接无重复、六阶段未知动作硬停、引用/设备/权限/boot/内核阻断、PID复用、root控制/防重放、真实WSL Unix socket及flock、实际adapter模拟完整恢复路径。旧/新契约exit0，路线判定与候选打包exit0，旧88/523/88项封存不变。本轮BOARD连接/动作0，候选未部署，A11仍未通过；不把测试夹具当设备释放证据。见`evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/REPORT.md`。

## A11 仅收尾两次窗口（2026-10-23）

PC原收尾6方法、续接13方法exit0，旧/新版契约exit0，历史A10 88项/A11 523项哈希不变。BOARD定向终止3308/3202后完整扫描VMA0/refcount0；经第二授权终止无native等待者5322。新6174在只读稳定性门禁停止，普通卸载/默认配置/GDM恢复未执行；本轮计算0，A11未通过。独立readback_01 exit0完整无设备占用、引用0，无新增内核文本，不能替代恢复通过。原host最终异常SSH码4294967295保留，新host尚在运行exitnull。全部扫描含失败及原始行号见recovery-continuation-v1/AUDIT.json；未将电脑用例充作BOARD验收。

## A11 打开失败补审（2026-10-23，仅PC）

`evidence/mlp_board_A/20261023-open-failure-review-v1/run_01.json` exit0；原v1及诊断v2各31场景（30失败、1正常），2编译/62运行均0。逐BO分配/尺寸/地址、逐group查询及契约、设备/UUID/run构造覆盖；返回码一致、0模拟提交、诊断失败阶段匹配。原523项封存逐项不变。BOARD操作0，无真实资源释放或故障原因结论，A11仍未通过。

## A11 集成与首次OPEN增量（2026-10-23）

PC定位补充：`open_diagnostics_01.json` exit0；独立`backend-diagnostic-v2`复跑30控制场景/600断言，核验其中6个打开失败阶段和异常详情，ARM64构建exit0。原v1源码及板上暂存包不变；新诊断BOARD NOT_TESTED，不能声称真实故障已修复。`stopped_audit_01`仅审计封存已有停止证据，不执行板端恢复。

证据根`evidence/mlp_board_A/20261023-integration-v1/`。overlay/管理器/量化引擎/资源可观测后端/ARM64构建/打包exit0；engine11、manager10、boundary19（含复用）、host6、execution-host6方法均exit0。真实运行：临时irq2启动、81文件上传/暂存、两组ARM64量化字节一致、运行时DT兼容与MLP加载通过；首次open返回8触发隔离，提交数0，无真实MLP数值或服务时间。`board_execute_01.json`为STOPPED，远端管理器未退出，不能伪造远端成功退出码。`stopped_readback_01`与`stopped_open_diagnostics_01`仅只读获取、exit0；证明VMA仍有65536字节、refcount1、恢复门禁未过。PC DT重建`fresh_platform_01.json`exit1（属性排序）保留，修复`fresh_platform_02.json`exit0；旧UART journal读超时124保留，改用完整raw dmesg快照审查，不当作干净日志。新故障定位派生不自动上板。

## A11 准备增量（2026-10-23，历史快照）

证据根`evidence/mlp_board_A/20261023-preparation-v1/`。旧/新契约各exit0；A076源/产物及A10 88封存条目核验exit0；冻结输入`freeze_02.json`exit0（复用6组独立参考、新5组CPP逐位一致）。`build_pc_02.json`exit0：派生后端30场景600断言+9数据/真实flock方法；`boundary_01.json`exit0：9子进程/错误结果/释放门禁方法。`build_arm_01.json`exit0：A53/2.18头文件库交叉构建（非ARM执行）。`metadata_01.json`exit0：MLP六BO参数/HWH/metadata对照。`board_preflight_01.json`exit0仅真实UART只读，当前1036不匹配验收irq2；计算、BO、PL加载均0。首轮手算夹具及include路径失败保留、修复后通过；无容差调整。完整维护入口联调及全部BOARD功能/恢复/计时待测，不升级A11或A12。

## A10 最小BOARD收口（2026-10-23）

`A10_20261023_single_isolation_pc_v1/tests_02.json`：Linux27/27 exit0；`host_tests_02.json`：Windows7/7（含3PS计划）exit0，首个runner解析exit2保留。`A10_20261023_isolated_single_v1/audit_tests_01.json`：10/10 PC证据反例测试exit0。BOARD仅1次N32，32输出/4080保护字正确，完整退出/扫描/refcount0/卸载/默认恢复通过；执行器与8条管理命令、GDM stop/start退出0，独立延迟读回通过。状态PASS_MINIMAL_WITH_LIMITATIONS；旧81项PC、v4真实空载/原系统冷恢复复用，不加成新板次数。实测双账、限额及未知值见resource_ledger.json，完整命令见该目录REPORT.md；1000轮取消、压力/P2安全排除，A11/A12不升格。

## A10 v4 BOARD空载（2026-10-23）

`A10_20261023_isolated_idle_v4/host_pc_tests_02.json`：PC 13/13方法+8计划，均exit0；原81项Linux控制器有效证据复用。`execute_idle_01.json`：BOARD一次空载exit0，含8条PL管理/只读命令与GDM stop/start均0；0核计算/0显式计算BO。`result_readback_01/`、`final_preflight_01.json`证明独立恢复，`audit_01.json`PC核验真实BOARD日志通过；不能将PC故障注入算实板。阶段`PASS_BOARD_IDLE_WITH_KNOWN_LIMITATIONS`，A10仍NOT_PASSED_POSTCOMPUTE_RELEASE_OPEN。下方旧未执行状态留作历史；证据根`evidence/board_platform/`。

## A10 历史资源账恢复（2026-10-23）

`evidence/board_platform/A10_20261023_resource_recovery_v1/tests_02.json`：Windows Python纯PC 7/7 exit0；`export_02.json`exit0。验证manifest/执行源码SHA、原始行号、null/单位/重复/错boot/篡改与禁止覆盖；只恢复历史数据，无BOARD执行或性能基准。此前81项控制器PC结果复用，分域计数不相加为硬件次数。历史1提交不重跑，计算后卸载仍FAILED，A10未通过。

## A10 PC联调增量（2026-10-23）

`A10_20261023_controller_integration_pc_v1/integration_01.json` exit1，夹具排序失配保留；修正后`integration_02.json`8/8 exit0；`components_01.json`81/81 exit0。真实PC构造/日志/锁/短命子进程，硬件及观测为显式夹具，绝非BOARD。`package_01.json` exit0，v4 15 payload+manifest已封存、未授权/未部署。原契约有效证据复用；本增量板连接/计算0，A10未通过。完整命令见同目录REPORT.md，证据根为`evidence/board_platform/`。

## A10 最新收尾（2026-10-23）

PC `idle_components_wsl_06.json`73/73 exit0；bootstrap2/上传3/准备执行8/专用收尾2均exit0。BOARD一次irq2启动确认；v2日志错误exit1、v3扫描竞争远端exit null，均未到PL/XRT。本轮驱动/PL/计算0。另授权仅收尾与独立终态读取各exit0：默认PL/GDM正常、无module/manager/active租约，当前irq2未返1036。空载worker和计算后释放NOT_TESTED，A10未通过；静稳修复只PC验证。完整命令、失败和证据：`evidence/board_platform/A10_20261023_isolated_idle_v1/FINAL_REPORT.md`。

## A10 隔离控制器接入（2026-10-23）

新证据根 `evidence/board_platform/A10_20261023_isolated_idle_v1/`。旧/新契约退出0；Linux62方法全部通过，Windows54方法50通过/4 POSIX跳过；既有8项最小门禁仅在Linux计通过。保留Linux首轮自扫描fd消失失败并修复；Windows广泛组合因旧POSIX入口import fcntl失败原样保留，未把该方法伪记Windows通过。UART只读19阶段55命令组、准备6计划、上传3方法、冷启动11断言通过。BOARD：原/候选FIT和恢复库哈希匹配，临时网络Unsaved=true、上传/16文件root暂存均0；一次正常关机已确认Power down。新空载执行及计算后释放尚未验收，A10 NOT_PASSED；完整命令和后续启动结果见本轮交接与原始JSON。

## A10 完整接收与PC进程边界（2026-10-23，最新）

接收包130文件校验exit0，原始一次提交/32输出/4080保护字通过，计算后卸载失败保留；不是本轮新BOARD计算。COM5只读7阶段采集，新板计算/PL/驱动/重启0，当前观察1036；初次受保护目录exit1及后续准确只读成功均保留。PC UART计划17阶段48组通过；捕获恢复6方法、4文件哈希导入0；新worker边界Windows18方法中16过/2POSIX跳过，WSL连同既有门禁/捕获共44方法全过exit0。首次Windows PID错配exit1保留，测试直接启动解释器后修复，不弱化身份门禁。新native worker/完整控制器未接入，新组件BOARD NOT_TESTED，无性能指标。证据 `evidence/board_platform/A10_20261023_peer_intake/verified_intake_receipt.json`；下节REPORT_ONLY/无板接触为初次接收历史。A10 NOT_PASSED。

## A10 外部交接接收（2026-10-23）

本轮PC：`check_contracts.py` 0、`qwen35_config.py` 0；输入两份文档的副本与SHA256核验、状态保留检查另见 `evidence/board_platform/A10_20261023_peer_intake/`。对方所称空载PASS、唯一N32 PASS、计算后卸载FAILED、正常1036恢复PASS均为REPORT_ONLY，缺原始材料，不计本轮BOARD通过。当前板状态null，新板接触/计算/启动/PL动作均0；没有重复已有效的计算或长回归。独立工作进程与新门禁实板验证NOT_TESTED，本轮无性能数据。A10 NOT_PASSED，1000轮CANCELLED_BY_USER。见 `docs/handoffs/A_A10_PEER_INTAKE_20261023.md`。

## A10最大精简窗口（2026-10-21，覆盖下方历史）

PC控制72普通+同72 ASan/UBSan断言、4信号保护0；ARM64最小host编译/板上linkage0。日志门禁最终20方法0；32路DT现场核验成立。BOARD空载load0、remove管理命令0但真实kernel BUG，初次/续行执行器均1；计算/BO为0，无默认恢复。电脑新所有权补丁实际remove函数生命周期harness原版ASan1、新版0，修补相关6方法0、独立ARM64翻译单元编译0；证据审计3方法0且拒绝将管理exit0视为成功。完整修订FIT/新板验收NOT_TESTED，A10 NOT_PASSED。详见`evidence/board_platform/A10_20261018_intake/MINIMAL_A10_20261021.md`。历史契约和有效证据复用，没有重跑200/1000轮。

## A10获准候选维护窗口（2026-10-21，最新）

收尾证据审计另有3方法exit0（真实日志SHA、未完成/重复命令拒绝、非零退出码保留），`idle_window_audit_tests_20261021_01.json`。语法/状态JSON及本次已跟踪状态文件diff检查0，不接触板子。

PC：字节日志/候选/历史空载收尾最终37方法0，新候选收尾5方法0，Windows上传计划4方法0；30启动保护断言/35UART计划0分别记录，不重复相加。dmesg raw+color冲突1、CR转换预检1、3个mock接口错误、收尾SHA录入错误1保留并修复。BOARD：正常候选boot1次；默认remove/新ZOCL insmod/普通rmmod/默认load各1次且命令exit0，独立恢复状态及原启动SHA/日志SHA读回0。外部模块标记和默认恢复2条属性告警触发失败，不标干净生命周期；测试位流0、PL计算0、计算BO0，新IRQ teardown未测，数值回归CANCELLED_BY_USER。最终29.617–31.738°C，无压力测试。报告`evidence/board_platform/A10_20261018_intake/IDLE_MAINTENANCE_20261021.md`；所有逐条命令/退出码、失败和源哈希见该报告与`idle_window_audit_20261021.json`。

## A10候选空载入口准备（2026-10-21）

PC：旧/新契约0，Windows14新方法0，Linux候选/历史空载/收尾/日志门禁共34方法0（与Windows重叠，不相加），实际7.8MB电脑包生成及独立清单/逐文件核验0。默认预览产生缓存的复现1已保留，修复后子进程预览不改包。BOARD：本轮未连接/未执行，候选空载/最小PL/BO/干净恢复仍NOT_TESTED，无实时温度补填。A10未过，数值回归CANCELLED_BY_USER。证据`evidence/board_platform/A10_20261018_intake/CANDIDATE_IDLE_PREPARATION_20261021.md`。

## A10候选真实启动及原默认返回（2026-10-20）

原模块只读备份及6,232项核验通过；独立候选板暂存6,218模块/6,231文件逐文件读回。一次候选启动登录6.8.12-a10irq1；初后检124仅日志慢传，后按确切boot补回完整候选journal exit0。用户重新上电后原内核/默认overlay/原哈希及候选保留只读0，不算主动断电故障测试。最高暂存36.432°C，当前30.052–32.718°C。PC Linux27方法全部通过、启动安全23断言、解压日志3方法通过；原37启动保护及新重接保护另列收据。路径校验1、UART容量未知退出、旧U-Boot解析2、日志124均保留。新的PL/ZOCL运行、IRQ干净卸载、小BO/单次vadd均未测试；A10 NOT_PASSED，1000数值回归CANCELLED_BY_USER。报告`CANDIDATE_BOOT_AND_RETURN_20261020.md`，机器审计`candidate_boot_and_return_audit.json`。

## A10候选暂存器准备（2026-10-20）

PC12方法exit0（含Linux renameat2不覆盖、热门禁/限速/回读损坏）；真实候选解包6218模块/6231文件/389973937B逐文件回读exit0，非板安装。UART29计划检查exit0；板只读目标/原模块/容量核实exit0，未备份原模块、未写候选。IPv6 SSH单次超时255保留，无改网。专项候选授权待回复；A10 NOT_PASSED。证据`CANDIDATE_STAGING_PREPARATION_20261020.md`。

## A10单次原系统启动路径验收（2026-10-20）

PC37安全检查exit0；真实软件重启1次、倒计时截停1次、原启动继续1次。U-Boot逐级只读查询四执行器exit0；原FIT三组件校验OK，登录后只读后检exit0，原内核/启动文件SHA/默认overlay保持，温度29.9–32.9°C。ANSI识别初失败、未定义可选变量停止、100秒登录提示未捕获及40秒空采集原样保留，未重复重启。新候选/PL/计算/BO未测；固件/overlay警告OPEN，A10 NOT_PASSED。报告 `evidence/board_platform/A10_20261018_intake/BOOT_INSPECTION_20261020_REPORT.md`。

## A10 2026-10-20重接

PC旧/新契约exit0、28动作计划检查exit0。BOARD只读重接exit0；新boot存储/原启动SHA一致，但末尾nmcli超时124，整条命令不记PASS；补工具/日志尾部只读exit0。原启动不变、无PL/计算/BO/重启/改网。本轮NM超时保留未修复，U-Boot真实能力未验证。A10 NOT_PASSED，数值回归仍CANCELLED_BY_USER。证据 `RESUME_20261020_REPORT.md`。

## A10关机后的PC配套构建（2026-10-19）

完整内核续建/新ZOCL238 CRC/模块暂存v2/候选FIT构建v2/独立archive回读均exit0。驱动136候选stub及同套san、81原版缺陷复现、6生成器方法通过；模块审计6和启动归档8方法通过。6218模块架构/版本/CRC、6127签名验证通过，91 staging原策略不签名。initramfs1669新模块与原模块覆盖相同，非模块原字节/原DT保持。暂存v1make0但缺签名门禁exit1，首次FIT工具路径失败exit1保留。BOARD本轮未连接、用户已关机；A10 NOT_PASSED、真实计算0，数值回归CANCELLED_BY_USER。见 `evidence/board_platform/A10_20261018_intake/DRIVER_AND_BOOT_CANDIDATE_PC_REPORT.md`。

## A10原启动备份与全内核电脑准备（2026-10-19）

PC：完整源树/私有依赖/配置均exit0，Image/modules/dtbs构建RUNNING（不是PASS）；原FIT提取与内核SHA/DT身份核验exit0、initramfs清单exit0，启动脚本解析8方法exit0，新版驱动元数据5方法exit0，串口计划26动作exit0。原下载404/100、计划正则误判1均保留。BOARD：只读重接、原FIT/脚本备份通过；授权内存网络创建后尾部查询124，独立Unsaved核验0，不重建。无内核/PL/驱动加载、BO或计算，最小通路NOT_TESTED。源级IRQ上下文风险OPEN，不用静态审计exit0当驱动PASS。数值回归CANCELLED_BY_USER。报告 `evidence/board_platform/A10_20261018_intake/KERNEL_FULL_PREPARATION_REPORT.md`。

## A10内核修复电脑候选（2026-10-19）

PC generator：4方法exit0。实际函数提取后的stub：原版308检查复现预期缺陷，候选304检查通过，各同套ASan/UBSan通过，不双倍计算用例；patch正反dry-run及SHA核对exit0。ARM64：3个完整翻译单元exit0，非完整内核链接；工具链13.4/13.3差异保留。CLOCK_SKEW在新PC构建目录消除。BOARD：本轮未连接/未执行，修复NOT_TESTED；A10未通过。完整内核/模块/FIT NOT_BUILT；数值回归CANCELLED_BY_USER。详细命令、失败与证据见 `evidence/board_platform/A10_20261018_intake/KERNEL_REPAIR_PC_REPORT.md`。

## A10日志门禁与准确内核源码审计（2026-10-19）

PC：新门禁9、受影响idle11、源码所有权模型8方法共28通过exit0；精确Ubuntu包SHA/无fuzz补丁及9静态断言通过。提取格式和注释误匹配两次exit1原样保留，修复后通过。BOARD：仅配置grep exit0，无新PL/BO/计算；确认experimental IRQ卸载路径配置启用，不等于补丁验证。数值回归CANCELLED_BY_USER；最小通路/BO/同步NOT_TESTED；恢复状态读回已有PASS但内核安全恢复仍NOT_PASSED。详见 `evidence/board_platform/A10_20261018_intake/SAFE_ACCEPTANCE_PROGRESS.md`。

## A10安全优先修订（2026-10-19，用户授权）

20长度/累计1000及重复数值回归：`CANCELLED_BY_USER_NOT_PASS`，不再计作A10待跑门槛。一次最小真实PL输入输出核对仍NOT_TESTED；小额BO/同步/实际地址与正常恢复仍需证据，IRQ节点引用泄漏OPEN。故意实板挂死/断电/DMA故障注入为`NOT_TESTED_SAFETY_EXCLUDED`，无活动DMA恢复通过结论。见 `docs/A10_ACCEPTANCE_SAFE_20261019.md`；历史矩阵不改写。

## A10默认配置收尾恢复（2026-10-19，BOARD）

用户专项授权后，收尾脚本exit0，remove/rmmod/default-load均exit0，独立读回通过、租约归档/SSH退出；不重新加载测试位流，无计算BO/计算。完整日志事后审计发现设备树中断节点引用泄漏（1 vs65），所以恢复状态PASS不等于clean-recovery PASS；该缺陷OPEN。原试验检查exit1不抹去。证据 `evidence/board_platform/A10_20261018_intake/cleanup-result.jsonl`，报告 `IDLE_CLEANUP_REPORT.md`。真实比较0，A10未通过。

## A10仅收尾入口（2026-10-19，PC）

11 unittest方法exit0，含包/读回、主子绑定、仅收尾命令白名单、租约身份、legacy DRM card占用、最终恢复一致性。证据 `evidence/board_platform/A10_20261018_intake/idle_cleanup_only_tests_v1.json`。新入口未上传/板跑，BOARD恢复NOT_TESTED；本增量无板连接，不重复测温或加载。

## A10一次空载实际加载（2026-10-19）

BOARD_CONFIG：卸载默认/insmod/加载测试退出0，overlay applied、renderD128出现；总入口因绑定数检查错误exit1，停止后只读exit0。默认恢复NOT_TESTED，待收尾确认，不能记空载闭环通过。PC修订主子绑定拓扑检查3方法exit0，未重新板跑。累计计数审计9方法exit0；真实空索引审计exit2，比较0。报告 `evidence/board_platform/A10_20261018_intake/IDLE_TRIAL_REPORT.md`。

## A10恢复判定与v4初始化（2026-10-19）

PC：v4原生72、同套ASan/UBSan72、4信号夹具、A53编译、来源摘要审计exit0；空载包/独立卸载读回判定4方法exit0。BOARD_READONLY：实际DFX库哈希、恢复材料、温度采集0.09379s exit0；DFX列表权限拒绝255、认证取消1、明确认证查询0分别保存。实际板库反汇编是PC静态证据，不是卸载实测。v4 BOARD/PL空载/BO/计算/故障恢复均NOT_TESTED，比较0；v3既有单次链接PASS只属于v3。报告`evidence/board_platform/A10_20261018_intake/PL_IDLE_PREPARATION_REPORT.md`。

## A10单次ARM链接与临时网络（2026-10-19）

PC：ELF9、传输4、证据摘要5方法exit0，22动作仅计划测试通过；失败快照完整保留。BOARD_LINKAGE_ONLY：单次`--check-linkage` exit0/0.03148s，LD_BIND_NOW，未打开FPGA设备。BOARD_NETWORK：临时eth0地址exit0，无默认路由，固定公钥Windows SSH exit0，WSL连接超时无板命令。BOARD_READONLY：平台采集0.11435s、子命令exit0。XRT差异节仍含rodata，不将采集exit0等同全ABI一致。BOARD_COMPUTE/BO/PL恢复NOT_TESTED，真实比较0。证据`evidence/board_platform/A10_20261018_intake/linkage_network_summary.json`及同目录`LINKAGE_NETWORK_REPORT.md`；无模型、Csim或长压力复测。

## A10重接与短测候选（2026-10-18）

新增PC FRU10方法exit0、17动作计划通过、旧/新契约exit0；暂停前60控制及同60san、4信号、A53链接v3证据复用，v1/v2构建失败仍保留。真实FRU2×1024B读取/内核摘要exit0，独立解析身份区PASS、扩展链FAIL；不把审计程序exit0误记全部FRU通过。重接COM5无shell返回，板端命令未执行exit=null，端口释放。当前ARM用户小样/PL/BO/vadd/恢复NOT_TESTED、真比较0。报告`evidence/board_platform/A10_20261018_intake/RESUME_AND_SHORT_HOST_REPORT.md`。

## A10新板驱动增量（2026-10-18）

PC：传输6方法、12动作安全计划、CR失败最小复现/3正则检查、短验收温度17方法、证据解析4方法均exit0；温度原14方法3失败与首次UART/HTTP失败保留。BOARD：固定ZOCL2.18无绑定加载/检查/普通卸载/收尾exit0，15份原始来源SHA见`evidence/board_platform/A10_20261018_intake/driver_board_check.json`。完整FRU读取exit1未通过；原固件/证书告警保留。PL/BO/vector-add/ARM用户小样/DMA恢复NOT_TESTED，A10 NOT_PASSED；没有重跑Csim/模型/长测或刷写。详见同目录`DRIVER_BOARD_CHECK_REPORT.md`。

## A07最终无板验收（2026-10-04，当前）

| 域 | 结果 |
|---|---|
| PC规则/meta | 干净包970断言、66真实归档meta/396篡改/4build与相同ASan/UBSan PASS |
| PC完整C ABI控制 | 29场景554检查与相同ASan/UBSan PASS；醒目标记替身，仅故障/传输，不计算假核 |
| Csim/Cosim | 当前本地Csim61/2800022通过；同版既有65 native RTL PASS+1恢复、66回放复用，不新跑RTL或重复计独立例 |
| 综合/实现 | 实际2026.1 target hw链接成功，原约150MHz，WNS+0.809ns、WHS+0.010ns、未约束/布线错误0；CDC safely timed；93 DRC警告/18 advisory和2 methodology建议保留 |
| ARM64交叉构建 | 新生产XRT库/host6导出9依赖PASS并干净重建；旧完整模型136单元/10库证据hash复用 |
| 交付复现 | B原preflight实际ELF/hash PASS，干净源码构建/测试 PASS，最终1101文件hash PASS |
| BOARD/ARM执行/BO/恢复/功耗 | NOT_TESTED，实际内存预算与性能为null；A12未接入PL |

正式`release/a07_b04_v3`；完整命令/退出码、原失败、hash见`evidence/A07_closeout/20261004-v1/`。A07只通过无板阶段，不等于G1或B04联合签核。

## A06最终离线接收（2026-10-04，当前）

| 域 | 结果 |
|---|---|
| 当前源码A Csim | Linux Vitis2026.1/HLS6493734实际exit0，61例/2800022检查PASS；两shape T1..8、tail1..8及错误/手算/FP32顺序 |
| PC/向量/ABI | 沿用并核验原A04独立PC、382精确SHA、17参数/meta40及源/XO/内嵌XML，不重复计算 |
| Cosim | 必需两shape T1与T8同版原始native PASS；66输出独立回放。总65 native PASS+1历史失败后恢复，未新跑RTL |
| 综合 | 复用精确XO报告，HLS slack -0.40ns，不是实现收敛 |
| 实现/ARM执行/BOARD | NOT_TESTED；A07与B04完整验收不因本次核验升级 |

A06=e227 double离线核接收PASS，hash冻结；A07仅前置解除。原所有失败保留，报告`evidence/A06_acceptance/final-20261004-v1/REPORT.md`。

## A06 A接手补全（2026-10-03，当前）

| 域 | 实际结果与边界 |
|---|---|
| A序列化补丁 | 两个派生testbench只改JSON二进制输出及CRLF；原B源码/XO不改 |
| 干净PC接收 | full50 + 真实权重/合成激活4例PASS；382文件SHA全部精确匹配，原1923payload rehash通过 |
| 归档RTL | 原66笔再次回放PASS；不是新RTL仿真，65 native PASS + 1失败后postcheck恢复区别保留 |
| 工具单测 | Windows/Linux各3方法PASS，数值修改/二进制翻转/换行不符/多文件均被拒；归档11方法PASS |
| 新版A本地Csim | NOT_PASSED；Linux许可失配，Windows2026.1备选K26 part检查exit1；无数值结果 |
| 原A独立数值/同版B仿真/综合 | 沿用已核验61例/2800022、B full50及required真实shape Cosim、确切XO报告，不重跑优化 |
| 实现/ARM执行/BOARD | NOT_TESTED；不因修好工具改变板预算、功耗或硬件误差 |

完整矩阵、命令退出码及失败保留见`evidence/A06_acceptance/a-owned-closeout-v1/REPORT.json`。A06整体仍未通过，已无等待B的项目。

## A06补交（2026-10-03，最新）

| 域 | 结果 |
|---|---|
| 实物/接口 | 1925归档文件、实际double XO及内嵌XML、14来源收据hash核验 |
| 新版A PC | A04独立61案例/2800022检查PASS；FP32 max_abs=0 |
| 新版A Csim | 许可失配exit1，数值NOT_TESTED；旧版3Csim成功仍只属旧源 |
| B同版Csim | 50笔及两shape T1..8审计PASS |
| B原Cosim＋A回放 | 65笔native PASS＋1笔原FAIL/postcheck恢复；实际66输出A04独立回放PASS |
| 向量重建 | 340字节一致、42JSON仅CRLF/LF；严格B入口exit1保留 |
| A归档工具 | 新旧共11方法最终PASS，首次Windows路径原始名问题已修复 |
| 实现/新ARM执行/BOARD | NOT_TESTED；物理预算/硬件误差null |

未签A06整体PASS；细节及负例见`evidence/A06_acceptance/supplement-v1/REPORT.md`。下方“许可已解除”仅为此前实例与旧版本历史，不覆盖本次MAC变化。

## A09（2026-10-03）

PC：新源码构建、72矩阵/145文件复现、9wheel断网新环境PASS；最终75应用/语音/控制+5部署/计量方法及两组各6反例PASS。真实WAV MODEL；no_hardware原TEMPLATE保留，定向修复后MODEL。首次缺输入/包安全检查失败均保留。Csim/Cosim/综合/实现/BOARD本轮NOT_TESTED；A07交叉构建复用，生产C++hash未变。功率/声学/BO为null，A09整体PARTIAL。报告`eval/qwen35/a09/REPORT.md`。

## A07不依赖B实物的准备（2026-10-03，增量）

| 域 | 结果 | 边界 |
|---|---|---|
| PC生产共用host逻辑 | 969断言PASS；ASan/UBSan相同969再次PASS | 不调用XRT设备，无假核计算 |
| PC ZIP/XO收件工具 | 8 unittest方法PASS | 合成结构fixture不是B实物或RTL证据 |
| ARM64交叉构建 | S1/CPU库/XRT候选库/自测/llama库PASS，136编译单元A53配置 | 不执行目标二进制 |
| SDK/rootfs库一致性 | 10个实际运行库SHA相同，ELF依赖闭包可解析 | Common rootfs不是完整KV260可启动链 |
| 本轮Csim/Cosim/综合/实现/BOARD | NOT_TESTED | 前次旧核Csim恢复PASS保留，不能迁给新版本 |

证据`evidence/A07_independent/preboard-v1/`。候选XRT六函数只证明真实SDK编译/链接；实际BO/超时/资源隔离需到板验证。A06/A07整体仍未通过，CPU默认不变。

勘误/历史边界：下表A06首次Csim许可失败已由`license-rehost-v1/REPORT.json`中的三版共183例成功补测解除；原失败行保留为首次记录，不再视为当前许可阻断。

## A06 B计算核接收（当前，2026-10-03）

| 域 | 结果 | 证据 |
|---|---|---|
| PC静态 | 244下载文件Git对象/SHA256通过，公共数学/ABI原字节一致，11项A04/A05身份保持 | evidence/A06_acceptance/static-audit.json、A04_A05_input_identity.json |
| PC数值 | 三版各61例/2,800,022检查PASS；每版2,586,304 INT32部分和及所测FP32逐位一致 | local-tests-v1/*-pc.json |
| A本地Csim | BLOCKED_LICENSE_BEFORE_SIMULATION；三次exit1，不计数值执行 | local-tests-v1/*-csim.json |
| B原有Csim | 提供方日志50笔成功；实际kernel源一致，部分testbench/runner历史哈希未闭环 | static-audit.json |
| B原有Cosim | baseline日志34笔成功，A未完整重放（五组各缺27tv文件）；reuse/double未完成 | B batches manifests + A static-audit.json |
| 综合 | B日志2026.1/K26/6.667ns存在；XO未交、负HLS slack；A未综合 | B verification/*/synth.log |
| 实现/交叉构建/BOARD | NOT_TESTED，硬件数值误差/BO预算null | REPORT.json |

A06仍未接收，不用PC零差异填硬件误差0。以下A05的PC PASS保留。

## A05续作收口（当前，2026-10-02）

| 域/项目 | 结果 | 证据（eval/qwen35/a05/） |
|---|---|---|
| PC最终v8真实物理T1/2/4/8+尾块 | PASS，72投影/23全词表位置/48混合状态数组逐位一致 | state-v8/numerics.json |
| PC与旧canonical T1固定样例 | PASS，逐位一致；不是所有长上下文无差异的声明 | state-v8/canonical-history-comparison.json |
| PC状态/功能 | 17检查PASS：取消/reset/未播重算/病例/256与1024token | state-v8/checks.json |
| PC补充压力 | 74断言PASS：3种提示、257/1025token全词表与decode、物理T8计数 | extra-batch-v8/report.json |
| PC应用 | 80断言PASS；17MODEL/7策略TEMPLATE、0非预期回退 | app-dev-v8/S1-summary.json |
| PC断网合成语音 | 两条真ASR→S1→检查→TTS→播放API完成 | voice-s1-v8/summary.json |
| PC算子历史保护 | CPU库SHA不变，沿用103 ABI与48独立SIMD样例 | batch-fix-v1/REPORT.json |
| 量化质量 | 原H0/S0/S1差异非零；医学/最终集未验收 | quality-v1/quality.json |
| Csim/Cosim/综合/实现/ARM64/BOARD | NOT_TESTED，硬件误差/BO预算null | 未执行 |

本次A05电脑工程门禁通过。旧失败不删除、不改为PASS；实际argv/退出码在`platform/qwen35/a05/evidence/continue-*.json`。以下表为首次实施历史。

## A05（首次实施历史，2026-10-02）

| 域/项目 | 状态 | 原始证据 |
|---|---|---|
| PC CPU ABI | PASS，103检查 | a05/abi-v4/summary.json |
| PC SIMD真实输入 | PASS，48整数与FP32逐位 | evidence/simd-real-v2.json |
| PC 全图/外部块状态 | PASS，仅physical T1；24层、23logits位置、48状态数组 | a05/state-v2/numerics.json |
| PC 取消/R0/病例/长输入 | PASS，17项；256/1024 token | a05/state-v2/checks.json |
| PC 最终v3 | PASS，11真实检查 | a05/final-native-v1/summary.json |
| PC 开发集 | PASS，17MODEL/7策略TEMPLATE、0非预期回退 | a05/app-dev-v3/S1-summary.json |
| PC 断网合成语音 | PASS，2条真ASR/S1/检查/TTS/播放 | a05/voice-s1-v1/summary.json |
| PC 物理较大batch同等性 | **FAIL/未闭环**；不能用API分块冒认 | a05/state-v1/numerics.json、batch-precision-v1 |
| PC 量化质量 | MEASURED_NONZERO，非临床验收 | a05/quality-v1/quality.json |
| Csim/Cosim/综合/实现/ARM/BOARD | NOT_TESTED | 没有调用，数值null |

本阶段整体PARTIAL；下一步修复物理batch或取得明确T1范围验收。完整路径前缀为`eval/qwen35/`或`platform/qwen35/a05/`；实际argv/exit在a05/evidence和a05/commands.json。36旧规则方法+3新方法通过，失败/误拒/真实deadline均保留。以下为历史。

## A04（当前，2026-10-02）

| 域/内容 | 实际结果 |
|---|---|
| PC字节/数值/拒绝 | 210断言PASS；同套ASan/UBSan再运行210，非420独立用例；6加载器测试方法PASS |
| PC完整导出 | 原BF16→72矩阵两遍；manifest逐字节相同；独立C++ BF16 pack72/72逐字节PASS |
| PC真实投影 | F16/Q4输入各24，共48；0/3/4/23层gate/up/down，T8 prefill+T1 decode；整数/FP32同数学逐位一致 |
| PC量化诊断 | 原BF16 FP32复算对W4A8同输入的NRMSE范围H0 0.062727—0.171426、S0 0.062473—0.171145；不等于全图质量已通过 |
| PC计时/内存 | 单线程O3，逐投影一次计时；含激活量化、无完整权重重排；RSS见load-profile-v2，未建立统计性能门槛 |
| PC历史保护 | 开始292旧seal全匹配；旧运行库11项身份不变；只更新状态文件且保留before |
| Csim/Cosim/综合/实现/交叉构建/BOARD | 全部NOT_TESTED；CPU普通g++不是Csim，旧vector-add不借用 |
| S1完整图、S2误差/功耗、医学 | NOT_TESTED，S2误差null；未修改病例/音频/医学审核状态 |

证据`eval/qwen35/a04/REPORT.v2.json`、逐例原始目录和`platform/qwen35/a04/evidence/`。启动命令冲突exit1保留，修复显式脚本入口后exit0；所有负例预期exit2保留，不伪装成消失的失败。下方为旧阶段。

## A03收口（历史增量，2026-10-02）

| 域 | 当前结果与范围 |
|---|---|
| PC A03功能 | PASS基线：原62单测、32真协议、6拒绝、4轮隔离外网WAV及真人录音/确认/听辨；本轮只复核真实证据，不重复计为新运行 |
| PC本轮静态核验 | 49项通过（19证据+30 A04输入），包括72个tensor各自形状/偏移/hash；旧seal的文档和两项录音修复差异明确列出 |
| PC质量 | 12合成WAV CER9.09%是历史小样；第二轮真人ASR错误与端点失败不变，单例听清不等于统计质量通过 |
| PC A04 | 前置PASS_INPUTS_READY；导出/独立数值/新激活未开始、NOT_TESTED |
| Csim/Cosim/综合/实现/交叉构建/BOARD | NOT_TESTED，未借用旧vector-add或0.5B结果 |
| 声学/医学/功耗 | NOT_TESTED或REVIEW_PENDING；ready/播放提交不冒充声学首音节 |

证据：`eval/qwen35/a03/closeout-v1/`；新实际命令日志`platform/qwen35/a03/evidence/closeout-*.json`。后续A08需长测、设备故障/额度恢复验证；A13/A15做声学与正式质量。以下是此前时点历史。

## A03 2026-10-02 增量

PC软件测试：51单测（15新增+36旧A02）、32真实worker协议检查、6拒绝检查通过；4轮断外网合成音频闭环及真实播放接口中途取消通过。12条合成ASR CER9.09%，医学词错识保留；9次端点检查保留3个停顿截断，不作为质量PASS。首次ready、WAV ready和播放提交已测；实际声学起点、麦克风和人工可懂度NOT_TESTED。Csim/Cosim/综合/实现/交叉构建/BOARD全部NOT_TESTED。阶段整体PARTIAL，报告`eval/qwen35/a03/REPORT.json`，命令/退出码`platform/qwen35/a03/evidence/`。以下历史证据保留。

## 📊 A-DESIGN-1.0 当前增量结果

| 域 | 状态 | 范围/证据 |
|---|---|---|
| PC 原 A01 | PASS 保留 | `eval/qwen35/a01/A01_REPORT.json` |
| PC 新构建 | PASS | 原固定库、新独立 native-design-v1，A唯一队列 |
| PC 集成 | PASS | F16/Q4 两套 256/1024/2048、多轮、取消、reset、fresh-process |
| PC logits/剖面 | PASS | 两套 final/legacy/all；真实后端输出行数；逐节点诊断 |
| PC 单测 | PASS，保留首次失败 | 导入6项、原配置9项；初次UTF-8问题已修复 |
| Csim/Cosim/综合/实现/交叉构建 | NOT_TESTED | 本轮不改变新默认核未验证状态 |
| BOARD/正式质量/功耗 | NOT_TESTED | 无板、不伪造医学审核；PC小样不充当产品指标 |

原始命令/退出码：`platform/qwen35/design_import/evidence/`；完整 trace、allocator 日志、报告：`eval/qwen35/design_import/`。正常与节点插桩耗时分别记录，不直接比较为优化收益。以下为 A00 历史矩阵，不用其“模型未运行”覆盖当前 A01 证据。

_A · 2026-10-02 · A00，仅工程入口验收_

---

## 📊 本轮结果

| 域 | 状态 | 实际范围 |
|---|---|---|
| PC | PASS | 包31项哈希；661项历史文件不变；恢复666文件逐项校验 |
| PC | PASS | 配置9项测试，Windows和WSL各运行一次，不相加为18个独立用例 |
| PC | PASS | 原包12项静态测试在WSL重跑；C11/C++17头文件语法检查 |
| PC | EXPECTED_REJECTION | --require-installed退出2；没有加载器不能宣布运行就绪 |
| Csim | NOT_TESTED | 新Qwen3.5默认核未实现 |
| 综合 | NOT_TESTED | 不搬用vector-add结果 |
| Cosim | NOT_TESTED | 不搬用B2小样例 |
| 实现 | NOT_TESTED | 新W4A8未链接 |
| 交叉构建 | NOT_TESTED | 本轮只查SDK文件，不称ARM构建通过 |
| BOARD | NOT_TESTED | 无板、无设备调用 |
| 质量/时延/功耗 | NOT_TESTED | 新模型与语音未运行，数值null |

## 🔗 复现与日志

Windows使用现有 `platform/local/a1/venv/Scripts/python.exe`；日志均由现有 `platform/a1/record.py --log <新文件> -- <命令>` 独占保存，包含cwd、argv、UTC、退出码、stdout及stderr。

| 日志文件（platform/qwen35/a00/evidence/下） | 命令 | 退出码 |
|---|---|---:|
| legacy-contracts.json | python scripts/release/check_contracts.py | 0 |
| checkpoint.json | python scripts/release/qwen35_checkpoint.py | 0 |
| create-branch.json | git switch -c member-a/qwen35-a00-20261002 | 0 |
| package-audit.json | python platform/qwen35/a00/audit.py | 0 |
| config-tests.json | python -m unittest discover -s platform/qwen35/a00 -p test_config.py -v | 0 |
| config-check.json | python scripts/release/qwen35_config.py | 0 |
| runtime-negative.json | python scripts/release/qwen35_config.py --require-installed | 2（预期拒绝） |
| wsl-tests.json | wsl -d KV260-A-2204 -- bash /mnt/c/Patientqwen/platform/qwen35/a00/verify_pc.sh | 0 |

WSL脚本只调用Python、gcc/g++语法检查、文件存在检查、df和sha256sum；没有XRT或目标板调用。旧require-frozen失败、RTL失败、链接失败及重试日志原样保留，新计划不将其追认为PASS。
# A08 当前分域结果（2026-10-03）

PC：固定200轮工程闭环完成（133 MODEL/67 TEMPLATE），9个故障/策略符合预期，69历史/策略单测及6新增确认控件单测通过。额外424轮后按用户要求停止，最后1条中断不计通过，两小时NOT_COMPLETED_USER_STOPPED。独立no_hardware实际任务尚未执行；fpga_required真实CLI预期退出2。资源采样FileNotFoundError保留；新控件未接线。A08整体PARTIAL，不是质量/声学/医学/实板通过。Csim/Cosim/综合/实现/A08交叉构建/BOARD本增量均NOT_TESTED。详见`eval/qwen35/a08/REPORT.md`，不覆盖下面各阶段历史有效结果。
2026-10-24 K26设备补装接续：契约/配置exit0，5817文件6240291149B备份及原关键文件/模块复核通过；官方ConfigGen第三次exit0，Add exit1缺下载认证，用户操作AuthTokenGen exit1。Windows2026.1启动/Tcl完整性检查exit0、K26仍0，不计器件安装或BD/综合/实现通过。旧203封存hash保持；活动治理连续性因CPU00合法追加失败、GBK读取失败均保留并单列复核。BOARD/电流/录放音未测。报告 `evidence/a13_A/20261024-audio-pl-build-v1/REPORT.md`。

## A13 静音板测增量（2026-10-25）

串口阶段：19项实际PowerShell门禁PC PASS；BOARD唯一BREAK+9获内核明确禁用回执，
按约停止exit2，不记level9/栈取证成功；原始140B已保存。无重启/卸载/JTAG/试音，
恢复和安全释放未通过。报告`evidence/a13_A/20261025-muted-uart-diagnostic-v1/REPORT.md`。

恢复接续：用户允许一次正常重启；三本地启动备份复验PASS，新SSH前置exit255/
payload_sent=false，UART RX-only确认双核soft-lockup。板端原件复核NOT_REACHED，
正常重启命令发送0；未恢复/未释放，不记重启PASS。见`evidence/a13_A/20261025-muted-normal-recovery-v1/REPORT.md`。

PC：131086实际C策略检查、5实际回调函数本地执行通过；四AArch64模块build-04 W=1
及A53零PCM程序构建通过。BOARD：四模块加载和PL/DT应用成功，但动态子设备未生成，
绑定FAIL，IIC/PCM/DMA测试NOT_REACHED。用户允许一次正常SIGTERM/回滚，程序提交后
回执未返回；串口新增soft-lockup/hung-task，恢复与独立释放后检UNKNOWN/NOT_PASSED。
dt-03总线修正版仅本地编译/实际boot FDT合并/源码审查通过，未上板。无试音/录音，
电压电流null，无额外重启或强制操作。报告`evidence/a13_A/20261025-audio-muted-bringup-v1/REPORT.md`。

## A13 WM8960主时钟：本轮无板矩阵（2026-10-25）

| 层级 | 实际结果 |
| --- | --- |
| PC模型／纯C | 语义5项；时钟4项含两拍负例；实际内核格式翻转/回调7项；DMA拒绝条件11项含旧u64回绕反例 |
| RTL仿真 | s05 xsim2026.1：520帧双向逐位比较、2周期TLAST、5类故障及相位/偏斜/非零回压/重同步/复位 |
| 综合／实现 | b05真实bit/XSA/routed DCP；BD关键警告0，WNS+5.629ns、WHS+0.010ns、TNS/THS=0；导出后后处理exit1保留，p04同DCP独立补验exit0 |
| CDC | 原始STA约束下网表证书9个同步FF、6条连接分别setup/hold共12报告；分析视图5条Info，Warning/Critical=0；MTBF未测 |
| 例外／静态门禁 | 13条VG146逐项核验；原始25项FAIL不覆盖；同formatter AST核对46标签位宽和属性字符串，非全自动风格PASS |
| AArch64／DT | 3模块v5、vermagic6.8.12-a10irq2；DT实际编译合并11节点disabled，XSA/HWH完整总线、TKEEP、地址/IRQ/时钟回读 |
| BOARD／电气／声学 | 全部NOT_TESTED；完整DMA系统协同仿真也未运行；本轮连接/加载/安装/录音/试音0 |

报告`evidence/a13_A/20261025-audio-codec-master-v1/REPORT.md`。982项旧证据及2266项私有TTS包已复验，不重跑旧A00，不触碰另一任务的板端占用。既有原测试记录保留。



## 2026-10-25 普通资源探测无板准备
| 层级 | 实际结果 | 边界 |
| --- | --- | --- |
| 历史保护/新版配置 | 两命令exit0 | 配置与静态检查，不是运行验收 |
| Linux PC控制 | 最终21项PASS | 明确PL/owner替身；无真实PL |
| 实际x86 CPU | R0/warm/hit、末位置logits/token/EOS/内容检查/正常关闭PASS | 完整中间状态未重测；不折算BOARD |
| 原件/包 | 父包168文件、5契约不变，46关键载荷相同；ZIP CRC PASS | 正常释放代码段相同，不是实际释放证明 |
| BOARD/CMA/时延 | NOT_TESTED/null | 无连接、部署或计算授权 |
原18/20项及初版CPU记录保留，不重复累计为独立板测。交接 docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md。


## 2026-10-25 A12 无板后续：短提示词未验收，原件电脑核对与日志PC原型完成

本轮三组短提示词各25对真实CPU R0/hit数值及完整状态指纹一致，7个策略输入零模型；内容分别20/25、20/25、21/25，全部NOT_ACCEPTED，保留拒绝/准备失败，不改checker或原107/70/37-token普通探测包。命中后新算35～46或25～36 token，均未达到此前16～24假设，不能承诺6～10秒首token。

完整既有PC原件4542文件/566008080字节已通过有界导出、全部原始字节SHA及旧比较器全字段核对；最终16项PC测试通过。导出每源文件一次读取，电脑包校验/解压核对分阶段；进程RSS33888 KiB不含系统页缓存，不是CMA回收证明，ARM导出仍未绑定。独立请求级日志PC原型最终14项通过，1000次模拟提交保留1005次所有权/1004次健康检查，持久化1005→7条，固定64条环；故障/未知仍保留所有权。不是PL完成或板端收益证据，未接入原包。

仅本地新增，BOARD/板端TTFT/收益NOT_TESTED/null，无部署/恢复/推送，不更新其他任务释放结论。先普通资源基线，再独立候选A/B；内容修复、控制/结果核验绑定、数值收口、检查位置/批许可及最终验收仍未完成。历史契约/新版配置exit0；复杂设计和证据未委派，实际模型设置unknown。详见 `docs/handoffs/A_A12_OFFLINE_FOLLOWUP_20261025.md` 与 `evidence/model_pl_A/20261025-offline-followup-v1/FINAL_REVIEW.json`。


## 2026-10-25 A12 请求日志结果核验/故障收口PC候选

独立v2修复旧原型在持续底层日志故障时异常处理再次写失败、等待许可者未获EOF的缺口；原缺陷已在PC复现并保留。新版本仅半关闭许可回复、锁存隔离/保留所有权，不视为在途完成或释放。结果结束禁用标量声明接口，接到冻结请求/BO/缓存/完成计数/状态清理/原内容checker及R0-hit比较，回执失败仍拒绝；exit0还必须有router_close和线程收口。

最终20项PC控制/真实文件I/O故障fixture通过，21种终态损坏及10种审计负例覆盖，初版13项中2错误和19项中1错误的测试预期失败及当时源码全部保留。2880次模拟许可/82条日志/4份回执是PC协议回放，不是新模型或PL。只读审计始终不给释放/重放；完整文件不能证明历史fsync成功的反例已留证。

既有短提示词75份原文重查，原25输入/事实及checker结果一致，三组20/25、20/25、21/25仍NOT_ACCEPTED。原探测ZIP、7源码、前轮6源码、168父包文件、5契约保持；BOARD/时延/CMA收益NOT_TESTED/null。未上板、部署、恢复或推送，不更新其他任务的释放判断。先原普通资源基线，再独立真实native/控制端绑定与同工作量A/B；检查位置/批许可和最终验收仍未完成。历史契约/新版配置exit0，复杂设计/验收无委派，实际模型设置unknown。交接 `docs/handoffs/A_A12_REQUEST_JOURNAL_VERIFIED_PC_20261025.md`，证据 `evidence/model_pl_A/20261025-request-journal-v2/FINAL_REVIEW.json`。


## 2026-10-26 A12 请求日志真实PC模型接入，目标仍active

新增x86 PC专用许可适配层，转发到既有CPU数学库；原生程序/CPU库不重编译，不改B或公共数学/ABI。真实模型R0/warm/hit两版各2880次CPU投影、72权重加载、2959所有权/2958健康检查；最终普通输出/末位置logits/清理与原CPU及彼此一致。PC严格日志2962→请求日志82条，各有4份回执；最终同一冻结问题的完整答案R0 9.509→4.862秒、hit 5.005→2.267秒，仅各模式一个最终样本，不折算板端或p95。独立核对原生stdout、许可链、回执与END先于交付时序通过。

真实数组ABI 5项、已记录真实响应/审计8项及真实调用链3故障关口通过。BEGIN fsync失败0提交；END失败已算1440但0答案交付；首提交健康拒绝0转发，保留旧助手误分类链并报告真正健康原因。CPU进程合作exit2，不记正常关闭/板端释放，不强杀。旧job输出可消费标志的首版真实FAIL与测试框架命名错误原件保留；修复独立v2后复测。正常/故障均无重型诊断，PL=0，硬件计数null。

旧普通探测包、前轮源码/失败、168父包文件与5契约保持。没有上板、恢复、部署或推送；CMA/板端收益NOT_TESTED/null，短提示词仍NOT_ACCEPTED。P1-2检查位置/周期健康、P1-3微批授权、PL外层独立绑定/模式切换和最终验收仍待推进，不能说仅剩上板或目标已完成。复杂设计/ABI/验收无委派，模型设置unknown。交接 `docs/handoffs/A_A12_NATIVE_REQUEST_JOURNAL_PC_20261026.md`，证据/剩余审计 `evidence/model_pl_A/20261026-native-request-journal-v1/FINAL_REVIEW.json`、`COMPLETION_AUDIT.json`。


## 2026-10-26 P1-2 PC 实测

当前新测试23项（14文件/监测+5边界+4原判据 fixture）和15项已有相关回归通过；9个真实CPU模型窗口含5正常、4故障，最终当前源码3正常/2故障均独立对账。日志阻塞故障：首提交已扣1但实际0；END已算1440但0交付。CPU EOF exit2不记正常关闭/Board释放。首次fixture错误与NTFS私有目录审计拒绝保留，未降门槛。Board/CMA/最终数值与性能NOT_TESTED/null。证据 `docs/handoffs/A_A12_FRESH_HEALTH_FENCE_PC_20261026.md`。


## 2026-10-26 A12 P1-3 本地微批许可 PC 候选

当前16项真实数组/后端、3项独立原件审计、4项关闭测试通过。最终正常/故障各2窗口；实际投影2880不变、批许可2880→40。缓存批撤销及END失败均0答案交付；v4未知在途局部END反例及v5拒绝保留。BOARD/CMA/真实DMA仍NOT_TESTED。

交接 `docs/handoffs/A_A12_MICROBATCH_LOCAL_BUDGET_PC_20261026.md`。


## 2026-10-26 A12 P1-4 PC窗口模式控制

23项新检查及11个真实CPU窗口审计通过；当前源码4窗口另列。实际父协调器退出时，子进程继续持锁并在EOF撤销，随后DIRTY拒绝重启；正常关闭后新会话默认严格、旧ID和候选锁存保持。首版遥测pidfd漏与观察库writer导出记录保留。

交接 `docs/handoffs/A_A12_MODE_WINDOW_CONTROL_PC_20261026.md`。


## A12 PL 授权候选无板进展（2026-10-26）

41个实际派生XRT后端控制用例及同组ASan/UBSan通过，A53共享库和完整gate编译对象构建完成；未知上传/启动保留BO，原普通包不变。ARM入口硬禁用，真实manager/设备代次/PL模式接线仍未完成，BOARD未测、时延收益null、目标active。详见 `docs/handoffs/A_A12_PL_AUTH_CANDIDATE_OFFLINE_20261026.md`。


## A12 PL manager协议无板进展（2026-10-26）

实际派生XRT后端双通道/继承原子页/请求日志接通：普通与sanitizer各17整窗、最终2整窗、11策略检查、2次manager真实退出通过。2880控制调用保持，消息2956→116；非模型或板端时延。缓存T旧版反例和其他失败保留，原普通包不变。实际模型route/设备代次/PL模式接入仍未完成，ARM入口禁用，BOARD未测、目标active。见 `docs/handoffs/A_A12_PL_MANAGER_PROTOCOL_OFFLINE_20261026.md`。


## A12 实际Qwen私有请求/Route无板接入（2026-10-26）

真实CPU模型11指定场景、额外4个PC探索窗口与持有pidfd并发回归通过；实际2880 CPU调用/图拷贝核验，输出/logits及运行时快照摘要匹配冻结普通CPU。A53前端/Route/私有ABI仅编译，实际PL结果未消费、ARM入口禁用。旧poll并发导致错误目标未触发的开发记录明确不接受；原失败/普通包保留。设备代次批准与PL模式仍待实现，BOARD未测、目标active。见 `docs/handoffs/A_A12_ACTUAL_MODEL_PRIVATE_ROUTE_OFFLINE_20261026.md`。


## A12代次消费门槛无板进展（2026-10-26）

A12代次消费门槛已完成PC实际模型验证：21 Linux夹具、22原生断言及sanitizer、6指定整窗和A53编译通过。共享4096页使用384字节，不加CMA BO/长前缀诊断。实际Board批准来源与PL模式仍未完成，ARM入口禁用，普通包/门槛/失败记录保留、目标active。 见 `docs/handoffs/A_A12_GENERATION_CONSUMER_OFFLINE_20261026.md`。


## A12原Owner代次来源无板进展（2026-10-26）

原Owner/Platform的租约/双锁/driver/kernel/BO来源准备代码与PL/GDM变更互锁已接；33 OS/策略、22原生断言与sanitizer、5实际CPU模型窗和A53管理签发库编译通过。冻结门槛AST保留，未加CMA BO/长诊断。真实Board来源未执行，XRT入口仍禁用；PL模式及真实Board manager/原Owner最终接口仍待接，目标active。 见 `docs/handoffs/A_A12_LIVE_OWNER_SOURCE_OFFLINE_20261026.md`。


## A12 PL模式无板进展与总审计（2026-10-26）

PL模式与同进程原Owner/双锁/启动资产门禁/最终worker接口候选已接；最终实际CPU模型普通与故障后新输入严格窗、独立审计、A53构建及目标故障用例通过。Board未执行，unknown/DIRTY和原门槛保留，普通探测包不变。总审计仍列短提示词内容及常驻SERVICE/应用路由缺口，不能称只剩上板；目标active。 见 `docs/handoffs/A_A12_PL_MODE_OFFLINE_20261026.md`。


## A12事实句短提示词无板验证（2026-10-26）

独立facts-only短提示词25/25固定输入原checker/EOS通过、50次实际CPU R0/hit、7策略零模型及8审计反例通过；新前缀34 token，新算14～21，旧snapshot拒绝。原默认/普通资源包及三旧候选失败保留。有限语法非医学审核；私有PL管理链绑定和SERVICE接线仍待做，Board未测、目标active。 见 `docs/handoffs/A_A12_FACTS_ONLY_PROMPT_PC_20261026.md`。


## A12短提示词私有协议无板验证（2026-10-26）

事实句短提示词接入实际CPU私有协议，当前25微批窗+6严格代表窗、8定向故障、13策略拒绝及独立审计通过。动态核算34-token前缀/24-token输出，原5000及健康门槛保留。生命周期持久记录后取最终fresh票据，旧V04启动失败留档；不是Board或SERVICE验收，常驻交互和新提示词Board适配仍待做，目标active。 见 `docs/handoffs/A_A12_FACTS_ONLY_PRIVATE_ROUTE_PC_20261026.md`。


## 2026-10-26 A12 有界常驻无板收口

最终25固定输入/7窗口、同会话追问与换病例、7策略零模型、容量及并发共11正常窗口，9故障窗零应用交付及原件审计通过；20项Python、真实私有Control9请求/第10拒绝和45状态标志普通+sanitizer通过。PC应用中位1.438949619秒；CLI完整stdout两次1.512574873/1.381635450秒。BOARD/A53执行、真实CMA/时延/医学未测，失败保留。

交接 `docs/handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md`；证据 `evidence/model_pl_A/20261026-resident-v1/FINAL_REVIEW.json`。
