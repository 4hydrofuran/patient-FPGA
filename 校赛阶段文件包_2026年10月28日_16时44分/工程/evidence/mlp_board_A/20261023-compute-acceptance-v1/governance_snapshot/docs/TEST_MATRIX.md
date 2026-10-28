# Qwen3.5 分域测试矩阵

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
