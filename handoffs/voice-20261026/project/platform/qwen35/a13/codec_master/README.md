# WM8960主时钟：独立无板候选，不可部署

保留六根信号线和板载24MHz。WM8960产生采样及I2S位/帧节拍；PS约100MHz只负责
过采样、AXI控制和数据搬运，不作为第二个采样率源。固定48kHz、S16_LE双声道、
每声道16bit槽、32BCLK/frame、256帧/1024B DMA周期。

最终状态只看本轮证据目录中的`OFFLINE_REVIEW.json`、`REPORT.md`与`SEAL.json`，
文件存在或Vivado进程exit0均不能替代验收。本目录不会连接板卡或自动加载产物。

## 设计与边界

- `rtl/audio_input_sampler.v`：三个独立三级ASYNC_REG链，BCLK额外等待四拍后发布事件。
- `rtl/audio_serial_slave.v`：同系统域设备节拍收发；一帧弹性缓冲、严格valid-ready、
  I2S边界LSB、TLAST、失钟/槽宽/欠载/溢出/包尾故障和停机确认。
- `build.tcl`：固定Vivado2026.1、xck26-sfvc784-2LV-c，继承官方kv260_base的PS/DDR/MIO，
  新建AXI DMA/IIC/GPIO与完整流接口。此维护位流不包含计算核，不可与TT10计算并用。
- `drivers/`：独立DMA派生模块、CPU DAI/PCM、单链路codec-master声卡。全部用户可达
  开流入口永久EPERM；不提供模块参数或DT解锁开关。当前不安装、不加载。
- `wm8960-master-disabled.dtso`：全部11个新增节点disabled，无fpga-region自动加载。

正式AXI-Stream接口元数据与时钟关联不可删。S_AXIS/M_AXIS分别包括TDATA/TVALID/
TREADY/TLAST；每拍一帧，S2MM TKEEP固定4'hf。只看逐根信号相连，不能忽略BD接口未连警告。

## 核验材料

证据根：`C:/Patientqwen/evidence/a13_A/20261025-audio-codec-master-v1/`。

- 原始严格门禁保留FAIL；13条VG146路径仅按用户授权逐项审查，预算仍为3。
- 其他工具局限（自动导航注释、concat求宽、AMD属性字符串）不伪改为严格PASS。
  `static-audit-final/`复用同一formatter AST，不增加另一套Verilog解析器。
- `EXCEPTIONS.md`与实际逐目标min/max报告、CDC原始及拓扑视图、同源RTL的xsim回归一起阅读。
- 规格在`spec/codec_master/`；三个同名Markdown及WaveDrom SVG为合同示意，不是实测波形。
- `CLOCK_REVIEW.md`给出跨链反例与有条件预算；亚稳态、MTBF、板外电气不能由RTL仿真证明。
- `MEASUREMENTS.md`列出后续实测项目、所需工具的原因及安全边界。

实际仿真验证自定义串行接口与独立DMA源/汇行为；完整PS/DDR/AXI DMA系统协同仿真
未运行，不等于DMA板端、Linux IRQ、声卡probe、长流或声学验收。TTS私有运行包沿用
此前已校验版本，没有重新打包权重或试音。

## 本地复核与回滚

纯模型可运行`model.py`、`clock_budget.py`；真实执行命令、退出码和输入hash见对应
证据JSON。硬件重跑必须使用未占用的新尝试编号及协作队列，先确认没有活动任务；
禁止覆盖已有`local/a13c_sNN`、`local/a13c_bNN`或receipt。不要运行已退休的`clean_draft.py`。

`native_job.py`与`run_native.ps1`仅启动本地2026.1工具，无hw_manager或板端命令。
`reconcile_b04.*`只为已核实退出的本任务b04失败预约留档，不是通用解锁器。

旧a06和旧证据保持不变。撤回仅撤回本轮A13增量，不恢复整仓、不覆盖并行TT10文档。
参见`ROLLBACK.md`。旧a06会输出BCLK/LRCLK，禁止在WM8960主模式下盲目回载。

外部5V、5VIN跳线、断开旧3.3V供电、共地与信号3.3V已由用户确认；实际电流及
外部电源容量仍null。本轮最新指令限定不上板、不录音、不试音，即便另一个任务
报告释放，也需后续新鲜状态和明确调试窗口，不自动部署。
