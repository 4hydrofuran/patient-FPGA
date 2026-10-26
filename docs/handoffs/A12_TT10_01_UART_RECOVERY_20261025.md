# TT10-01 恢复进展：网络恢复，内核阻断，未完成

用户已授权继续恢复，并接通J4数据USB；固定FTDI B/COM5串口与SSH均已核实为原板卡。网络原来没有IPv4；一次直接ip addr add成功后地址又消失，失败SSH/前后串口证据保留。随后按工程既有方案创建仅驻内存的NetworkManager连接，D-Bus确认Unsaved=true，192.168.2.2/24与固定主机密钥SSH复核成功。没有写永久网络、网关/DNS或改开发机网络。

当前boot d6d3b16f-f78c-4efa-acaa-14fc8b076fe8、内核6.8.0-1036-xilinx，已不是旧boot/6.8.12-a10irq2。旧manager167484/worker167575已不存在，如何退出及退出码未知；不得追记正常退出，也未执行旧PID恢复/强杀脚本。旧租约完整保留且SHA不变，未归档。完整FD/VMA只读扫描两次均通过（193/194进程），默认overlay applied、GDM active、ZOCL absent；这些观测不构成当前严格关闭门禁通过。

内核全文保存为CURRENT_KERNEL.raw.txt，SHA 9191287a4b763164d6010168548d6c8a5242ae1ea0f9903e7d84e17f9ec1e6f4。原严格诊断规则提取195行，包含X.509证书加载WARNING/调用栈，以及pinctrl、TPM、OP-TEE、overlay属性等诊断。195是匹配行数，不是195个独立故障。没有批准该基线、静默忽略告警或放宽释放门槛；因此旧租约继续保留、新窗口未准备。

原image.fit、boot.scr.uimg及已保存a10irq2候选均已只读备份到boot-backup-01，三件大小/SHA与板端及工程pin一致。既有候选启动流程PC 17项通过，不代表本轮已启动候选。下一步具体维护方案见BOOT_PLAN.md：专项确认一次正常重启并临时启动已有a10irq2，仅做只读复核；保留默认启动文件，不自动重试/复位/刷写。该新启动动作尚未获专项确认、未执行。

本次确实发生的板端改动仅为临时网络恢复及其独立恢复日志。无信号、重启、复位、刷写、模块/测试PL操作、模型运行或租约改写。CPU关闭通道26项PC通过仍为未部署；source-04的24项复核、14项回归、普通应用1对R0/hit、零后缀与A53构建通过均保留；未重跑source-03。此前字节码清理审批拒绝记录保留，未尝试绕过。

TT10-01未完成，新增PL调用0、实板TTFT=null、≤10秒NOT_VERIFIED，TT10-02未开始、A12第11步PENDING。原进度与全部失败证据保留；PROGRESS.json为较早网络阻断历史，本次以PROGRESS-02.json为准。本次调试/证据验收由主代理完成，未调用DeepSeek；既有DeepSeek排版回执不改。实际模型设置unknown。

接续保留原恢复授权；专项正常重启/候选启动须先确认BOOT_PLAN.md范围。不要自动复用旧boot/PID或把无板通过转记BOARD。
