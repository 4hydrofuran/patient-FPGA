# 最新：连续问诊服务已上线

最新现场状态：用户随后要求退出界面并关机，已完成。连续服务worker正常退出0，累计9次模型请求、8424次提交与确认完成，租约已归档、ZOCL不存在、默认PL已恢复。随后只发出一次正常poweroff，串口被动等待最终确认 `reboot: Power down`。板子当前已关机，以下活动服务内容是关机前记录。关机及被动确认回执在同证据目录request-shutdown/shutdown-status/poweroff/powerdown-passive UART JSON；不可据本文旧PID认为仍在运行。

用户本轮要求像实际使用一样支持多条问诊和结束后新问诊，已完成必要软件调整及真实验证。详细记录：`evidence/frontend_board_A/20261026-continuous-session-v1/REPORT.md`。

**当前活动服务替代此前gui-qa-v2。** root `/var/lib/kv260-a12/web-multi-20261026-v1`，Owner `a12-web-multi-20261026-v1`，manager6433、worker6596；boot68fc4950-b776-4f54-8b67-c40ddeac6bb6、irq2内核。活动租约/ZOCL是用户有意保留。不能用此前关机、失败退出或单问窗口释放回执认定现场已空闲。

真实GUI验证：病例3同场两问分别回答20分钟/胸前正中，结束评价2问20分；新开病例1回答10分钟，结束评价1问10分。三条均MODEL/FPGA_REAL和内容检查pass，同一worker、72权重一次加载、70-token缓存只预热一次，累计3384次提交。随后再开新的病例3空白用户会话，turns=[]、ready=true。不要向这个用户场次插入代理提问。

本次新Owner独立预算60000次、4小时；原验收5000/1800配置及原生二进制保持不变。底层实际ready已确认60000。输入前保留10296次最坏完整问题预算，时限/额度到达后保存记录并正常收尾。不是无限自动续租，不把4小时配置当长期稳定性已经通过。

连续模式不在finish后关闭后端，也不限制一场一问。每场原业务200条上限保留；最近8场在内存，已结束场次归档到 `bundle/run-v1/s2/consultations`，旧snapshot/evaluation/turn结果保持可读，第9场可继续创建。PC22项检查通过，实板仅两场三问基本验证。

用户结束一场仍继续占用服务/模型，这是请求的行为。真正停服使用可信宿主写ROOT/stop-request.json，等待当前问题完成及原PS正常worker关闭、恢复default PL、归档Owner。之后结果HTTP保留30分钟。若用户要求关机，先正常停此服务并读取真实释放回执，再关机；不能直接套用“无租约”关机脚本。

此前gui-qa-v2用户问题也已真实完成：worker_exit=0、2664次提交与完成、原Owner正常归档和default恢复，之后才停旧结果服务。新连续窗口当前尚未结束，不能提前追记normal restore或manager_exit=0。没有重启/Vivado/Vitis、公共ABI或提示词变更，无DeepSeek核心验收，无提交/推送。
