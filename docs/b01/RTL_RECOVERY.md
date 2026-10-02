# B01 本机 RTL 验证记录与复现

当前核综合/XO成功，Vitis 原生 `run_b01.ps1 -Target cosim` 返回 **1**。第一次失败在 XSIM 生成的 `xsim_48.c` 编译阶段，实际 RTL 尚未启动。首次日志和收据保留在 `evidence/b01/cosim_attempt_first/`、`logs/b01/cosim.log` 与 `reports/b01/cosim.receipt.json`，没有把该返回码改写成成功。

诊断时对**相同** Vitis 生成的 HDL、test vector 和仿真目录执行生成的 `xelab` 命令，附加 `-mt off -v 1`，并仅在该子进程移除 `CPATH`。50 个生成 object 完成；本机内置 MinGW 链接随后报 `Access is denied`。改用现有 `D:\mingw64\bin\g++.exe`，对这些 object 加 `--image-base,0x400000` 重新链接，退出码 0。无 Vivado/Vitis 安装文件、全局 PATH 或设计源码改动。

从根目录运行 `tools/relink_xsim_snapshot.ps1` 可重复**链接步骤**，它检查 object 序号、现存生成 C 文件与相应 object 的时间，再写 `reports/b01/xsim_relink.receipt.json`；仅链接成功不能视为 RTL 通过。每次改变核或重新综合，必须重新执行 Vitis Cosim 以生成对应 HDL/向量并完成 xelab 编译，不能复用这次的旧 object。

本次实际后续操作：在 `build/b01_hls/hls/sim/verilog` 中执行本地保存的 `run_recovered_xsim.bat`（其唯一执行行与工具生成的 `run_xsim.bat` 的 XSIM 行相同）；XSIM 返回 **0**，日志出现 `25 / 25`。在 `build/b01_hls/hls/sim/wrapc_pc` 运行 `cosim.pc.exe --suite cosim`，进程 PATH 临时包含 `D:\2026.1\2026.1\win64\lib\csim`、Vitis 的 MinGW 10 bin 和 `fpo_v7_1`；输出回放返回 **0**。第一次手动运行 postchecker 时漏了 `libhlsm-GCC95-x64.dll` 所在的 csim 目录，返回 -1073741515，失败收据也保留；补足运行时目录后通过。

实际输出保存为 `evidence/b01/rtl_recovered/tv/rtldatafile/rtl.w4a8_linear_v1.autotvout_gmem_{y,meta}.dat`，输入与软件 expected 保存于相邻 `cdatafile`。生成的 `apatb_w4a8_linear_v1.cpp` 指向这些 RTL 输出文件。整个 36 文件证据集、实际使用的仿真快照 SHA 和源码 SHA 见 `reports/b01/rtl_recovered_summary.receipt.json`；仿真和回放日志分别是 `logs/b01/xsim_recovered.log`、`logs/b01/rtl_postcheck.log`。

回放覆盖 25 个合成输入事务，含两种新目标形状的 T1、小边界、错误和重复 job。`cosim.pc.exe` 输出 `B01 PASS suite=cosim transactions=25`，新尺寸两例 max_abs/NRMSE 均为 0。日志中的 58175 个 INT32 比较来自测试程序对独立 reference 和核辅助计算的回归；RTL 内部部分和没有逐项探针，不能把该数解释成 RTL 内部和的直接观测。5664 个 FP32 输出比较包括读取 RTL 的 Y。T8 RTL 与原 B2 新尺寸 Cosim 仍未测试。

工程状态使用 `PASS_RECOVERED` 精确表示“标准总流程退出 1、相同生成设计的实际 RTL 和输出回放退出 0”。原失败与后续通过是两个不同执行记录；今后可用新 Vitis 版本或清洁系统环境复核原生总流程，但不能追认原失败为 0。
