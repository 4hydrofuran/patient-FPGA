# B01完成清单（2026-10-02）

工程数值门槛PASS；阶段COMPLETE。实际客户端Sol/High/Standard设置仍未核实，不由本地文件宣称切换。

| 任务条款 | 已完成内容 | 证据 |
|---|---|---|
| 1 独立标量参考与手算字节 | 独立dense INT64/FP32参考保持与B00字节相同；新增FP32量化标量参考；0x97/0x2f及[890,-891]硬编码交叉检查 | reference/、tb/golden_w4a8.hpp、hand_sample原始数据 |
| 2 舍入、scale、尾块、保留码、长度、有限数 | 27量化断言、32主机拒绝例、私有核原5类错误、INT32逐位检查、冻结FP32容差 | tests/support/、host/、logs/b01/native_test.log |
| 3 两形状T1..8确定向量 | N3584/K1024和N1024/K3584各T1..8；全部输入/输出/seed/expected及SHA保存；追加真实layer0两权重T1/T8电脑回放 | vectors/b01/、vectors/b01_real/、vectors/model_source/ |
| 4 重复job与错误语义 | 相同/不同job、5次成功累计、1次错误后旧Y不消费/计数不增、恢复合法任务；主机拒绝不启动核 | tb/tb_w4a8_linear_v1.cpp、repeat_jobs向量、native/Csim/RTL postcheck |
| 5 原B2新尺寸覆盖 | 同一保存字节32案例PC回放通过；原B2全部16新尺寸Csim通过；新尺寸Cosim明确NOT_TESTED | baseline/b2/src/、baseline_test及baseline_csim receipts |
| 6 独立入口与开发负载 | run_selftest.ps1不依赖A/C/板卡；JSON负载含seed、shape、布局、字节量、容差、各域状态；ZIP解压重新构建且328文件hash一致 | run_selftest.ps1、docs/b01/workload.json、clean_repro.receipt.json |

当前核额外综合/XO通过，17个核参数与B3兼容；小边界加两种T1的25个RTL事务经本机链接恢复和真实输出回放通过，见RTL_RECOVERY.md。T8 RTL、新尺寸原B2 Cosim、真实权重Csim/Cosim、平台链接、ARM64和BOARD未测试。B04动态库尚未实现。
