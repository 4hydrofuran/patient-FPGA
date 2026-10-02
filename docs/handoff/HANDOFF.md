# B00 交接（2026-10-02）

工程目录 D:\KV260-project-HLS\b_qwen35；分支 b/qwen35-compute。B00 工程验收PASS，客户端指定选项未核实。
原 b2_hls/b3_hls/handoff 未修改；源码/参考/配置与B3字节一致。冻结ZIP已复制到 evidence/history 并完成CRC/SHA校验。
run_b00.ps1 通过公共头文件C11/C++17、固定字节样例/错误语义、旧full native与B2同输入对照。
所有新Qwen3.5形状、Vitis重跑、实现、ARM64、BOARD均未执行。
首轮fixture链接失败因MinGW辅助程序PATH缺失；原记录在 evidence/b00/attempt_first，已用进程局部PATH修复并恢复环境。
下一步B01：同时扩X/Y的Cosim depth与TB缓冲，生成两种新形状T1..8及新公共数值负例；不得覆盖历史报告。
真实模型revision/权重还未获取，平台与板卡状态未知。动态库六符号只完成声明检查，完整实现归B04。
