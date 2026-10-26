# A12单投影停止交接

2026-10-24 A12第07步单投影：l00 gate 3次真实PL调用T8/1/1，job1/73/145，Y被GLU真实消费；同板S1/S2的10行logits、36份抽样投影、72诊断节点、混合状态逐位一致。两worker正常exit0，默认PL/GDM恢复、ZOCL无/设备FD-VMA无；最终扫描拒绝后manager27132/startticks2110722保留双锁/active lease，无受控恢复入口。本轮STOPPED，07整体未完成，三个MLP投影/08未执行；后续先安全收口管理器，不能复用旧许可。两个06历史FAIL按用户指示保留待评估。报告 `evidence/model_pl_A/20261023-step07-single-v1/REPORT.md`。以下均为历史快照。

单投影证据通过，生命周期仍未闭合。原始快照：本轮readback-v1/stopped-snapshot-v1.json。独立快照时manager只有一线程、无子进程/设备/XRT；wrapper27125等待。两把锁及活动租约仍保留，严禁据此继续计算、删除租约或假记正常退出。当前代码无受控恢复入口，编辑源文件不能唤醒旧实例。先按REPORT最后一节单独处理收口，再讨论扩大范围；不重跑A11、不重启刷写。
