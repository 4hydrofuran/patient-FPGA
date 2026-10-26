# A13 WM8960主时钟：无板交接

本轮只做无板：没有SSH连接KV260、PL/DT加载、模块安装、录音或试音。外部5V、
5VIN跳线、旧3.3V供电断开、共地与信号3.3V由用户确认；实际电流/电压和MTBF未测。
另一任务的板端租约、双锁与现场从未操作，不能把本地构建预约归档当作板卡释放。

## 实际完成

- s05：最终RTL的xsim2026.1，520帧双向逐位比较、2周期TLAST、5类故障与相位/偏斜、
  非零回压保持、半帧启动、清错、复位隔离。
- b05：xck26-sfvc784-2LV-c，正式AXIS接口/时钟关联，实际bit/XSA/routed DCP，
  WNS+5.629ns、WHS+0.010ns、TNS/THS=0，BD关键警告与布线错误0。
- b05导出后reset_path后处理失败exit1保留；p04从相同SHA DCP只读重开，原约束STA
  复现，9个音频同步FF的同钟/属性/直连/唯一扇出证书与12份级间setup/hold通过。
  仅分析用视图实际报告5条安全Info、Warning/Critical0，不重导出设计。
- 13条VG146按用户授权逐项核验。原始严格门禁25项FAIL保留；其他导航、concat和
  属性字符串工具问题另有同一formatter AST评审，不称全自动门禁PASS。
- 3个真实AArch64模块v5，内核6.8.12-a10irq2；CPU端格式翻转和DMA32位/对齐/周期
  条件以真实C执行反例补验。模块永久EPERM，不可直接开流。
- DT在原irq2备份上真实编译合并，11新增节点全disabled；导出HWH完整AXIS、TKEEP
  常量、地址、GIC SPI104..107、时钟及引脚方向核对通过。

## 入口与回滚

源码：`C:/Patientqwen/platform/qwen35/a13/codec_master/`。
证据：`C:/Patientqwen/evidence/a13_A/20261025-audio-codec-master-v1/`。
先读`REPORT.md`、`OFFLINE_REVIEW.json`、`EXCEPTIONS.md`和最终`SEAL.json`。
最终硬件位于`native-tools/b05/artifacts/`，此目录不是当前部署授权。
回滚见源码`ROLLBACK.md`，实测及原因见`MEASUREMENTS.md`。

旧a06和982项旧证据不变；2266项私有TTS包单独复验，不复制/再分发权重。没有本轮
实板修改需要撤销。旧a06会输出时钟，codec主模式下不能盲目回载，必须先消除双驱动。
共享文档仅追加A13增量，不能恢复整份旧文档覆盖并行TT10记录。

## 后续独立阶段

完整PS/DDR/AXI DMA协同仿真未运行；真实codec PLL/声卡probe/DMA IRQ/停止恢复、
板外时序、实际IIC边沿、电压/静态与峰值电流、声学及TTS板端仍NOT_TESTED。
继续等待另一任务完成独立后检并明确释放；随后另开新鲜身份、原件备份、唯一租约/
双锁和明确调试窗口。不直接改DT为okay或删EPERM，不自动进入BOARD。
