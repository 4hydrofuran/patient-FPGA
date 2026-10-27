## 2026-10-27 A12 核验模型答案复用

经用户明确允许，固定病例198条真实模型/EOS/原checker答案已构建，精确事实键、每问复验、独立来源回执、
原路由/评分/未命中链和实际浏览器前后对照已完成。开发机25对完整绘制中位875.0→42.3ms；这是复用模式，
不是每问重新计算PL的加速，也不是板端数字。剩余仅新BOARD上的缓存可见时延、一次真实PL未命中、原Owner恢复与独立释放。
详见 `release/a12_verified_answer_cache_20261027/START_HERE.md`；当前BOARD仍NOT_TESTED/null。

## 2026-10-27 A12 fast response 无板缺口已收口

N0～N6 已实现：冻结网关内部短 prompt 注入、34-token profile/真实 hit 拒绝回退、10584 完整上下文预算、
ready、IME/SSE/会话与同钟计时、模板预编译和独立部署包。25 项真实 CPU 网页路径、7 策略、3 配对、
同场两问/20 分冻结及定向回归已通过。剩余为 B0～B4 的真实 PL 34-token 命中、板上可见时延、
连续问诊与原 Owner 恢复/独立释放；新 BOARD 仍 NOT_TESTED/null，不把 CPU/浏览器替身计作 10 秒通过。
入口 `release/a12_fast_response_20261027_v2/START_HERE.md`；旧 70-token 与所有历史失败/PASS 保留。

## 2026-10-26 A13 精简板前实现已完成

原生1036缺SIMPLE_PM_BUS改用小型私有展开驱动；五模块136项CRC、原生FIT DT合并、
禁止正常/异常热回载的新执行适配层及8项针对PC检查完成。当前板前包已封装，默认PLAN_ONLY。
剩余为下一次一次合并前检的新鲜boot/日志/互斥/供电/恢复出口绑定，以及真实IIC/DMA/
停止与独立恢复后检，BOARD仍NOT_TESTED；原物理测量与内核根因unknown不追认。
不再要求dummy DT、无绑定装卸、完整控制框架重构或全量故障注入。
见 `docs/handoffs/A_A13_FAST_PREBOARD_COMPLETE_20261026.md`，下方设计期缺口为历史快照。

## 2026-10-26 A13 例程审查未解除的缺口

例程源码/PLL算术已核对，当前必补为实际路径内核兼容、DT展开、禁热回载与正常停止。
独立clock-only API、完整v2控制与全量故障注入按时间约束延后；新BOARD仍NOT_TESTED。
厂家工程不含Linux热回载验收，不能据其放行；24MHz额外
输入方案还需改线与物理来源核验，当前不选。B1拆控制器/codec、B2拆配置/实际时钟观测，
仪器电平/边沿与电流证据仍缺。见 `docs/handoffs/A_A13_EXAMPLE_BASED_BOARD_PLAN_20261026.md`。

## 2026-10-26 A13 下一板测P0缺口

下一板测方案仅DESIGN_ONLY。仍缺当前内核的全部导入CRC/ABI审查、1036源码/FDT对照、
v2有限阶段控制与正常/异常双路径no-hot-restore、持久ENTER/RETURN及故障日志/栈路径、
PC故障注入/E2E。现有checked_close仍可能热回载，不能直接放行。上次中断关机请求
也须在下一前检消解，不向旧认证窗口继续输密码。A窗口不改真实PL；B窗口另需批准恢复
出口并逐项实测，B4停流不等于默认恢复释放。见 `docs/handoffs/A_A13_NEXT_BOARD_PLAN_20261026.md`。

## 2026-10-25 A13 冷启动后仍未放行（覆盖下方旧恢复快照）

默认6.8.0-1036-xilinx/PL与五原件已确认；严格191进程无PL占用，旧故障boot已结束。
旧活动租约原字节仍在，第三易失锁不存在，启动告警未修复；只读不归档，safe_release=false。
旧四模块正常rmmod exit0证据已取回，后续默认恢复或扫描未完成、根因unknown。尚缺获批
死租约归档/独立后检、匹配内核的新窗口、合作控制端到端装配、回滚边界核查与供电/接线
新鲜确认；静音IIC/PCM/DMA仍未达，不试音。见 `docs/handoffs/A_A13_COLD_BOOT_READONLY_20261025.md`。

## 2026-10-25 A13 恢复后新增边界

单次正常重启与既有irq2 RAM引导、默认平台恢复、死租约原字节归档、独立释放后检完成。
未修复启动告警；精确基线仅供恢复归档，不能据此加载音频或计算。WM8960仍无声卡，现有
CPU DAI/card永久EPERM，尚缺独立板测驱动的故障/IRQ/XRUN/时钟停止生命周期、静音PLL/IIC/
DMA与停止恢复实板核验；音频/TTS板测NOT_TESTED，实际电流电压null。另见
`docs/handoffs/A_A13_NORMAL_REBOOT_RECOVERY_20261025.md`；旧缺口与失败不删除。

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

## 2026-10-25 TT10-01恢复已获授权，固定SSH不可达，等待板端控制台

用户明确“授权，继续推进”，覆盖此前暂不恢复；先重新核对现场，释放/默认恢复证明后才准备独立新窗口。固定SSH超时exit255，payload_sent=false，无板端脚本/恢复/信号/租约/网络/电源操作。本机192.168.2.1/24和以太网直连路由存在，目标ARP不可达，用户确认电源/网线正常；当前未枚举串口，正引导连接J4数据USB或使用现有板端终端，只读取得IP/路由/boot。现时设备状态未知，旧PID/boot不可直接复用。授权仍有效，BOARD未验收、TT10-01未完成、新增PL=0、TTFT=null。详情 `evidence/model_pl_A/20261024-ttft10-01-v1/recovery-authorized-20261025-v1/PROGRESS.md`；原PC通过与A13条目保留。

## 2026-10-25 TT10-01 CPU关闭通道PC通过，未部署且不恢复板端

独立管理器源码修订evidence/model_pl_A/20261024-ttft10-01-v1/cpu-close-20261025-v1/manager-source-03完成CPU登记、合作关闭、正常退出后新鲜关闭检查，计算锁存不解除，原完整扫描/默认平台/GDM/归档/双锁规则保留。最终26项PC测试通过，含2项真实source-04 CPU模型关闭/取消，以及派生失败入口在PC进程内exit1、失败结果与租约归档；原失败不改为计算PASS。超时、坏退出、身份/设备/租约/内核/扫描/GDM异常与关闭时quarantine仍保留owner。原余量阈值不变，拒绝前保存准确样本。平台/GDM/内核/设备状态仅PC夹具，BOARD未测试。

