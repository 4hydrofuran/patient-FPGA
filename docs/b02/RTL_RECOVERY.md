# B02 RTL 联合仿真与本机恢复记录

`run_b02.ps1 -Target cosim` 的 Vitis 原生流程退出 **1**；失败点是 XSIM 生成的 `xsim_54.c` 编译，未运行 RTL。原始日志、生成命令和原始收据保存在 `evidence/b02/cosim_attempt_first/`。这项失败不改写为 0。

对同一次综合 HDL 和 Vitis 生成的 `--suite cosim` 25 笔输入，在 `build/b02_cache_x_hls/hls/sim/verilog` 从生成的 `run_xsim.bat` 取 Xelab 行，附加 `-mt off -v 1`，仅在子进程去除 `CPATH`。第一次恢复尝试停在 `xsim_54.c`；第二次完成该文件但停在 `xsim_55.c`；第三次完整编译 56 个目标文件，最终由本机 MinGW 链接器报 `CreateProcess`。各次详细日志在 `logs/b02/xelab_recovery*.log`，未更改 Vivado 安装文件、全局工具链或设计源码。

随后运行 `tools/relink_b02_xsim_snapshot.ps1`，先检查 `xsim_0..55.win64.obj` 的连续性、剩余生成 C 文件与目标文件时间，再用本机 `D:\mingw64\bin\g++.exe` 和 Vivado 2026.1 的模拟器库链接。最终链接退出 **0**，其对象 SHA 记录在 `reports/b02/xsim_relink.receipt.json`。在第二次 Xelab 中手动补编并链接出的快照因 Xelab 尚未完整生成版本标记，被 XSIM 拒绝；这次失败只用于诊断，不计入通过。

用同一生成的 XSIM 启动行 `run_recovered_xsim.bat` 执行 RTL，退出 **0**，日志出现 **25/25**；包含 `N=3584,K=1024,T=1` 与 `N=1024,K=3584,T=1`。实际 RTL 输出由 `build/b02_cache_x_hls/hls/sim/tv/rtldatafile/` 保存，生成的 `wrapc_pc/cosim.pc.exe --suite cosim` 回放这些输出并核对独立参考，退出 **0**，25 笔事务均通过。其日志和收据分别在 `logs/b02/xsim_recovered.log`、`logs/b02/rtl_postcheck.log`、`reports/b02/xsim_recovered.receipt.json`、`reports/b02/rtl_postcheck.receipt.json`。

`evidence/b02/rtl_recovered/` 归档了输入、期望、RTL 输出、生成 Tcl/批处理、周期文件及 `w4a8_linear_v1.wdb` 波形。该大文件被 `.gitignore` 排除以避免把 2 GB 波形放进源码仓库，但在本机交付目录中保留。所有 36 个归档文件和快照/回放程序的 SHA256 见 `reports/b02/rtl_recovered_summary.receipt.json`。凡核源码、测试向量或 HDL 发生变化，必须重新生成本次全部仿真产物，不能复用这些对象或波形。
