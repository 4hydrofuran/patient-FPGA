# TT10-01：恢复完成，独立窗口已在电脑端准备，阶段未完成

## 本轮实际结果

J4数据线重连后固定FTDI B/COM5复核通过；首次postboot只读采集因USB端口断开失败，记录保留。一次正常重启及一次临时bootm已获专项授权并完成，当前boot为1d0499ab-f1f9-438c-969a-3e701a0d806f、内核6.8.12-a10irq2。同板machine-id、原启动文件、候选FIT、已安装ZOCL文件、XRT库哈希均匹配。三件启动文件完整本机备份保留。没有saveenv、刷写或改默认启动文件，没有第二次重启/硬复位。

SSH在正常重启时断开，原Windows返回码4294967295保留；板端reboot-command.json明确exit0，串口核对U-Boot/三组件哈希/载板配置后仅发出一次bootm并见登录。首次认证等待已取消且payload_sent=false，首次被动捕获超时没有发送任何启动字节，都不占用额外重启。

当前内核启动诊断与原TT10-01已审查基线对照：原250行匹配，本次186行匹配；除同一X.509栈CPU编号和一个x22寄存器值外，本次每项诊断及次数均已存在于旧基线。此前PL动作产生的诊断在本次新启动中不存在。这些是仍OPEN的已知限制，不是修复或计算验收。本次仅将精确原始字节SHA e6c899a5780c7c6c6549ff11fa8940654665ba699e4c5e85c088fbb5f401069e审查为恢复基线；后续新诊断继续锁存拒绝。计算阶段仍需独立新鲜基线与资源审查。

## 旧失败与归档证据

旧boot已在本轮首次接通串口前变化，旧manager167484/worker167575不在；退出方式/退出码均未知，原CPU余量拒绝不转记正常退出或计算PASS。本轮未向板端进程发送信号。旧租约在新boot持有协调锁及双规范锁、完整FD/VMA扫描、内核连续性、默认overlay/GDM、原件哈希复核后，以renameat2(RENAME_NOREPLACE)原样移入：

`/var/lock/kv260-a1/history/a12-tt10-01-20261024-v1-priorboot-abnormal-20261025-v1/lease.json`

租约SHA仍为568d525f398a30b931f1767f4eec6ac19303814e781b1602d5756062f2a248e7。归档后的独立SSH只读后检exit0：活动租约为空、两把规范锁无持有者、完整扫描无加速器FD/VMA持有者、默认overlay applied、GDM active、ZOCL absent。范围仅为恢复/归档通过，TT10-01计算BOARD仍未验收。

首次归档前的严格哈希检查拒绝已保留：UART脚本text=True转换了41个CR，随后一次本地JSON读取未指定UTF-8又误解码了版权符号。已改为二进制采集+base64/长度/SHA、显式UTF-8，修正后UART与SSH的58363原始字节完全相同；不对日志做归一化来绕过严格比较。早期误标raw的转换产物、失败、纠正说明全部保留（UART_KERNEL_NEWLINE_FAILURE.json）；新的精确审查以IRQ2_KERNEL_RECOVERY_REVIEW-02.json为准。

## 独立板测窗口准备

电脑端新包为同证据根window-20261025-v2/bundle-v3；新window_id=a12-tt10-01-20261025-v2，拟用全新远端目录/租约，未部署、未执行。包含source-04 A53程序及最终CPU关闭manager-source-03；关闭mixin放在-I模式明确加入的platform/qwen35/a12导入目录。保持旧6项请求、70token前缀、5000硬上限/4752最坏调用预算、原内存/CMA阈值、公共数学/ABI/硬件不变。新驱动默认PLAN_ONLY，执行需要准确窗口参数及另行计算授权；现有启动维护授权不包含计算。

包内Python编译、Linux -B -I真实导入/继承来源、驱动默认PLAN_ONLY、全部manifest字节/SHA通过。原父包165个manifest文件仍相同；只复制清单文件，没有复制或删除历史额外字节码。原清理审批拒绝记录仍保留，未绕过。准备过程第一次因sysfs状态末尾换行拒绝，发生在新目录创建前，原失败保存；修正为对状态枚举去除行尾后严格比对。

## 通过项、待办与边界

原source-04 24项严格复核、14项脚本回归、普通应用1对R0/hit、零后缀、A53交叉构建，以及CPU关闭26项PC检查继续有效；未重跑source-03。新增UART发送时限9项、跨启动归档9项PC检查和新包隔离导入/PLAN_ONLY检查通过。恢复已完成，启动文件/平台默认状态保留。DeepSeek未参与本轮调试/板端/验收，短状态记录由主代理直接完成；历史排版调用回执保留，实际模型设置unknown。

下一步是单独审查新包的即时计算基线、资源余量、全新命名空间和双锁/唯一租约，再由用户明确授权这一独立计算窗口。需要在板上实际核对关闭通道、完整数值、普通应用R0/hit与真实少算/TTFT。仍不得将PC、交叉构建或恢复后检当作计算BOARD通过；源04关闭通道未在板端运行。V07/V08质量拒绝、教师审核PENDING、原历史失败保留。

TT10-01未完成；本轮新增PL调用0，实板TTFT=null，≤10秒NOT_VERIFIED，TT10-02未开始，A12第11步PENDING，A13条目保留。PROGRESS-02与BOOT_PLAN的未授权/未归档措辞为较早历史，已分别由BOOT_AUTHORIZATION、BOOT_EXECUTION与本报告覆盖。

接续从新窗口PLAN.md与最新PROJECT_STATUS开始，不复用旧boot/PID/租约，不重发已经使用的一次启动维护。