原204个保护文件SHA/长度不变；旧包新增15个测试字节码已归档，清理被自动审批拒绝（blocked by policy）而留在原位，原源码/manifest/证据未变。DeepSeek仅排版25个固定测试名称，主代理核验，核心实现与验收未委派；实际模型设置unknown。首次DrvFS检查及第二次测试失败保留。无SSH/板端更新/恢复/终结/租约操作，无新板包或独立窗口准备。TT10-01未完成，PL新增0、实板TTFT=null、≤10秒未验收，TT10-02未开始、A12第11步PENDING，A13条目保留。用户另行授权恢复并证明释放后才准备独立新板测窗口。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/cpu-close-20261025-v1/REPORT_PC.md`，接续 `docs/handoffs/A12_TT10_01_CPU_CLOSE_PC_20261025.md`。

## 2026-10-25 TT10-01 source-04无板复核通过，阶段仍未完成

已修复对照路径、JSON logits位置键类型和重复运行目录问题；旧BOUNDARY摘要缺完整哈希字段，改从source-03已有原始文件只读重算，未重跑source-03模型。保留两次原始失败及本轮文件总数检查失败（443个二进制文件+1个manifest=444，逐文件哈希相同）。source-04共24项检查和14项脚本回归通过：144条完整投影流、108个完整logits、混合状态与R0/恢复及source-03逐字节摘要相同；普通应用DEV-001的1对R0/hit、原内容检查、自然EOS、零后缀及worker正常exit0通过。命中复用70、新算37 token。固定2026.1 SDK/cortex-a53交叉构建通过，未部署或板端运行。

5044个本轮保护文件长度/SHA不变，原source-03的89项及25对结果不重记到04；V07/V08质量拒绝和教师审核PENDING保留。BOARD旧窗口仍仅有CPU阶段隔离记录，当前现场未重查；本轮无SSH/恢复/终结进程/租约操作，新增PL调用0、实板TTFT=null，不宣称10秒达标。下一步先补CPU故障合作关闭/正常终结及独立新鲜关闭检查，保持计算锁存/未知DMA隔离；用户另行授权恢复后再审查独立板测窗口。TT10-01未完成、TT10-02未开始、A12第11步PENDING、默认后端不变；A13条目保留。报告 `evidence/model_pl_A/20261024-ttft10-01-v1/SOURCE04_NO_BOARD_REPORT.md`；最新接续 `docs/handoffs/A12_TT10_01_SOURCE04_NO_BOARD_20261025.md`。


## 2026-10-25 TT10-01本轮结束，BOARD隔离现场保留（未完成）

source-03的15项组件、89项完整模型、25对真实输入一致性及A53构建通过；V07/V08模型质量拒绝保留。首次BOARD在CPU诊断阶段因原CMA/内存余量门槛隔离，新增PL调用0、TTFT为null，租约/监管器保持，正常释放/桌面恢复未完成。用户明确暂不恢复、保留现场，随后要求尽快结束本轮；没有执行恢复或强杀。source-04诊断资源修订PC构建/7项I/O检查及已保存数值gate通过，但汇总脚本两次失败仍需处理，未做新A53/BOARD。TT10-01不能标完成，TT10-02未开始；默认选择不改，A12第11步PENDING，A13旧条目保留。接续见 `evidence/model_pl_A/20261024-ttft10-01-v1/PROGRESS.md`。

## 2026-10-24 TT10-00输入、计时与R0对照冻结完成

25条真实问题与7条策略响应分账，原17条提示词/token字节不变；确认中性前缀70token、变化后缀35—46token。最终27项PC检查及两轮4次真实PC请求；健康版/02版独立BOARD窗口9360真实PL调用，443份投影/logits/混合状态逐位一致、应用事实检查和正常释放/独立延时恢复通过。TTFT_app包含实际路由、模板与原生分词，普通/剖面分开；基线R0未达10秒，缓存仍NOT_IMPLEMENTED。CROSS_BUILD为NOT_REQUIRED_UNCHANGED_A53，下一项TT10-01；默认后端不改、A12第11步PENDING、A13既有条目保留。报告 `evidence/model_pl_A/20261024-ttft10-00-v1/REPORT.md`，输入/计时/对照与预算均已封存。

健康版首次独立后检失败及02首次创建租约前扫描拒绝均保留；精确初始子条件未保存，记UNKNOWN，不追认为已知瞬态。只读复核后分别追加后检、独立v2窗口，未放宽门槛或强制清理。


## 2026-10-24 A13 不改线时钟路线与TTS包准备后的缺口

保留24MHz与六信号线可选codec主＋新PL过采样从接口/设备节拍DMA，
音频采样共源、PS/AXI不要求同源。不是a06软件切换：实际HWH仍输出两时钟，
PG308把Slave mode列不支持而2026.1隐藏参数/存根暴露从接口，生产支持未证实。
原a06仅实现证据不追认功能，三条旧CDC仍在；新RTL/DMA/驱动/DT未实现，
新仿真/综合实现/BOARD未跑。建议新16bit槽BCLK32Fs，区别旧32bit槽，不能混用。
21项PC转换/模型保护测试及真实TTS文件合成通过；4wheel/19资源/144ARM64 ELF
包准备完成，未装未运行ARM。PC峰值303776KiB高于256MiB设计预算，不放宽预算，
ARM导入/库符号/指令/内存仍未测。48k转换不是ASRC，不代表解决硬件频差。
电流null，3.3V总100mA、不试音；明天外5V计划尚未生效。证据
`evidence/a13_A/20261024-audio-nowire-tts-v1/REPORT.md`。918旧封存及A12更新保留。

## 2026-10-24 A13 CDC/IIC/模块时钟无板复核后的剩余门槛

本轮完成两次a06检查点只读复核、5条FIFO bus-skew通过（最差9.841ns）、
19项PC源/算术/负例及两个加固禁流模块AArch64交叉构建。原CDC-6三条与IIC
四项缺外部delay仍保留：FIFO约束不能证明配置原子性，slack=inf不是PASS。
新候选所有open/params/trigger入口永久EPERM，未安装，不代替流式CDC实现。
WM8960手册上升/下降均300ns，不能只套100k Standard-mode的1000ns上升限；
2k上拉RC模型C上限177.03pF，实物上拉、电容/线缆、波形和总电流仍未测。
模块24MHz与PL12.288MHz独立来源未证明同步，需准确板本/供应商细节与用户
选择同源时钟方案，不能外送MCLK造成争用或只反转主从位。无板审计完成不等于
流式或电气签核完成；RTL仿真/BOARD/实际回滚仍未测、NOT_DEPLOYABLE。
3.3V总100mA、电流null、不试音不变。实测清单及工具用途见
`platform/qwen35/a13/audio_signoff/MEASUREMENTS.md`；证据
`evidence/a13_A/20261024-audio-offline-signoff-v1/REPORT.md`。旧760文件保持。

## 2026-10-24 A12 短输入10秒主线的待实现缺口

新入口 `docs/A12_SHORT_INPUT_TTFT10_PLAN_20261024.md`，旧CPU子计划暂时搁置。
精确前缀完整状态、应用计时、后缀结构及缓存后的管理/CPU计算优化均待实施。
现有17条输入共有71token前缀，仍余34—45token；71不是普遍中性前缀，不能
据此宣称10秒可达。当前02普通TTFT50.701秒为历史两次均值，未测新热请求。
原03由本线接手后移P2。新PC运行验证/交叉构建/BOARD为NOT_TESTED，A12第11步
PENDING；A13下列工作与缺口保留。

## 2026-10-24 A13 器件补装与实际构建接续

Windows2026.1准确K26器件缺口已解决，官方device-only Add及独立版本/模块/
目录/备份核验exit0，未重装升级。真实构建暴露并修复原XDC foreach未应用六脚
约束的问题；a06六脚均固定/LVCMOS33。Clock Wizard重复PS主时钟缺陷已由No_buffer
及来源断言、真实a06实现/报告闭环，WNS5.460/WHS0.010ns，原生/队列exit0。
仍有CDC-6三项多位配置一致性待验证、IIC缺四项外部delay，未豁免；候选NOT_DEPLOYABLE。
473旧封存文件未变。3.3V总100mA、电流null；模块内部轨/24MHz与PL时钟一致性、
IIC与音频物理时序、DMA/声卡/实板回滚和计算音频共存仍缺，禁止部署/试音。
当前证据 `evidence/a13_A/20261024-audio-pl-build-v2/REPORT.md`，下方为历史快照。

## 2026-10-24 CPU02管理路径优化

02无板及BOARD有界工作完成，决定ACCEPTED_BOUNDED_SAMPLE_CPU02。35项PC故障/协议验证；两个新窗口9792真实PL调用，旧/新数值逐位一致、逐次持久许可与正常恢复通过。不可变日志表示/摘要复用、逐次锁FD直查及同schema紧凑持久日志已实现，每次fsync和新鲜安全检查保留。普通自然回答2次配对，最终08更多重复仍待做；报告 `evidence/model_pl_A/20261024-cpu-opt-02-v1/REPORT.md`。01A/03/数学/默认FPGA/启动未改，A12第11步PENDING，A13保留。实际模型设置unknown，无子代理。


## 2026-10-24 CPU01兼容与板上更新

01A共享输出头缺口在A独立派生版修复，旧格式/V2读取器与01B兼容，PC/A53/BOARD通过，CPU计划01完成。两个新窗口7632真实PL调用；旧/新同板全部投影、logits及混合状态逐位相同，正常关闭并独立/延迟恢复通过。候选部署于`/var/lib/kv260-a12/cpu01-integrated-20261024-v1`，原基线与失败保留；扰动仅单样本描述，不宣称低扰动/加速，02/03未实施，默认FPGA不变，第11步PENDING。报告 `evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1/REPORT.md`。实际模型设置unknown，无子代理。

2026-10-24 A12 CPU队友01A回交核查：REVIEWED_CHANGES_REQUIRED_TIED_OUTPUT_HEAD。446 payload/396原日志及基底/补丁hash匹配；Linux OpenMP实际6旧检查、126投影、157分类断言、60图/1308断言和ELF入口通过，1/2线程40性能样本完成。发现当前模型token_embd共享输出头漏识别，独立反例exit1；需修订，classification_accepted=false。V2旧读取器适配待A实施；本机合成图观察开销约23.4%/34.0%，不作低扰动或板速结论。未改原交付、01B/03、默认选择或旧失败；无板连接，ARM/BOARD未测。证据 `evidence/model_pl_A/20261024-cpu-peer01a-review-v1/REPORT.md`。 下方历史保留。

2026-10-24 A12 CPU优化01B完成：PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS。13项Linux PC控制路径、8文件观测去除AST等价核对通过；两个独立顺序BOARD窗口共6480真实PL调用，manager/worker正常exit0，独立及延时恢复检查通过。实际prefill/decode逐条归属和管理/健康/持久记录/通道余额、观察扰动已分账；同程序/库/位流，输出摘要匹配。01A/03未改，02未实施；全01仍待队友01A。A12第11步与默认FPGA关闭保持。证据 `evidence/model_pl_A/20261024-cpu-opt-01b-v1/REPORT.md`。 下方保留历史。

2026-10-24 A12 CPU优化00：基线身份、工作量、指标边界与回退定位已冻结，仅关闭本地证据可追溯缺口。许可prefill/decode内部细分、14.264秒默认桶细分、候选收益和健康版长输入仍待测；01B/02及队友01A/03尚未验收。不把本地冻结解释为新BOARD或最终收口。 证据 `evidence/model_pl_A/20261024-cpu-opt-00-v1/REPORT.md`。下方保留历史。

2026-10-24 WM8960增量：新增PL/IIC/clock/双DMA候选Tcl/XDC、两个已交叉构建的真实codec/formatter禁流模块、默认disabled DT（编译/合并通过）及8个PC安全测试；仍PARTIAL_OFFLINE_CANDIDATE_NOT_DEPLOYABLE。Windows2026.1/BASIC有效但K26/xczu缺器件库，WSL启动exit42许可不匹配，BD/综合/实现未测；不能换目标代验。100mA电流null、内部供电轨/时钟一致性/IO时序与音频生命周期/实板回滚、计算音频共存仍缺；无板端操作/录放音。详见 `evidence/a13_A/20261024-audio-pl-v1/REPORT.md`。下方保留历史盘点。

2026-10-24 A13 03已定位D10/D11接入缺口：当前Python3.12.3/AArch64/glibc2.39基本匹配现有候选，磁盘/空闲资源已有BOARD读回；WM8960驱动模块与I2S内核支持存在，但live DT/声卡缺对应通路，仅DP播放、无capture。需独立PL/DT/clock/DMA/codec绑定与用户权限方案；实际格式、音量控件、语音驻留/峰值和模块输入电流仍未测。100mA上限不能由降低软件音量保证，未试音。详见 `evidence/a13_A/20261024-step03-v1/REPORT.md`。A12最终收口与后续BOARD语音验收独立保留。

2026-10-24 A13 01—02本地准备完成，D02/D10/D11/D12差距见 `evidence/a13_A/20261024-steps01-02-v3/ARM64_GAP.md`：现有9 ARM/cp312候选并非目标导入通过；WM8960附件仅接线输入，供电/电平/时钟/控制器/ASoC/DT/ALSA与overlay共存待核；pc_audio固定WSLg，PC整机通用关闭不可直接管理PL。44锁项与146 ELF静态核验通过；A12任务11、ARM import、板端语音、声学/质量/医学仍待。未实施P2或改默认选择。

2026-10-24 A12健康检查专项：PASS_HEALTH_ONLY_BOARD_BOUNDED。统一主线程/许可线程检查调度、只读常驻kmsg增量读取、复用温度路径；每次许可仍新鲜观察并fsync。3240真实PL调用、3样本同板CPU/PL及旧PL的token/文本/EOS/prefill摘要匹配；自然普通回答PL124.340→64.304秒，同轮CPU73.987秒；健康剖面69.202→11.789秒。短样本PL仍慢，长上下文未复测，危险故障/性能统计限制保留。两worker/manager exit0，正常默认恢复及独立/延时后验通过，旧2547封存文件不变。原ARM/位流/数学/契约不变，默认FPGA关闭，11未做。报告 `evidence/model_pl_A/20261024-health-opt-v1/REPORT.md`。

2026-10-24 A12第10步完成：同板CPU/PL公平小样本普通模式与轻量分项、完整病例回答及128/1022输入通过独立审计；真实PL 17856次，重复完成报告/健康日志已按基线定位并在新窗口验证修复，输出token/文本/EOS和prefill摘要匹配。任务09与历史FAIL/24691文件保持；两窗口正常恢复并独立/延时复核。速度、瓶颈和样本时间比见 `evidence/model_pl_A/20261024-step10-v1/REPORT.md`；无p95/统计显著、物理总峰值/功耗/硬件周期/AXI字节仍null。默认FPGA关闭，R0长输入成本保留，A12任务11未完成。下方为历史快照。

2026-10-24 A12第09步完成（PC/BOARD分域、保留限制）：T1/2/4/8及尾块、连续decode、R0/reset、两份合成病例切换重放、R1/R2拒绝通过；同板CPU/PL短logits和原始混合状态逐位一致。默认1024上下文以1022输入+2输出预算验证chunk8/256，状态/最终prefill指纹匹配，进程内全词表差异0。真实PL共24192次；完成边界取消后禁止新submit、丢弃迟到结果、旧worker不可复用，正常恢复后新窗口匹配基线。实际ARM两项启动拒绝exit2、无设备打开许可/静默回退；策略7条为PC无模型。两窗口正常exit0并独立/延时复核释放恢复；旧FAIL及16202历史文件保留。2048、危险BOARD在途超时/POISONED/拔除未测，默认FPGA关闭，R0长输入交互延迟风险待10实测，性能/物理总峰值null；10/11未做。报告 `evidence/model_pl_A/20261024-step09-v1/REPORT.md`。下方为历史快照。

2026-10-24 A12第08步完成（有限范围、保留限制）：24层72投影完整诊断，216次真实PL返回Y及消费者核验通过；逐层输入输出、节点、10行logits和混合状态与同板S1逐位一致。冻结开发集17条同板CPU/PL自然生成配对通过，PL实际25776次；7条策略模板单列为PC无模型，原始语言检查{'pass': 17}，医学审核未完成。每窗口72份权重只加载一次、148BO共140591104B复用；两窗口worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。一次正常重启仅FSBL的失败保留，专项授权冷启动恢复irq2，默认启动文件不变；直连使用未保存NM配置。06旧FAIL保留；正常生成关闭逐调用Y诊断账，216次重诊断证明单列。默认FPGA未启用，物理峰值/硬件全局计数/加速比null；09未启动。报告 `evidence/model_pl_A/20261024-step08-v1/REPORT.md`。下方为历史快照。

# A-DESIGN-1.0 设计导入差距

2026-10-24 第06步两项遗留失败复核完成：跨PC/ARM整图FAIL复现并保留，17组同输入独立标量复算（含9次真实PL输出）逐位一致，同板S1/S2为第08步唯一硬件数值基准，该跨ISA限制不阻断08。新独立窗口实际驻留72份权重、148个BO共140591104B，group3/低2GiB/不重叠/8192分配对齐均通过；驻留CmaFree263136KiB，高于98304KiB门槛，首次容量FAIL不追改。精确7份归档哈希核对后fsync/fadvise，文件保留，无全局清缓存。管理端禁止所有submit，本轮模型核提交0；worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。两项均不再阻断受控进入08，但下一窗口须新鲜身份/内核/完整BO/资源门禁并验证全范围真实消费；08尚未启动，物理峰值/加速比null。报告 `evidence/model_pl_A/20261024-step06-review-v1/REPORT.md`。下方为历史快照。


2026-10-24 A12第07步完成：l00 gate/up/down共9次真实PL调用，T8/1/1，3份权重仅加载一次、10个BO共6062080B复用。实际Y分别被GLU/残差ADD消费；同板S1/S2的10行logits、36份投影输入输出、72诊断节点和混合状态逐位一致。两worker及manager正常exit0；v2首轮扫描短暂进程变化保留，第二次完整扫描通过后自行归档租约和释放双锁，未发强制信号。独立及延时复核默认PL/GDM恢复、无ZOCL/设备用户/active lease/相关进程。第06步两项FAIL及旧单投影收口FAIL/-9保留，第08步未启动，默认FPGA未开启、加速比null。报告 `evidence/model_pl_A/20261024-step07-mlp-v1/REPORT.md`。下方内容为历史快照。


2026-10-24 A12专项收口已完成：新鲜证实旧27132仅持锁等待且无子进程/XRT/设备后，一次pidfd定向SIGKILL结束（真实-9保留）；新finalizer正常exit0，旧租约原字节归档、双锁释放，独立及延时复核默认PL/GDM正常、无设备用户/ZOCL/active lease/相关进程。新增计算/PL装卸/服务改变/重启0。单投影既有PASS保留，三个投影/08未执行；首次收口FAIL与06两项FAIL保留。新增Window v2完成7项PC恢复测试，BOARD未测。报告 `evidence/model_pl_A/20261024-step07-finalize-v1/REPORT.md`。下方STOPPED/持锁等为历史快照。

2026-10-24 A12第07步单投影：l00 gate 3次真实PL调用T8/1/1，job1/73/145，Y被GLU真实消费；同板S1/S2的10行logits、36份抽样投影、72诊断节点、混合状态逐位一致。两worker正常exit0，默认PL/GDM恢复、ZOCL无/设备FD-VMA无；最终扫描拒绝后manager27132/startticks2110722保留双锁/active lease，无受控恢复入口。本轮STOPPED，07整体未完成，三个MLP投影/08未执行；后续先安全收口管理器，不能复用旧许可。两个06历史FAIL按用户指示保留待评估。报告 `evidence/model_pl_A/20261023-step07-single-v1/REPORT.md`。以下均为历史快照。

2026-10-23 A12 第06步：真实ARM64同板S1通过（有限范围）；T8/T1 logits及混合状态逐位一致、12组抽样投影通过、自然合成输入正常EOS。HWM770636 KiB，最高33.604°C；CPU-only两窗口正常退出，独立后验默认PL/GDM保持、无设备用户/ZOCL/锁/active lease。跨PC/ARM整图FAIL保留并定位到A8边界，同输入8组独立标量参考逐位一致；首次全模型资源附加余量FAIL保留，归档缓存定向释放后v2容量观察通过，实际PL BO/address/物理峰值仍未测。PL提交0、加速比null；07未开始。详见 `evidence/model_pl_A/20261023-step06-v1/REPORT.md`；以下旧阶段状态为历史快照。

2026-10-23 A12 01—05：PC 实现与交叉构建完成，BOARD NOT_TESTED。原 A11 PASS_WITH_LIMITATIONS 保留；下文 A12 未开始等为历史快照。8 个模型图场景与原 A05 v8 对照的 logits/混合状态逐位一致，丢弃输出被拒绝；31 控制场景/764 检查、Linux/应用/窗口/包门禁通过，最终 ARM64 候选和静态包完成。完整模型 BO 140591104B 仅推导；硬件数值、物理峰值、速度仍 null。失败保留，默认配置未启用；下一步 06。报告 `evidence/model_pl_A/20261023-preboard-v1/REPORT.md`。

## A11 实板验收完成（2026-10-23）

D07/D08/D09：真实输出、分段及含搬运计时、常驻IO/权重复用与正常计算后恢复均有BOARD证据。新增已完成数值失败的正常关闭协议，未知完成/POISONED继续隔离，14引擎+11编排方法PC通过。显式charge峰值2162688B，物理峰值null；硬件整数探针、有效PL/DDR带宽、AXI/周期、p95、长稳及故意超时BOARD恢复仍未测，不用CPU或host计数顶替。2026-10-23 最新：A11 PASS_WITH_LIMITATIONS。冻结23次实际调用/5次权重加载，11形状（含真实gate/up/down T1/T8/T3）FP32输出逐字节等于独立参考，最大误差0；T1服务中位数5.109–5.268ms、T8 15.257–16.764ms，均含量化/同步/复制。worker/manager正常退出，独立后验默认PL/GDM恢复，无FD/VMA/ZOCL/锁/active lease。A12未开始；下方NOT_PASSED是历史快照。见`evidence/mlp_board_A/20261023-compute-acceptance-v1/REPORT.md`。

## A11 open阻塞修复（2026-10-23）

D07/D09：两页起分配避免本次单页绕过全局CMA落高DDR，保留每BO低2GiB/尺寸与4MiB预算检查；零计算正常返回及进程释放已板验。完整权重/23调用数值/含搬运计时/计算后恢复仍未测，物理峰值与收益null；P2不扩展。2026-10-23 最新：A11 open错误8已定位并修复。4KiB sx BO落到34507137024高地址而被低2GiB检查拒绝；私有分配对齐改8192，同诊断库单变量板测open0/close0、四IO地址合法、worker/manager正常exit0。独立后验默认PL/GDM恢复、无ZOCL/FD/VMA/持锁/active lease；0计算，A11 NOT_PASSED、A12 NOT_ELIGIBLE。以下旧状态为历史快照。证据`evidence/mlp_board_A/20261023-open-investigation-v1/REPORT.md`。

## A11 最终仅收口（2026-10-23，已完成）

D09：补齐“硬件已恢复后的资源空闲等待者交接、原租约原子归档、锁释放、工具正常退出、独立后验”协议；16方法PC与一次实际v2收口通过。v1日志基线误配保留最小复现，v2增加真实冻结81文件包/journal组合测试；不是降低内核门槛。最终无设备FD/VMA/ZOCL/锁/active lease，默认PL/GDM正常，无新增内核诊断。旧等待者专项SIGUSR1退出不是A11正常worker退出；原open错误8、诊断实板验证、数值/含搬运计时/正常计算后释放仍未完成。D07/D08无新数值/性能结论，收益null；P2大内存/长期稳定/完整模型PL/架构搜索仍未验收。证据`evidence/mlp_board_A/20261023-final-closeout-v1/`。

## A11 v3仅收尾BOARD增量（2026-10-23）

D09：v3实际通过旧等待者交接及四项默认恢复，单完整扫描门禁已能推进，无重复硬件命令；但GDM启动后的最终扫描FD表变化被归为不可续接硬停，缺少“所有动作已知完成后的仅归档/正常退出”协议。当前默认PL/GDM/资源已独立核验，8851与双锁/租约仍保留，不能标整个恢复PASS。真实停止夹具2方法确认不会被新干净扫描自动绕过；PC传输路径/可选文件错误另存最小复现并修正。D07/D08数值/时延无新增，性能收益null，P2压力/长稳/大内存仍未测。见cleanup-board-v3报告。

## A11 收尾v3电脑修复（2026-10-23）

D09：冻结真实失败轨迹已在PC复现，取消跨扫描全局PID完全相同的附加条件，保留完整设备资源门禁；增加同监督器查询/显式续接与已提交步骤记账，未知命令结果硬停止。30方法PC通过，真实WSL socket/flock及实际adapter模拟组合覆盖，但BOARD NOT_TESTED，不能称修复已在板上验证。默认恢复、open错误根因及A11数值/计时仍待；不改D07/D08数学/模型/性能，P2保持安全排除。证据`evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/`。

## A11 仅收尾增量（2026-10-23，未恢复）

D09真实信号终止后VMA从65536字节变0、ZOCL refcount从1变0，不能算正常worker退出。新增6+13方法PC与专项恢复入口；首次因消失进程扫描不完整停止，续接因两次全局进程集合相等要求未满足再次停止。全局集合稳定性/无可控续接是工具缺口；扫描无设备占用不等于默认已恢复。6174持锁，卸载/默认恢复NOT_DONE，D07/D08数值和时间仍null。需要先电脑审查边界，保留严格FD/VMA/refcount/内核门禁，不再循环创建停车进程。P2与旧证据不变。见`evidence/mlp_board_A/20261023-recovery-continuation-v1/REPORT.md`。

## A11 集成窗口增量（2026-10-23，OPEN失败、未通过）

PC补审：逐BO/逐group故障及契约失配覆盖已补，原与诊断后端各31场景返回码一致、0模拟提交，30失败诊断匹配；不等于真实XRT释放，也未证明此次错误原因。恢复仍需专项决定；无新板操作。详见`evidence/mlp_board_A/20261023-open-failure-review-v1/REPORT.md`。

- D07/D08：完成MLP overlay/位流转换、原生持久worker、分段计时和冻结23调用入口；PC真实量化11方法及控制流30场景通过，BOARD仅两组短量化通过。真实层计算提交0，数值/服务时间/加速收益仍null。
- D09：管理器10方法、进程边界19方法（含继承测试）、host6方法及启动入口6方法通过。实际错误码8后停止，不强杀；残留worker寄存器VMA/refcount1使释放门禁拒绝，默认恢复未完成。保护进程缺少可审阅的正常收尾入口，不能把保留隔离称恢复成功。
- XRT：A53派生库在实际2.18运行环境加载成功，但不等于FPGA后端open成功；本次open返回SP_DEVICE_ERROR，v1未提供具体异常阶段。独立PC派生已补打开阶段/异常详情日志，30控制场景、6定位检查及ARM64构建exit0；未部署、未重试，真实失败原因仍UNKNOWN，不改数学或覆盖已暂存包。
- 原启动/系统库哈希不变；当前irq2，本次新boot基线及实际DT兼容已核验，旧证书/pinctrl/TPM/overlay警告保留。未发现本窗口新增Oops，仍不得忽略实际资源残留。
- P2：大内存、长期稳定、硬件AXI/周期计数器和HLS架构搜索继续NOT_IMPLEMENTED，不补压力测试。瓶颈/性能优化未开始。

本窗口证据：`evidence/mlp_board_A/20261023-integration-v1/REPORT.md`。下方准备阶段缺件描述保留为历史。

## A11 最小板测准备（2026-10-23，尚未通过）

- D07/D08：真实l00 gate/up/down、捕获T1/T8及派生T3已冻结；21真实形状+2合并小例；6旧参考复用，新5组PC逐位通过。BOARD数值/计时仍null。
- D08：原A07主机计时合并copy/sync且不含最终caller复制，新增独立派生候选分段计时；完整quant-to-return服务计时仍须接入native worker。未据PC假XRT计时宣称性能。
- D09：A10父进程双锁与原A07自取锁冲突，新增只借用已持有flock的私有接口、无LOCK_UN；9项PC数据/真实锁测试通过。A11子进程边界复用A10释放检查，9方法通过；完整manager/worker联调尚未完成。
- XRT：原2.23依赖所需19符号在缓存2.18存在，A11候选用2.18头文件和库交叉构建成功；缓存库不冒充板上库，BOARD ABI/运行待测。
- 当前启动为1036而非A10验收irq2；只读停止。MLP overlay/bit.bin、同次启动DT/log核验、板上受控分配、23次实测和恢复仍缺证据。
- P2：大内存/长期稳定/新硬件计数器/HLS架构搜索 NOT_IMPLEMENTED（安全排除或本轮范围外），不计入A11最低功能通过，但P0缺项仍阻断通过。

证据与失败修复：`evidence/mlp_board_A/20261023-preparation-v1/REPORT.md`。

## A10 最小收口（2026-10-23）

D09：独立单调用worker、父进程持续租约/双锁、真实waitpid后完整FD/VMA/refcount检查，已经通过一次实板计算后卸载/默认恢复；历史仅API关闭却残留映射的失败原样保留。D11：新资源账按原始行号/SHA分开PSS/RSS、CMA和显式BO；49344字节小额包络、3地址及sync API开销实测，物理峰值/内部BO/3200MiB全模型包络null。27+7+10项PC测试、一次N32/4080保护字及独立延迟内核读回通过；15.228秒维护/最高采样32.624°C，无压力。仅记PASS_MINIMAL_WITH_LIMITATIONS，不作性能改善、零泄漏或长期稳定主张。P2长稳/最大预算/功耗/故障注入NOT_IMPLEMENTED_SAFETY_EXCLUDED；数值1000回归取消。完整差距、命令与证据`evidence/board_platform/A10_20261023_isolated_single_v1/REPORT.md`。A11/A12仍独立未验收。

## A10 v4真实空载闭环（2026-10-23）

D09/D11：有界PL前静稳和独立native子进程退出门禁现具BOARD证据；一次16.230秒，最高采样32.997°C，完整172进程释放检查/refcount0后普通卸载、默认PL/GDM恢复，延迟读回无新的未审查故障。新增13项PC host/证据测试+8计划exit0，旧81项有效证据复用；scope0计算/0显式计算BO，不能证明计算后释放。下一缺口只剩该失败场景的新进程隔离验证及最终收口；历史资源账无需重跑。告警/隐式分配/null/P2保持明确，未作性能改善结论。证据`evidence/board_platform/A10_20261023_isolated_idle_v4/`；A10 NOT_PASSED_POSTCOMPUTE_RELEASE_OPEN。

## A10 历史资源证据恢复（2026-10-23）

D09/D11：从已验历史N32记录恢复49,344字节显式BO包络、准确3地址及进程/物理内存分账，原始行号/来源SHA保留。7项PC恢复测试0，板操作0；不再为补资源字段重测。原sync区间含emit/fsync、VmHWM含先前进程活动、after_normal_release标签不等于完整释放，均明示；物理峰值/纯同步/模型峰值仍null，无性能改善结论。计算后卸载失败及新隔离空载仍OPEN，P2 NOT_IMPLEMENTED。报告`evidence/board_platform/A10_20261023_resource_recovery_v1/REPORT.md`。

## A10 收尾后电脑端联调（2026-10-23）

D09/D11：补此前mock过多遗漏的实际日志/锁/子进程退出到恢复编排，新增8项、相关81项PC通过；首轮夹具排序失配保留并修正，生产门禁未放宽。静稳修复已封入v4、未上板，无新板端授权或动作。BOARD空载/计算后释放及原系统返回仍待，A10未通过；无性能指标改善主张，P2 NOT_IMPLEMENTED。详见`evidence/board_platform/A10_20261023_controller_integration_pc_v1/REPORT.md`；下方“未打包”为原窗口历史。

## A10 本轮收尾（2026-10-23）

D09/D11：irq2实启动确认；PS显示误分类/日志字段冲突已修，GDM停止后的proc竞争在PL前安全阻断。用户另批仅收尾后终止无设备的等待者、恢复GDM/租约，独立核验通过。本轮驱动/PL/XRT/计算0；最新有界pre-PL静稳修复73项Linux PC通过，未部署。A10未通过，空载/计算后释放仍待；内核启动警告和软件reboot问题保留，无性能改善结论，BO/模型PSS/同步null，P2未实施。详见最新交接及`evidence/board_platform/A10_20261023_isolated_idle_v1/FINAL_REPORT.md`，下方为较早快照。

## A10 独立空载工作进程与完整控制器（2026-10-23，接续）

D09/D11：已补无BO/RunStart分支的native worker、管理方持续双锁/租约、GDM隔离、真实子进程退出和完整fd/VMA/refcount/连续内核门禁接入；PC完整编排及拒绝路径通过。真实Linux测试发现扫描器自己的临时fd导致错误不完整判定，修复为在scandir存活期间读链接，其他权限/竞争仍拒绝。Linux62方法通过；Windows50过/4 POSIX跳过，8项最小门禁在Linux运行。新的空载包已逐项哈希暂存，正常1036关机已读到Power down，获准一次人工冷启动irq2，实板空载验证尚待。计算后释放仍OPEN，A10不因PC或空载准备通过；无性能变化结论，P2 NOT_IMPLEMENTED，取消长回归不变。见 `docs/handoffs/A_A10_ISOLATED_IDLE_20261023.md`。

## A10 原始材料补齐与PC释放边界（2026-10-23，覆盖下节初次缺件）

D09/D11：已接收并核验130文件及实际执行器；唯一N32/空载/冷恢复从REPORT_ONLY升级为原始证据审阅通过，计算后卸载仍FAILED。实际同一管理进程保留XRT VMA的编排缺口已定位。新PC组件实现独立子进程退出、同窗口身份、保留管理方双锁、不强杀/重试及完整fd/VMA/refcount/内核拒绝门禁；真实失败VMA快照与Linux子进程/锁检查覆盖，相关44方法退出0。未接入完整native worker/新窗口控制器，未部署或板测，不将PC通过充当实板修复；任意设备别名和跨机不合作消费者不能由一次proc快照解决。只读登录浏览获得1036当前观察，无新PL或计算。指标无新增测量，P2 NOT_IMPLEMENTED，长回归取消不变。证据与未决项见 `docs/handoffs/A_A10_PEER_INTAKE_20261023.md`。

## A10 外部交接后的差距（2026-10-23，报告接收）

D09/D11：报告称一次 N32 和空载生命周期已通过，但计算后残留64KiB设备VMA，卸载及延迟OF清理失败；需实际执行器的独立工作进程退出边界与完整fd/VMA/refcount/内核门禁。对方已有PC版释放门禁，文件尚未收到，不重造替代驱动、不重跑正确计算。本机只有两份报告，原始输出/新驱动/源码/1036恢复基线缺失；BOARD结果暂为REPORT_ONLY，A10 NOT_PASSED。新增接收收据与缺件清单，PC旧/新契约0，无板动作与性能变化。P2优化NOT_IMPLEMENTED，压力/极限/故障注入SAFETY_EXCLUDED；详见 `docs/handoffs/A_A10_PEER_INTAKE_20261023.md`。下文“最新”均为其历史窗口。

## A10最大精简后的真实阻断（2026-10-21，最新）

D09/D11已减为一次32元素及空载生命周期；新日志分类仅接受按操作精确核实的提示，实际32路DT与源码解释IRQ index32。空载卸载出现真实SLUB BUG，候选内核路径重复释放`intc->data`；保护生效，未算、未继续恢复，A10 NOT_PASSED。电脑派生补丁清空拥有指针，ASan原失败/新通过、ARM64单元编译通过；不是完整FIT或板验证。最高观测33.401°C，BO/sync/PSS均null，无性能改善结论。P2压力/极限/长稳/故障注入NOT_IMPLEMENTED/SAFETY_EXCLUDED；1000次数值回归仍取消。见`evidence/board_platform/A10_20261018_intake/MINIMAL_A10_20261021.md`。本次Oops启动及原候选禁止继续测试。

## A10候选维护实际结果（2026-10-21）

D09/D11：获准同候选启动与默认配置正常恢复有BOARD证据，但新增日志门禁停在外部模块标记，测试位流从未加载，IRQ修复不能记板测通过。修复日志raw选项/字节保持，补真实SHA、固定boot/目标路径与仅收尾入口；37+5相关Linux方法和4上传方法通过。默认恢复2条非overlay节点属性生命周期告警仍OPEN；旧X509/固件pinctrl限制保留。新profile与物理账真实更新，PSS/RSS/BO地址/峰值/sync均null，不把3200MiB规划或电脑内存当实测。无性能改善结论，P2优化/极限探测/压力NOT_IMPLEMENTED；数值回归CANCELLED_BY_USER。证据`evidence/board_platform/A10_20261018_intake/IDLE_MAINTENANCE_20261021.md`。下一步电脑区分精确预期诊断与真实引用错误，不关闭/泛化豁免门禁。

## A10候选空载执行入口（2026-10-21，仅PC）

D09/D11新增与已启动候选准确匹配的空载入口及不可覆盖包，补新boot/逐项原始日志审阅、精确命令允许列表和候选父子绑定检查。14新方法/34Linux相关方法通过；Python缓存清单错误复现并修复。没有BOARD增量或性能改善；原X509/固件/overlay告警仍OPEN，无真实基线豁免，新IRQ生命周期/最小PL/BO待测。P2优化/压力/极限分配未实施。见`evidence/board_platform/A10_20261018_intake/CANDIDATE_IDLE_PREPARATION_20261021.md`。

## A10候选已启动与原默认返回（2026-10-20）

D09/D11的独立候选与可恢复路径取得BOARD证据：原模块树备份、6231文件实际暂存回读、U-Boot三个SHA256校验、候选ARM64登录；用户重新上电后原默认系统返回且原哈希不变。并非故障自动回滚或新IRQ修复已验收。当前完整候选历史日志已补回，X509信任链/固件pinctrl/默认overlay警告保留；新PL生命周期和最小真实计算/BO双账仍未测。路径/健康日志频率/旧UBoot格式/日志压缩采集工具补测试，最高暂存温度36.432°C，无性能改善结论。P2优化、压力、极限分配和在途故障注入不实施。报告`CANDIDATE_BOOT_AND_RETURN_20261020.md`。

## A10完整配套电脑候选（2026-10-19，板OFF）

D09/D11差距继续收敛：完整独立内核、修复IRQ生命周期的新ZOCL及238CRC、6218模块/6127签名审计、保留原DT/启动用户空间的FIT和独立回读已通过PC检查。未把构建成功当BOARD验收；暂存make0但漏签名与缺dtc失败均保留并修复。新增6模块门禁/8归档方法及136驱动stub检查/同套san有证据。取消的数值回归保持取消。仍缺实际启动/返回原系统、无新增IRQ错误的正常PL恢复、一次最小I/O与BO双账；板子关机，不读旧温度作当前值。P2性能优化/压力/活动DMA故障注入未做。详见本轮 `DRIVER_AND_BOOT_CANDIDATE_PC_REPORT.md`。

## A10启动备份及配套构建（2026-10-19）

原FIT/脚本已真正备份并核SHA/CRC，原内核组件和KV260 revB选择逻辑已确认；此前“脚本未获得”缺件说明更正，旧失败保留。NetworkManager内存连接经Unsaved=true验证，电脑VPN/永久配置未动。完整内核电脑构建仍运行，新版模块/ZOCL/initramfs/FIT与实际一次性启动/回退未就绪，原件备份不等于恢复通过。另发现固定XRT中断管理调用处于irqsave自旋锁区的静态风险，三文件内核补丁不覆盖它；需电脑评审处理，不在板上危险复现。最小真实通路/小BO同步/干净恢复仍未通过，数值回归保持取消，P2压力/优化不实施。见 `evidence/board_platform/A10_20261018_intake/KERNEL_FULL_PREPARATION_REPORT.md`，无板性能改善声明。

## A10内核修复候选（2026-10-19，PC）

已实现三个精确源文件的OF/experimental parent引用修复与固定IRQ卸载遍历界；候选304 stub断言及同套sanitizers、4生成器测试、正反patch/SHA和3个ARM64翻译单元通过。无板连接或指标改善声明，完整内核/模块/FIT及回退备份/启动路径未就绪；并发IRQ与在途DMA恢复未证明。原板缺陷未关闭，不能靠降低日志门禁通过。数值回归取消；P2性能/压力/极限探测不实施。报告 `evidence/board_platform/A10_20261018_intake/KERNEL_REPAIR_PC_REPORT.md`。

## A10安全修订与内核阻断定位（2026-10-19）

用户取消20长度/1000及重复数值回归，见 `docs/A10_ACCEPTANCE_SAFE_20261019.md`；不再列必需缺口。新增PC日志门禁接入每步状态变更前后，错误/告警/断档失败即锁住后续动作；28相关测试通过，尚未部署。精确Ubuntu源码显示extended IRQ引用与可变mapcount卸载循环两条风险；只读板配置确认experimental路径启用。源码模型不是实板修复或唯一动态根因证明，不重新加载试错。资源物理账与进程账已分别整理，未测BO/PSS/峰值保持null，3200MiB未验证。一次最小通路/小BO同步/干净恢复仍阻断，P2压力/故障注入不做。报告 `evidence/board_platform/A10_20261018_intake/SAFE_ACCEPTANCE_PROGRESS.md`；下文旧门槛和待补门禁保留为历史。

## A10收尾后的新增缺口（2026-10-19）

默认恢复/模块节点消失已真读回，但完整日志事后出现IRQ控制器设备树节点引用计数1/65不平衡错误。执行器未在每步对新增内核消息设诊断门禁，不能把流程exit0当无异常恢复；归档原始日志，保留未决，不反复装卸定位。下一步先PC查引用路径和补门禁，A10实际计算仍0。报告 `evidence/board_platform/A10_20261018_intake/IDLE_CLEANUP_REPORT.md`。P2长测不做。

## A10空载加载与检查缺陷（2026-10-19）

单次专项授权下已真加载测试PL并出现ZOCL节点，但检查器漏建中断子设备模型而停止；电脑修复核验父子路径与具体驱动，保留原失败，不重新加载。默认恢复尚未执行，保留中央租约，先申请仅收尾；没有计算BO/核执行。IRQ枚举终止和overlay警告保留，不作IRQ功能/无泄漏结论。累计20长度/1000规则已PC夹具测试，真实计数0、BOARD时延/预算null。P2长测/性能优化仍不实施。报告 `evidence/board_platform/A10_20261018_intake/IDLE_TRIAL_REPORT.md`。

## A10配置恢复判定（2026-10-19）

实际板库反汇编证实卸载exit0不能证明overlay删除，新增独立节点/绑定/引用/持有者读回判定及4 PC测试；该判定尚未接入已部署执行器。v4主机补生产初始化取消/健康/10s软限与trace，72+同72san+4信号、A53编译通过，不能强停挂起ioctl，v4板测未做。准备仅bit/dtbo/shell的空载候选，中央租约和逐步读回为执行前门禁；待一次空载配置授权，不含计算。异常DMA停止仍未证实，不把空载卸载当故障恢复。证据`evidence/board_platform/A10_20261018_intake/PL_IDLE_PREPARATION_REPORT.md`。P2长测/性能/极限内存不做，无收益结论。

## A10授权链接/网络增量（2026-10-19）

已补真实A53单次链接检查（0.03148s、exit0，不打开设备）及可撤销临时直连IP/固定主机公钥SSH；未改系统库或持久网络。只读平台清单0.11435s确认默认overlay/恢复文件存在，但尚非恢复成功。XRT文本/符号/重定位等节相同；rodata仍不一致，完整组合待验。新增5项PC摘要拒绝测试，复用9 ELF、4传输、22动作计划。P0/P1剩余精确PL恢复、初始化取消审查、最小PL授权、20长度1000真比较与BO边界/同步；PL/BO未测，计数0。P2持久自动部署/吞吐优化/极限探测未实施，不加板上负载；没有性能提升声明。证据`evidence/board_platform/A10_20261018_intake/LINKAGE_NETWORK_REPORT.md`，原失败不改写。

## A10接续：身份与短测所有权（2026-10-18）

新增PC独立FRU身份区/有界扩展链审计及10测试，保留137/122偏移坏链；暂停前FIT内核与安装文件摘要一致。短vadd候选已实现提交前在途标志、异常保留BO、不消费错误输出、中央租约/哈希/健康门禁、小批次休息；60控制+同60san+4信号与A53链接证据复用，不重新构建。仍缺实际运行库构建/ABI闭环、完整初始化取消/恢复审查及真板ARM/PL/BO/vadd/恢复；不得把保留BO视为PL停止。本次重接未收到shell，当前健康未知，只读动作未执行。报告`evidence/board_platform/A10_20261018_intake/RESUME_AND_SHORT_HOST_REPORT.md`。P2自动部署/持久安装/吞吐优化未实施，无性能收益值；FRU坏链不自动授权EEPROM修写。

## A10 D09/D11短时驱动增量（2026-10-18）

已实现并真板核验：固定SHA暂存、9类绑定/引用者/安全策略门禁、一次无绑定模块加载及普通卸载、原始taint与离散温度/内存分账；未加载PL或运行计算。传输CR边界失败修复并保留最小复现；PC短验收补hwmon和无效温度失败关闭，17方法PASS，旧发布包不改。证据`evidence/board_platform/A10_20261018_intake/DRIVER_BOARD_CHECK_REPORT.md`及15份源SHA摘要。

P0/P1仍缺：FRU校验错误/启动FIT和固件API对应性、2.18板运行时与2026.1产物配套、PL恢复方案与专项授权、旧vadd超时活动BO隔离、实际ARM/BO/vector-add/恢复。A10 NOT_PASSED，3200MiB包络未证实，不把CMA与PSS/BO重复累计。P2：联网自动部署/持久驱动/吞吐优化/极限探测NOT_IMPLEMENTED或NOT_TESTED，无性能收益声明。

## A07 D09/D11正式收口（2026-10-04，当前）

- 已完成保留：A06冻结B核、A04/A05模型与独立数学、原S1 Cortex-A53 136单元/依赖证据；未重做模型和语音。
- 必须补实现，已补：生产六函数C ABI控制路径、生命周期/POISONED资源隔离和负路径测试接缝，替身不参与生产构建；可搬移源码与准确依赖/来源清单。
- 必要补测，已完成：29控制场景554检查与相同san；970主机规则、66meta/396篡改/4build和san；真实ARM库/host重建、B原preflight、干净包复现和1101文件SHA检查。
- 必须补构建，已完成：实际v++ target hw约150MHz链接/布局布线，WNS+0.809ns/WHS+0.010ns，0未约束/布线错误，CDC safely timed；DRC93 DSP警告/18 advisory及2平台clock advisory明示、不改severity。
- 后续板端：启动/DT/固件/内核/XRT组合、CMA/BO窗口预算、设备身份/恢复、A12模型PL消费；全部NOT_TESTED/null，不是A07无板失败。
- P2 NOT_IMPLEMENTED：更多DSP流水/并行、arena/异步预取、固定MAC Linux迁移，不计性能收益。

交付`release/a07_b04_v3`；报告`evidence/A07_closeout/20261004-v1/REPORT.md`。A07离线PASS，B04联合签核和BOARD不推定通过。历史条目保留。

## A06最终接收（2026-10-04，覆盖下方历史阻断）

唯一剩余必要补测已完成：当前e227297 double实际Linux Vitis Csim exit0，61例/2800022检查，原A04参考/配置/数学/容差未变。已核验原源/XO/XML/必需Cosim与严格382向量，A06离线接收PASS并按hash冻结。未重跑已有效的模型、语音、长测或优化搜索。

P2仍为波形浏览与内部FIFO测量；A07真实平台链接/实现、控制层失败修复、KV260启动/BO/BOARD属于后续，绝不由A06推断通过。许可证仅本次Host ID匹配且实际Csim可用，不保证WSL重启后MAC固定。证据`evidence/A06_acceptance/final-20261004-v1/`。

## A06 A接手收口（2026-10-03，当前覆盖下节反馈待办）

- 必须补实现，已补：A所有的两个JSON序列化派生补丁及清洁接收入口，源hash锁定，不改B核/原向量；382文件逐字节复现，不再需要B修工具。
- 必要补测，已补：严格全包重建、PC50/真实权重4、归档RTL66重放；正反向byte guard在Windows/Linux各3方法，归档11方法通过；A07实际接口说明完整。
- 必要补测，仍阻断：当前源码A本地Vitis Csim。Linux官方许可绑定与当前Host ID不符；Windows2026.1备选实际K26 part检查exit1。不能用PC/B报告替代用户指定的本地Csim。
- 已完成保留：A04独立PC61/2800022、新版来源/17参数/XO/270TV/两shape T1..8与T1/T8 Cosim、资源/II/背压核验。旧0.5B和fdd1通过不转移给新源。
- P2与后续：WDB波形浏览、内部AXI FIFO占用剖析为P2；实现时序/平台配套、BO可达/BOARD另阶段，数值保持null。本轮不以优化建议冒充实施。

证据`evidence/A06_acceptance/a-owned-closeout-v1/`。A已接手剩余维护，不给B新增待办；账号许可仍需用户官方操作。

## A06 D07/D08 补交复核（2026-10-03，当前）

已完成：实际double源码/XO/内嵌XML与17参数、同版来源、270TV/66RTL独立回放；新核A04 PC61、真实shape T1..8、参考INT32/FP32与负例；HLS资源/II/缓存和背压原始证据分域记录。实际内嵌XML与外置序列化hash分账；B组双缓存4352B与119KiB整tile理论值区分。

必要补测：新版本地Csim因当前WSL HOSTID失配未执行，旧版PASS不继承；待官方许可可用再只补该项。接收暂不冻结。B严格Linux清洁自测42份JSON CRLF/LF导致exit1，属于工具可移植性反馈，二进制数值已闭环。5WDB缺、stall_max_k原流程失败/postcheck恢复、内部AXI FIFO峰值未测皆明示，不自动要求所有优化重跑。

P2可选：额外FIFO内部信号剖析与完整波形浏览；实现收敛/BO预算/BOARD属于后续阶段不是已完成值。旧下表“没收到XO/TV”仅为历史。本轮不改A07—A09成果，证据`evidence/A06_acceptance/supplement-v1/`。

## A09 D00/D12/D13（2026-10-03，最新增量）

详见`eval/qwen35/a09/DESIGN_GAP.md`。清洁目录构建/权重复现/离线Python依赖、A08定向修复与小样、部署准备/论文NA模板已实施；不恢复200/两小时。匹配启动链、A06/A07最终核和链接、BO执行入口、系统/ARM语音安装闭包仍缺；新确认UI真人实操未测。默认CPU不受缺B/C阻断，A09整体PARTIAL，BOARD为null/NOT_TESTED。

## A07 D09/D11独立准备（2026-10-03，最新增量）

| 分类 | 当前实际完成 | 仍待工作 |
|---|---|---|
| 已完成保留 | A05 CPU入口/模型/72矩阵/契约；旧核本地Csim补测已通过 | 不重做旧有效数据，不转移给新B核 |
| 必须补实现，已补候选 | 六函数XRT、持久对象/权重BO/池、参数/meta/BO窗口、POISONED保留资源、拒绝未验收核 | 最终XO ABI、实际板行为、A12模型接入未验证 |
| 只需补测，已补PC | 969主机断言+相同sanitizer、8归档安全方法 | 不是XRT/PL模拟成功 |
| 必须补构建，已补 | Cortex-A53完整S1及XRT候选交叉链接；136单元和10库一致性 | 真实v++核链接/实现、ARM执行仍待 |
| 必须补交/实测 | B实际ZIP/XO/原始证据、匹配启动链、DT/CMA/BO预算/恢复 | 保持A06/A07未通过与null预算；不拼启动包 |
| P2可选 | arena、异步预取、更多并发与吞吐优化 | 不以建议冒充实现或收益 |

完整报告`evidence/A07_independent/preboard-v1/REPORT.md`。下方A06中“许可证阻断”是首次记录，已由许可恢复报告解除；新候选版本仍须自身证据。

## A06 D07/D08 接收验收（2026-10-03，当前）

| 分类 | 实施与证据 | 尚缺或边界 |
|---|---|---|
| 已完成保留 | A04独立参考/72矩阵manifest及本次4权重文件、A05交接等11项身份一致 | 不重复导出、不改完整模型 |
| 必须补实现，已补 | A自有只读下载/哈希审计、参数映射、独立接收testbench | 不另写HLS核，不执行B自测脚本覆盖原包 |
| 必须补测，PC已补 | baseline/reuse/double每版61例，含两真实尺寸T1..8、INT32/FP32顺序、尾部/错误 | A本地Csim被官方许可证Host ID变化阻断；PC不是Csim |
| 必须补交付，未闭环 | 唯一版本、实际XO/内嵌XML、同版构建/testbench证明、原始输入及RTL输出 | B报告未代替实物；不冻结核、不签通过 |
| 只需补证/补测 | baseline已有34笔分组RTL记录，但每组27项tv缺失；reuse/double RTL未完成 | 只要求B最终选定方案闭环，不重跑全部优化搜索 |
| 机制审阅完成 | baseline无跨T权重复用；reuse跨T顺序复用；double双2176B槽且load/compute DATAFLOW | P_N/P_K/P_T=32/1/1，不把复用当T倍算力；FIFO占用/随机背压未验证 |
| 必需后续阶段 | A07由A做XRT/同步/meta/隔离；A11板测，A12消费PL结果 | CMA/BO预算/硬件误差null，BOARD NOT_TESTED |
| P2可选 | 更大P_K/P_T、完整down双tile缓冲、200MHz | 未实施不计收益；不要求B改架构 |

2176B/group与down完整tile双缓冲121856B≈119KiB推导保留；B double实际缓存两个group共4352B，不是119KiB全tile缓存。BRAM18K/36K口径、AXI逻辑字节/实测总线字节分开，见A06报告。

## A05续作收口 D04/D05/D06/D09（2026-10-02，当前）

状态 `PASS_PC_A05_FULL_MODEL_PHYSICAL_T8`；证据 `eval/qwen35/a05/batch-fix-v1/REPORT.json`。

| 分类 | 实际变化与测试 | 边界 |
|---|---|---|
| 已完成保留 | 开工12523项旧seal全部匹配；模型/72 sidecar/CPU算子库原样保留 | 103 ABI、48 SIMD有效证据不重做 |
| 必须补实现，已补 | 非MLP投影固定逐token SIMD GEMV；仅CPU FlashAttention固定归约路径 | 真实MLP T2/4/8；不改精度、GDN公式或公共数学 |
| 必须修复，已补 | 零输出位置保持上游空张量语义；v6崩溃最小复现保留 | final-logits正常模式通过，不强开all绕过 |
| 必须补测，已补 | 最终v8的72投影、23位置logits、48状态数组、scalar/optimized逐位；17状态+74补充检查 | 含原失败1025token、真实物理T与尾块；不靠文字相似 |
| 只需复测，已补 | dev24/80断言、17MODEL+7策略模板；两条断网合成音频 | 医学审核/最终300题/声学/BOARD不混入通过 |
| P2可选 | R1/R2、更多吞吐优化 | 未实施、不计收益；默认R0 |

历史数值越限、节点诊断中不同前缀状态不可比的说明、v7长KV失败均保留；根因与修复前后指标见新报告。下方A05 PARTIAL为首次实施历史。

## A05 D04/D05/D06/D09（2026-10-02，首次实施历史）

| 分类 | 实施/证据 | 状态边界 |
|---|---|---|
| 已完成保留 | A04 1603项先核验；72 sidecar、A01库/模型不重导不替换；共享文件before留档 | 旧证据不冒认本阶段通过 |
| 必须补实现，已补 | SP_LINEAR CPU、执行期CUSTOM节点、72权重、A8共享/失效、严格FP32 | 无FPGA/逐矩阵Python IPC |
| 只需补测，已补 | 103 ABI、48真实SIMD投影、scalar/optimized全图、取消/会话/内存/dev/语音 | PC限定范围通过 |
| 必须补实现，已补 | R0清空重算且响应前清空；GGUF目标页保护/RSS0；weight_load_count72 | 启动峰值仍计入，BO预算null |
| **必须修复，尚未闭环** | 物理T1/2/4/8/整段等价性：原物理批越限，F16诊断仍T1越限 | **A05 PARTIAL**；canonical物理T1不替代物理T8验收 |
| 保守规则反例，已修 | 2条完整关系表达；36旧单测+3新方法；dev回退2/17→0/17 | 不改真值/数字/否定/额外事实检查 |
| P2可选 | R1快照、更多吞吐优化 | 建议不计实现；R1禁用 |

证据：`eval/qwen35/a05/REPORT.md`、`state-v1/v2/numerics.json`、`quality-v1/quality.json`、`app-dev-v3/S1-summary.json`、`voice-s1-v1/summary.json`。量化差异非零；医学/300题/声学/BOARD不降为P2。以下A04“A05待做”为历史。

## A04 D06/D08（2026-10-02，当前）

| 类别 | 实施与验证 | 尚未声称的结果 |
|---|---|---|
| 已完成保留 | A01原始BF16/revision/72映射与旧运行库、A03有效代码/失败/音频证据；开始核验292项历史seal | 不重做迁移、工具安装或录音 |
| 必须补实现，已完成 | 新`quant/export_w4a8`、只读加载器、独立Python标量和C++标量/32lane优化路径 | 不是SP_LINEAR ABI或全图S1 |
| 必须补测，已完成 | 手算、ties-even、跨组、K129/N33/T1..8、subnormal/NaN/保留码/长度/溢出/FP32顺序；210断言和同套消毒器 | 不把重复运行计为420独立用例 |
| 必须补测，已完成 | 72矩阵两次可复现导出+C++独立重导；0/3/4/23层48个真实投影、CPU同数学逐位一致 | 不把CPP参考0误差写成W4A8相对原模型0误差 |
| 必须补清单，已完成 | 每张量方向/源和输出hash，理论及实际140378112字节，内存实测，H0/S0/局部S1/S2分账 | S2无板误差null，实际BO预算null |
| 后续必做A05 | SP_LINEAR调用入口、图接入与完整S0/S1 logits/任务质量；避免两套完整模型常驻 | 本阶段只完成可重用C++参考/优化内核 |
| P2可选 | 更强SIMD/多线程、敏感层高精度、校准、混合格式 | 均未实施、无hash/收益，不悄悄改冻结格式或容差 |

质量定位：固定样例W4-only最大NRMSE16.20%、A8-only6.77%；非普适质量结论，不能据此宣布最终问答通过。详见`eval/qwen35/a04/REPORT.md`。下方“A04未开始”为历史快照。

## A03收口增量（2026-10-02，历史）

唯一阶段文件现为增强包`03_A_系统实现与验证_阶段提示词_措辞精简版.md`。下方原A03“未录音/待授权”是历史，现由`eval/qwen35/a03/closeout-v1/REPORT.md`覆盖其当前状态，原证据不改。

| 类别 | 核验结果/安排 |
|---|---|
| 已完成保留 | 真实持久语音、能力/路径/队列/epoch、事实检查后TTS、断网WAV冷启动、端点三阈值对比及失败保存 |
| 只需补测，已补 | 录音就绪修复62项测试；授权首轮否定/数字转录；第四轮单问句经真实Qwen/检查/TTS播放，用户确认清晰 |
| 必须补的当前证据整理，已补 | 旧seal与当前源码对应核验、原始wire/结果核对、当前README/manifest/状态纠偏、新报告及哈希；没有未决A03功能补测 |
| 后续必做而非A03重复门槛 | A08长测/请求与spool维护/音频设备阻塞故障；最终独立语音和医学质量；A13/A15声学计时，均未验收 |
| 补充验证 | 隔离外网与真人麦克风冷启动组合尚未测；A03条文WAV/麦克风路径已有分开的真实覆盖，不要求再次录音才能做A04 |
| P2可选优化 | 自动端点替代PTT、流式TTS/重叠、更复杂去噪/热词；未实现不计收益 |

声学计时对正式性能验收是后续必需证据，不一概降为P2。当前仅声学回采的具体实现方式可另选。A04前置通过、实现未开始；原0.5B激活不是本次输入验证。

_成员 A · 2026-10-02 · 按真实证据接续，不重做 A00_

---

## 📍 当前定位

2026-10-02 A03增量：`PARTIAL_PC_SYNTHETIC_LOOP_PASS_PENDING_MIC_AND_HUMAN_LISTEN`。以下A02/A01均为保留历史，不覆盖已有效证据。新增报告`eval/qwen35/a03/REPORT.json`。

| A03 D02/D10差距 | 分类与当前结果 | 证据/限制 |
|---|---|---|
| 持久ASR/TTS、JSONL隔离、能力检测 | 必须补实现P0，已补并实测 | 真模型32项协议检查，SP_VOICE_V1字节不变 |
| 200ms流块/ack清理/配额 | 必须补实现P1，已补 | 单并发、4作业、64MiB/512文件、有序ack；部分转录不评分 |
| 半双工/epoch/未播不提交 | 必须补实现P0，已补 | 实际取消播放，已播历史0；软件drain与声学实测分开 |
| 首句事实检查后TTS | 只需接入补测，已补 | 4轮中2模型、1ASR澄清、1检查器拒绝后模板；无隐藏回退 |
| 600/900/1200ms端点比较 | 只需补测，已测发现不足 | 构造停顿均丢后半句；PTT保留，不删失败样本 |
| ready/提交/真实出声分离 | 必须补字段，已补 | ready约15.344s；声学首次有效声音null，无回采不报PASS |
| 许可/版本/依赖固定 | 必须补审计，已补来源 | 非商业限制和禁止权重自动发布；不替代法律审核 |
| 实际麦克风/中文可懂度 | 人工前置+只需补测，未完成 | 授权未答复，未打开麦克风，听辨表待填 |
| null置信度真实转录确认 | 必须补交互流程，已实现并单测 | 原句YES确认入口；未实际录音使用。合成fixture确认不适用于真人，评分仍待审核 |

P2可选：自动VAD/更好端点、流式TTS、设备专用回采。未实现不计收益；当前并未通过改语速、删静音或漏播改善指标。

2026-10-02 A02增量已实施，当前工程验收为`PASS_PC_ENGINEERING_DRAFTS_REVIEW_PENDING`，不覆盖下方A01历史。当前结果与真实命令见`eval/qwen35/a02/REPORT.json`；原版本快照在`eval/qwen35/a02/before/`。

| A02 D02/D03差距 | 分类 | 实际处理与证据 |
|---|---|---|
| 病例/状态/检索/检查/评分混合 | 必须补实现 P0，已补 | A自有domain/planning/checking/scoring/session；旧应用只读 |
| AnswerPlan与缺失≠否定 | 必须补实现 P0，已补 | allowed/required/unknown/已确认历史；规则和真实CPU测试 |
| 规则路由与歧义澄清 | 必须补实现 P1，已补 | 一轮最多一次LLM；DEV-010过度路由修复和标签erratum单独留档 |
| 数值/单位/否定/关系/漏答检查 | 必须补实现 P0，已补 | 整句有限语法、uncertain保守处理、负例单测；不宣称开放语义正确率 |
| 原句证据和确定性评分 | 必须补实现 P0，已补 | span/原始时间/否定/低置信度审核；仅话题覆盖，不评人格和真实情绪 |
| 短答与回退警戒 | 只需补测并按失败修复，已补 | 三轮开发结果64.7%→35.3%→0%，门槛始终10%；最后回归另存 |
| 300条独立最终集 | 计划已交，真实编写未完成 | 300项source隔离任务冻结，0题已编写；不宣称300条通过 |
| 病例/未知策略/评分医学真值 | 人工前置，尚未审核 | teacher_review.csv空白，软件演示模式以外禁用 |
| 真实播放、流式打断、ASR错误率 | 后续A03，NOT_TESTED | PC_TEXT_TEST_ACK不等于音频已播；同步阶段并发修改明确拒绝 |

P2可选项：更多经教师审阅的自然表达、统计路由/意图模型、流式逐句生成。当前没有实现，不据此声称收益；不得用最终集调试。首轮/第二轮失败、原始候选和所有模板回退保留。

历史 A00 通过；A01 原文本基线通过并保留。本轮已补齐 A01 新增设计证据，PC 通过。下一阶段 A02；不把旧 RA03 缺 B/C 包视作新版默认系统阻断。结果见 `eval/qwen35/design_import/REPORT.json`。

唯一阶段依据：增强包 `03_A_系统实现与验证_阶段提示词.md`，版本 A-DESIGN-1.0；补充依据：13 首次导入、12 D00/D01/D04/D05/D11/D14。原任务包与 archive 仅留档。

已读取当前状态、A01 原始 PC 日志、最近历史交接、原生入口、固定 llama.cpp 的 batch/graph/memory 实现；没有扫描 B/C 工作区。

## ✅ 已完成并保留

| 项目 | 优先级 | 真实证据 | 边界 |
|---|---|---|---|
| A00 迁移、配置、所有权 | P0 | `platform/qwen35/a00/` | 不重复迁移/安装 |
| revision/许可/模板、72 MLP 映射 | P0 | `models/model.lock.json`、`quant/qwen35_tensor_map.json` | 新 0.8B，不用旧 0.5B 替代 |
| F16 / Q4_K_M CPU 生成 | P0 | `eval/qwen35/a01/A01_REPORT.json` | 非自定义 W4A8 |
| 256/1024/2048、取消、reset、全状态重算 | P0 | A01 两种精度的原始 JSONL | 小规模 PC 功能证据 |
| 契约/fixtures 与增强包一致 | P0 | `eval/qwen35/design_import/intake.json` | 未改公共 ABI，不代 B/C 签名 |
| 目标和实际值分离、预算推导 | P0 | `design/qwen35/` | DERIVED_NOT_MEASURED；BOARD=null |

导入前核验 A01 原摘要内所有文件哈希；小范围修改前副本存于 `eval/qwen35/design_import/before/`。原日志、模型、旧可执行文件不覆盖。

## 🔧 当前 A01 增量

| 差距 | 原分类 | 处理 | 验收 |
|---|---|---|---|
| 输出头与各层分项证据 | 必须补实现 P1 | 增加可关闭的逐节点 CPU 诊断；与正常执行分离 | 两种精度 PC PASS |
| 只取整段所需 logits | 必须补实现 P1 | final 默认、legacy_chunk_last 对照、all 有界诊断 | 两种精度 PC PASS |
| 混合状态实际分配 | 只需补测 P0 | 核查 allocator 日志、明确 1 slot / 0 快照 / R0 | 日志及查询一致 |
| 新需求下 reset/cancel 一致性 | 只需补测 P0 | 复用原集，在新独立构建重跑 | 两种精度 PC PASS |
| MAC/存储/状态下界 | 只需补测 P1 | 原包工具读取锁定的真实 config，T1/T8 | 已生成，非性能实测 |

旧实现每 256-token 块输出末位置，并非每个输入 token 都输出全词表。final 改为整段仅最后位置；零输出中间块仍必须更新完整混合状态。all 仅诊断，限制提示不超过 256 token，不用于常规服务。

256/1024/2048 输入的旧分块与 final 最后位置 logits 在两种精度下均逐位一致；all 模式对照最终位置全词表，F16 最大绝对误差约 4.05e-6，Q4_K_M 约 2.86e-6。预设 `atol=0.002, rtol=0.0002` 仅用于不同 GEMM/GEMV 诊断，不改变 W4A8 契约容差。1024 输入的实际后端 trace 仅产生一个输出位置。

测试容量 4096 的真实日志：KV 48 MiB，卷积/递归状态合计约 19.27 MiB，0 rollback snapshot；设计的 KV 24 MiB 是 2048 容量推导。Q4 CPU 另有约 209 MiB REPACK 分配，未隐藏在模型文件大小里。板端物理归属仍待测。

Windows 首次单测因默认 GBK 解码中文 intake 失败，已显式 UTF-8 修复；原失败保留，6 项复测通过。新增诊断样本不构成正式性能、医学质量或量化质量验收。

## 📋 后续必须实现

| 阶段 | 优先级 | 缺口 | 模块边界 |
|---|---|---|---|
| A02 | P0 | AnswerPlan、事实权限/未知语义、输出校验、病例与评分测试、教师审核 | `system_qwen35/`；不改 C 旧 cases |
| A03 | P0 | 持久离线语音、完整首句、epoch 取消、端点与实际播放边界 | `modules/voice_A/`；SP_VOICE_V1 |
| A04–A05 | P0 | 自定义 W4A8、独立参考、完整图和混合状态正确性 | A 默认实现；保留 SP_LINEAR_V1 |
| A06–A07 | P0/P1 | 默认 HLS、仿真、离线链接、ARM64、BO 驻留与 T≤8 复用 | `modules/linear_A/`；非旧 vadd 成果 |
| A08–A09 | P0/P1 | 统一 trace、线程预算、200 轮闭环、干净复现 | 应用调度与证据编排 |
| A10–A17 实板部分 | P0 | 启动配套、真实内存/BO、声学延迟/能量/稳定性/恢复 | 无板全部 NOT_TESTED |

运行时只负责模型与状态；病例层负责事实权限、检查与评分；语音只接受批准音频/已验证文本；计算库持有 BO 并返回显式状态。不存在新增云调用；当前原生入口不是已完成的产品服务。

## 🎯 可选优化与停止边界

P2：精确中性前缀快照、额外输出头卸载、TTS 重叠、校准/微调。先证实瓶颈和收益再立项；不扩大硬件范围，不为它们清空 P0 通过记录。MAC 数量比不是时间比；逐节点栅栏诊断会改变融合/调度，不冒充正常执行速度。

3200 MiB 仅规划包络。Linux MemTotal、CMA、PL 可达性与 BO 常驻预算均未知；PC RSS、映射页、重排副本不可机械相加。功耗、医学审核、录音授权与全部 BOARD 项未完成。

本轮无刷写、登录、远程推送、B/C 代签或硬件回退；模型/助手实际设置无法读取时仍记 unknown。
# A08 当前增量（2026-10-03，用户停止额外重复）

默认整机入口/真实CPU与语音/统一trace/线程队列/取消和播放期限已实现，固定200轮及9个故障/策略用例完成；额外424轮后停止，两小时不追认为通过。详细差距与证据见`eval/qwen35/a08/REPORT.md`。尚需定向修复检查器肯定句、WAV人工确认接线、资源采样竞态，以及独立no_hardware单例；不重跑200轮或为时长重复。ReviewGate控制单测不是界面集成或真人确认。ASR质量、声学/医学/独立终测/BOARD仍开放。以下旧条目按其原阶段理解，不覆盖本增量。
2026-10-24 WM8960构建前置：用户已允许Windows2026.1仅补MPSoC/Kria器件，备份及精确Add配置完成；下载认证仍缺，Add和用户操作认证均exit1，未补装、K26仍0、综合实现未测。下一输入由用户在本地完成官方认证，不再等待器件补装许可；继续保持电流未测不试音与独立回滚边界。见 `evidence/a13_A/20261024-audio-pl-build-v1/REPORT.md`。

## A13 静音板测最新缺口（2026-10-25）

新串口诊断仅一次BREAK+9，内核明确拒绝日志级别操作；通道有响应但未取得调用栈。
运行时完整SysRq掩码未知，不能继续其他命令。卡死根因与恢复/释放仍未证实，
见`evidence/a13_A/20261025-muted-uart-diagnostic-v1/REPORT.md`。

后续一次正常重启已获准，但新SSH只读前置超时、载荷未送达；本地三备份通过不等于
板端原件新鲜复核。UART确认两个CPU核卡死，正常重启发送0、授权未消费，硬件复位/
断电恢复需另行确认。报告`evidence/a13_A/20261025-muted-normal-recovery-v1/REPORT.md`。

四独立静音模块及A53全零程序已交叉构建，本地策略/回调检查通过。首次部署因动态
simple-bus不展开子设备而失败；匹配源码已确认原因，dt-03 simple-pm-bus本地编译/合并
通过但未部署。IIC/PCM/DMA/声卡仍未验收。失败管理器无合作关闭通道，必须修复。
用户授权一次正常SIGTERM/回滚后发生新的内核soft-lockup，远端审计与回滚结果未返回；
默认恢复和安全释放未证实。恢复专项优先，新重启/强制动作须另行确认；不追加信号或
重放、不试音。见`evidence/a13_A/20261025-audio-muted-bringup-v1/REPORT.md`。

## A13 WM8960主时钟无板核验增量（2026-10-25）

新独立候选完成s05真实仿真、b05综合实现和同SHA routed DCP的p04复核；WNS+5.629ns、WHS+0.010ns、TNS/THS=0，5条CDC Info、9个音频ASYNC_REG及12条级间setup/hold报告。13条VG146按用户授权逐项例外；原始严格门禁25项FAIL仍保留，包含导航/concat求宽/属性字符串工具问题，不标全自动风格通过。b05导出后的后处理exit1及p01/p02/p03覆盖、选路不足均保留，p04独立补验exit0，不重导出硬件。

仍OPEN：完整PS/DDR/AXI DMA协同仿真、实际驱动probe/PLL/IRQ/长流和恢复、IIC模拟边沿与板外setup/hold、实测电压/电流与MTBF、声学/TTS板端验收。3个AArch64模块是永久EPERM候选，DT11节点disabled，不可直接删锁解锁。外部5V及跳线/旧供电断开/3.3V信号由用户确认，电流仍null；本轮不上板、不录音、不试音，不碰另一任务的板卡所有权。报告`evidence/a13_A/20261025-audio-codec-master-v1/REPORT.md`；旧a06、982项旧证据和2266项私有TTS包校验保留。



## 2026-10-25 普通资源探测无板准备
独立R0/warm/hit包bundle-v2及21项Linux控制测试、真实x86 CPU流程通过；无重型诊断、原安全门槛和失败锁存保持。BOARD/CMA改善/时延未测，最终完整数值验收未完成。管理器UNBOUND拒绝、无计算授权；当前故障恢复、安全释放、新鲜绑定驱动与独立/延迟后检仍是板测前置。旧TT10-01失败、A12第11步及A13状态不变。交接 docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md。


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


## 2026-10-26 P1-2 新鲜检查与独立监测 PC 候选

FD/缓冲复用仍逐次全字节与 maps 检查；独立新鲜 fence、发送及 END 后故障关口已接真实 CPU 模型。23 项新增+15 项相关回归及最终真实模型/故障审计通过。Board 双锁/租约/kmsg 接线、时限依据、微批预算与撤销/重启、模式切换和最终验收未完成。候选不启用默认或替换原普通包；详情 `docs/handoffs/A_A12_FRESH_HEALTH_FENCE_PC_20261026.md`。


## 2026-10-26 A12 P1-3 本地微批许可 PC 候选

P1-3 可信单 worker 的后端本地微批预算已通过真实 CPU 模型/数组/撤销/重启/未知在途验证。真实 PL 设备代次/BO 接线、P1-4 模式安全切换与最终验收仍未完成；候选不默认启用。

交接 `docs/handoffs/A_A12_MICROBATCH_LOCAL_BUDGET_PC_20261026.md`。


## 2026-10-26 A12 P1-4 PC窗口模式控制

P1-4 无板PC窗口协调器已验证：活pidfd/只读页观察、空闲切换、故障新窗口严格回退、dirty重启拒绝。生产模式/服务请求路由、真实PL设备代次与BO/run.start接线、A53构建和最终验收仍未完成。

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

本轮必要无板候选工作已收口：原Session/可信历史/病例/内容门槛、同进程分词与公共warm、有界多请求及最终应用交付门槛已接通。typed Board应用工厂及固定/opt目标配置已准备，实际放置/授权/执行未做。整体A12/Board资源与性能、医学及生产验收继续未完成。

交接 `docs/handoffs/A_A12_BOUNDED_RESIDENT_NOBOARD_20261026.md`；证据 `evidence/model_pl_A/20261026-resident-v1/FINAL_REVIEW.json`。
