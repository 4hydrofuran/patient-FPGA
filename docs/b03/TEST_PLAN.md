# B03 开发与验收计划

基线 B02_X128 原始源码及testbench冻结在 baseline/b02/，SHA见 source_manifest.json。公共数学/字节布局/私有顶层参数和meta布局不变。

三个独立构建：baseline、reuse、double。T1保留原decode调度；T>1采用输出tile→group→token顺序，跨token复用W4及Sw，并保证每个token的FP32沿group递增累加。double使用两个明确独占的权重/scale缓存，当前计算与下一group加载并行，函数返回后才交换所有权；最后group不请求下一块。先完整预扫非法W4再进入任何输出路径。

PC/Csim full继续覆盖两种新尺寸T1..8、旧形状、手算/量化/主机错误/私有核错误。新增T2/3/5/6/7/8的N65/K257跨tile与奇数group尾块，T8重复执行。独立dense INT64/FP32 golden不调用待测核，历史1e-6门槛与新形状1e-4+1e-5*abs(ref)不变。

RTL b03_cosim实际包含两种目标形状T1/T8、全部既有边界/错误/重复任务及新增尾块。逐次TRANSACTION标签绑定性能文件，仿真输出经原生cosim回放核对。各构建依次PC→Csim→综合→Cosim，保留失败尝试，不覆盖日志。通道/数据流报告用于确认加载与计算是否真实重叠；AXI背压覆盖须以仿真BFM配置为证，不能由功能PASS推断任意外部背压。

## 内存受控的等价分组

每个variant依次执行`run_prefill.ps1 -Variant <baseline|reuse|double> -Target cosim -Group <smoke|gate_t1|gate_t8|down_t1|down_t8>`。
smoke运行原前30笔事务；其余各组运行原同seed的大矩阵一笔。每组原生C/RTL PASS，或经严格恢复后的真实RTL及POST_CHECK分别退出0，才执行`python tools/archive_prefill_batches.py --archive <variant> <group>`。恢复时原生退出1仍保留为失败，见RTL_RECOVERY.md。归档保存actual RTL输入/输出、逐笔周期、metadata、日志、源码SHA，再允许下一组覆盖构建目录。普通组使用trace_level=none。

全部组完成后执行`python tools/archive_prefill_batches.py`，以完整PC日志中的(case,T,N,K)多重集合核验每版34笔RTL覆盖未减少，生成独立消融表。逐组job序号从1000重新开始，属于合法独立任务，数值输入seed不变；跨调用生命周期仍由原重复任务组验收。

随机背压的原smoke32笔入口保留。为控制内存，同一testbench新增stress_basic/lifecycle/tail/max_k/max_n五组选择，事务数分别为12/11/7/1/1，总计32。配置hls_prefill_<variant>_stall_<group>.cfg启用random_stall=1和trace_level=port；五组均须真实RTL及原生POST_CHECK通过。verify_prefill_stress.py核验五组(case,T,N,K)多重集合与原smoke32笔一致，并保留生成BFM的延迟约束和实际端口波形。分组不修改核源码、数学、公共布局或容差。

选型先要求全部数值/RTL通过，再比较T1 decode、T8总周期/每token周期、HLS资源和时序估计。只冻结一个候选；资源/时序仍须B04实现验证。逻辑请求字节数不冒充DDR实测。实现、aarch64、BOARD、模型质量/整机时延/功耗继续NOT_TESTED。
