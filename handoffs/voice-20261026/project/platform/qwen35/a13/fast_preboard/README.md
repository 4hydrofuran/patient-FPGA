# A13 精简板前包

只补本次真实静音链路；固定2026.1，目标6.8.0-1036-xilinx。不接板，不重建SDK，不重跑
封存RTL/CDC/STA，不运行dummy DT往返或全量控制故障测试。

产物：`evidence/a13_A/20261026-fast-preboard-v1/candidate-01/`。

- 复用四个已编译原生1036模块；第五个`a13_audio_bus.ko`显式创建音频子设备。
  原生内核无SIMPLE_PM_BUS配置，故不用未提供的通用驱动。该小驱动不访问寄存器。
- `pl-load.dtbo`只做一次PL/AFI配置，核对AFI驱动绑定后才应用`audio-muted.dtbo`。
  音频DT无firmware-name；使用原生启动FIT备份提取的DTB做真实离线合并。
- `pcm_zero_test`保持48k/stereo/S16_LE、1024B周期、8192B缓冲和内核归零。
  先写4608帧（96ms标称样本量）正常drop，再写47872帧（约997.33ms）正常drain；
  均按256帧周期对齐，避免尾周期填充把满流推过标称1秒。drop可能丢弃尚未输出的零样本，
  不把写入帧数冒称实际播放帧数，墙钟时间也不冒称实测采样率。
- 复用既有status/close进程；新适配层不卸音频DT/模块、不回载默认PL、不释放未知所有权。
  完成后明确报告AUDIO_IDLE_RESERVED，实际持锁保留，控制端仍可回应；不把保留配置当卡死。
- 正常/失败都保留日志，configfs open/write/close/applied各有回执；无重试/信号/重启命令。

默认查看命令（无设备访问）：

```
python3 -B <candidate-01绝对路径>/runner.py
```

未来板测入口为`runner.py --start <新鲜REQUEST.json>`；本轮不执行。模板authorized=false、
boot/log均null，不能直接开始。下一次按用户明确上板请求，仅做一次合并前检，绑定当前
boot、日志、互斥、供电和恢复出口；不要复用旧待认证关机助手。按现有原数值门槛执行。

停止/恢复：PCM正常关闭须证实TX/RX halt、无错、codec回slave/PLL-off且功放关闭；随后
保留音频配置和维护所有权。默认平台恢复另走事先确定的正常重启/受控冷启动，再做一次
独立后检。包内没有自动回载、清租约、强卸载或重启命令。异常状态保持UNKNOWN/原失败。
原启动文件及五原件备份不变；独立5V供电不随Linux关机断电，不带电改线。

板前复现（WSL KV260-A-2204）：prepare.py生成新候选，build.sh交叉编译小总线与PCM，
offline.py abi/dt作一次兼容及DT核对，test_fast.py检查改动的结束/失败路径，offline.py seal
封装。生成脚本使用独占新目录；已有candidate-01不得重新prepare覆盖。
历史代码、失败目录、935+982封存和逐项例外不修改。
