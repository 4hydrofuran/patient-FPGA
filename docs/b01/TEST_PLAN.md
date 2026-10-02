# B01 独立数值验证计划与已执行边界

数学规范：contracts/quant_v1.json；独立expected：tb/golden_w4a8.hpp，dense行主序INT64每组累加，FP32按group顺序恢复。
reference/quantization.hpp 与固定手算码比较，tests/numerical/quantization_reference.cpp 可不链接任何HLS源码独立执行。

已执行：两种新形状N3584/K1024与N1024/K3584的T1..8，共16组合；seed=0x20261002+shape_index*256+T。
旧手算/尾块/极值/多scale/padding保留码等历史测试保留1e-6绝对门槛；新形状固定atol1e-4+rtol1e-5，不按结果改变。
新形状使用一般非二进制Sw与各token不同Sx；所有INT32部分和bit-exact。每case记录max_abs/NRMSE与dense/packed/expected文件hash。

27项量化断言：正负ties-to-even、W4/A8夹紧、舍入环境、零组、K尾部absmax、A8行scale与padding、NaN/Inf原始输入、INT32范围。
32个公共主机拒绝用例：job/维度/空指针/五类短缓冲、非法W4/A8、W/X/Sw padding、零/负/NaN/正负Inf scale。
主机适配层错误不启动核、不修改Y/meta；它们不是RTL内部检查，也不是B04的动态库生命周期实现。
私有核继续验证原有5类错误；新增相同/不同job连续执行、成功计数、错误后旧Y不消费及合法输入恢复。

真实权重扩展：官方固定revision 2fc06364715b967f1860aea9cf38778875588b17，layer0 gate_proj/down_proj各完整BF16矩阵；各T1/T8，共4电脑case。
真实权重转FP32仅作精确bit扩展；激活仍为合成输入。没有模型真实层激活、72矩阵全覆盖或完整模型推理。

当前与原B2新形状T1..8 Csim通过；原B2新形状Cosim未执行。
当前核代表性两种新形状T1及小边界共25事务的RTL Cosim通过（PASS_RECOVERED）；原生Vitis总流程首次失败，保留退出码1，后经本机链接恢复并执行实际RTL及cosim.pc.exe输出比较。T8 RTL验证属于B03，不用Csim代替。
全部步骤限定无板；平台、布局布线、ARM64、BOARD、整机质量与速度均未测试。
