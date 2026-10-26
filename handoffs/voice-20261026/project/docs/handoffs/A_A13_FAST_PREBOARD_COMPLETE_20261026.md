# WM8960 精简方案板前工作完成

2026-10-26；范围：PC实现、A53交叉构建、原生DT离线合并及针对验证。
**未连接板卡、未加载PL/驱动、未关机/重启、未试音；BOARD仍NOT_TESTED。**

## 实际完成

- 四个原生`6.8.0-1036-xilinx`静音模块复用，未修改其源或封存RTL。
- 原生配置无SIMPLE_PM_BUS，新增约30行`a13_audio_bus`专用驱动，直接调用
  `of_platform_populate/depopulate`；无寄存器、时钟、复位访问。已按同一精确头文件交叉编译。
- 五模块ELF/AArch64、精确vermagic和全部136项导入版本CRC与匹配Module.symvers一致。
  解析Ubuntu实际的`next/u32 crc/name`可变布局，未把开发机kmod解析失败当ABI失败。
  模块依赖字段均为空；运行时签名执行策略仍在下次合并前检确认，不强制装载。
- DT分为一次编程的`pl-load.dtbo`（含AFI配置）及不含firmware-name的`audio-muted.dtbo`。
  私有总线显式展开子设备；运行路径先确认AFI驱动绑定，再发布音频外设。
  已从原件SHA匹配的默认启动FIT提取原生DTB，成功合并两DT并核对资源、IRQ、时钟及关键原属性。
- 适配既有控制进程，删除本次候选正常/异常清理中的DT移除、模块卸载及默认PL热回载。
  正常PCM关闭后为`AUDIO_IDLE_RESERVED`，实际锁/租约保留且status/close可响应；未知子进程
  不强杀，不提前解锁。恢复默认平台走事先确定的正常启动出口，本包不含重启命令。
- 全零PCM程序已交叉编译；短流4608帧正常drop，满流47872帧正常drain，固定48k/stereo/
  S16_LE、1024B周期、8192B缓冲、内核归零，RX/模拟功放关闭。均按256帧周期对齐；
  标称样本量约96ms/997.33ms，drop写入数不是实播数，墙钟耗时不是实测采样率。
- 8项针对PC检查通过，覆盖结束/逐阶段错误停止、未知/活子进程拒绝清理、未授权模板、
  configfs close回执顺序、无热回载源码路径，以及真实PC控制进程与实际flock保持。
  设备状态为明确PC替身，不冒充真实DMA/IIC或总线展开通过。

## 交付与最短使用路径

板前包：`evidence/a13_A/20261026-fast-preboard-v1/a13-fast-preboard-native1036.tar.gz`。
展开目录：同级`candidate-01/`；25份封装文件（24份清单内容加MANIFEST），9份部署资产。
长度/SHA见`PACKAGE.json`；所有文件长度/SHA见`candidate-01/MANIFEST.json`。

默认`python3 -B <candidate-01绝对路径>/runner.py`已在PC验证，只输出PLAN_ONLY，无板端动作。
`REQUEST.template.json`保持authorized=false，boot/log为null；本轮不生成旧boot的执行授权。

下次只需一次现场合并前检，绑定新鲜身份/内核、独占状态、日志、5V供电与恢复出口；
随后按单次PL配置→音频DT/静音IIC→短全零/满全零TX→正常停流保留所有权推进。
不做dummy DT往返、无绑定模块装卸、完整控制框架重构或全量故障注入。
若实际内核变了，精确匹配入口直接拒绝；不猜内核、不强装1036模块。

旧935+982封存、逐项例外/原FAIL、失败现场、旧租约归档、启动/默认平台原件及备份保持。
未改公共契约、未重建SDK或重跑Vivado/RTL/CDC/STA；供电/边沿/实际采样率、真实PCM/DMA与
声学结果均未测，数值null，不宣称根因已修复或绝不会卡死。

## 证据与已保留的问题

`evidence/a13_A/20261026-fast-preboard-v1/`：

| 证据 | 结果 |
| --- | --- |
| contracts/config before+after | 实际exit0 |
| prepare-01 / build-01、02 | 实际exit0，复用现有2026.1SDK |
| abi-02 / ABI.json | 实际exit0，五模块136项CRC |
| dt-02 / DT.json | 实际exit0，原生FIT FDT合并 |
| lifecycle-pc-02 | 实际exit0，8项检查，约1.29秒 |
| seal-01 / plan-only-01 / package-01 | 实际exit0，封装并验证默认不执行 |

首次ABI审查器仅接受`GPL`而误拒合法`GPL v2`，已修正审查器；首次DT检查发现继承了旧v2
固件目录，已修正生成器和新候选路径。原abi-01/dt-01失败及`dt-01-failed/`原字节保留，
没有上板试错。交叉编译器13.4与内核构建器13.3不同、初次新模块BTF因缺vmlinux跳过的
诊断保留；不为这些诊断安装/升级工具，不把CRC通过等同真实装载通过。

实现：`platform/qwen35/a13/fast_preboard/`；使用xilinx-suite核对内核/DT移植边界。
核心实现、架构和证据验收未委派；实际模型设置unknown，无凭据持久化。
