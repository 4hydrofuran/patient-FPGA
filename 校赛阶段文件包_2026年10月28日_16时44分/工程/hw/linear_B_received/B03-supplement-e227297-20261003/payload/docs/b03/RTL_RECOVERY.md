# B03 串行RTL与本机工具链恢复

原始combined仿真未完成，不能用进度条作PASS。五个等价分组保留原34笔调用。每个分组由Vitis从当前综合RTL与同一testbench产生向量、C输出回放程序和Xsim编译产物。

本机旧版Vivado GCC先出现CreateProcess。进程级RDI_PREPEND_PATH加入该GCC配套bin后，相同生成C可编译，但内置链接器仍可能Access is denied。原始cosim.receipt.json实际退出1及日志不改写。

run_prefill.ps1在原生失败后只在目标文件均完整、序号连续、时间不早于本次准备、现存C对应object有效、postchecker不早于其源文件且source/TB/config哈希相同的情况下恢复。所有本次object的SHA保存到*_snapshot.json；调用已存在的D:/mingw64/bin/g++.exe，保持对象不变，以--image-base,0x400000连接Vivado模拟内核库。使用相对object路径缩短Windows链接命令，并仅为健康MinGW设置其配套COMPILER_PATH。没有修改安装目录或全局环境。

本机basename辅助程序启动失败时，Vitis还可能在wrapc_pc目录生成名为cosim.tv.exe的程序，不能拿它作输出回放。恢复入口显式使用cosim.pc.mk、DIRECTORY=wrapc_pc及独立postcheck_objects缓存重建cosim.pc.exe，要求编译日志出现POST_CHECK；编译器DLL仅通过进程PATH提供。具体make参数、编译日志、postchecker与RTL模拟快照SHA均留存。

reports/b03/postcheck_consumer_proof.json记录额外验收：用明确POST_CHECK构建的程序重新回放已归档baseline smoke和gate_t1实际输出，两组均退出0；只把scratch副本中的手算Y[0]从890改成0，程序非零退出且明确报告FP32不匹配。原始归档SHA不变。此检查证明回放程序确实消费RTL数据。

恢复后按工具生成的同一XSIM命令实际运行RTL（*_rtl.receipt.json必须为0），再以对应suite执行Vitis生成的cosim.pc.exe回放实际Y和meta（*_postcheck.receipt.json必须为0）。独立golden、错误输出不变和完成计数检查原样保留。单独relink=0不是功能验收；原生退出1保持FAIL，最终分组可标PASS_RECOVERED。

普通组关闭波形；应力组random_stall=1且保留端口波形。archive_prefill_batches.py校验逐笔周期、实际输出文件时间、源指纹及全部测试集合，再逐组归档。恢复路径不会生成原生最终Cosim报告；归档真实XSIM性能文件、relink/RTL/postcheck日志与原生失败记录，避免使用旧报告冒充本次通过。

完整实现/板端DDR、XRT库、超时DMA生命周期不属于本次证明。

## 2026-10-03工具启动与快照完整性补充

xelab最后的主C对象完成后仍需C++ DPI对象和xsim.svtype/version/mem/reloc/type支持文件。恢复入口检查本次源/config指纹与生成物时间；缺少对象时仅使用本次生成C和已安装Vivado GCC补编，保留C/C++语言、参数、前后SHA与退出码，再继续工具原有xelab命令。支持文件不全或kernel没有Simulation completed时拒绝计PASS。POST_CHECK使用独立postcheck_objects_<时间>目录，避免旧缓存掩盖本次编译证据。自动恢复同样适用于五个背压分组。

本机MinGW的Windows/Linux检测子进程也曾停在精确的uname | grep -i Linux命令。tools/check_prefill_os_probe.ps1只处理超过120秒、父make命令指向本工程cosim.tv/pc.mk的该探测进程；保留PID、父命令及时间到os_probe_interruption.json。原有MAKEFLAGS指定Windows_NT，随后仍须实际RTL与POST_CHECK完整通过。此恢复不终止编译或仿真进程，也不把探测恢复本身当作功能PASS。

## 原生RTL完成后的仅回放恢复

baseline down_t8原生RTL完整结束，但basename辅助启动问题导致wrapc_pc目录生成了cosim.tv.exe，原生POST_CHECK未能启动，整个CLI仍退出1。xelab已清理object，因此不能套用重新链接保护入口，也不应重复长仿真。

tools/complete_prefill_postcheck.ps1只在本次源/config指纹一致、原生日志出现完整1/1与Starting C post checking、xsimkernel.log明确Simulation completed、实际输出/周期/日志均新鲜时重建明确POST_CHECK的cosim.pc.exe。它记录实际RTL文件前后SHA不变，并回放真实Y/meta。原生CLI退出1不改写，未观测的RTL子进程exit code保持null；状态为PASS_POSTCHECK_RECOVERED，不能误写为原生PASS或杜撰子进程退出码。

成功收据：reports/b03/baseline/20261002-171355-5951792/cosim_down_t8_postcheck_only.receipt.json。首次使用mingw32-make别名启动失败；改为已存在的make.exe后编译及回放退出0，没有更改核或向量。五组及34笔集合最终验收见reports/b03/baseline_acceptance.json。
