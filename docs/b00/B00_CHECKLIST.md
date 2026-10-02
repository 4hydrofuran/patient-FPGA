# B00 完成清单（2026-10-02，Asia/Shanghai）

工程验收：PASS。独立检查无需 A 运行时、病例或 C 语音服务；历史与新增证据分离。
客户端 GPT-6.1 Sol / High / Standard 要求已记录，但实际设置无法由本地文件核实，client_setting_verified=false。

| 原任务要求 | 完成内容 | 证据与边界 |
|---|---|---|
| 1. 保留 B2、新开计算优化分支 | 新增独立 b_qwen35；分支 b/qwen35-compute；B2/B3 冻结ZIP备份、CRC及SHA校验 | reports/preservation.receipt.json；旧工程不改 |
| 2. 核对新尺寸与公共规范 | N3584/K1024 与 N1024/K3584；T1..8；数学和布局比较完成 | docs/b00/INTERFACE_AUDIT.md；新形状执行归B01 |
| 3. 标准 C 模块边界 | 原样导入公共头文件/量化契约/锁；六个函数C11/C++17类型检查通过；私有meta尺寸/偏移检查通过 | contracts/ 与 tests/interface/；未实现动态库，归B04 |
| 4. 独立 harness、seed、错误用例 | 继承dense INT64参考与HLS TB；公共字节样例回放；非法W4/短长度不改Y、不增计数；旧full与B2对照复跑通过 | run_b00.ps1、tests/numerical/、tb/、logs/、reports/；新负例规划归B01 |
| 5. 单一优化主线 | 保留32-lane，先新形状正确性，再权重复用/双缓冲/调用开销；无并行重写 | docs/b00/OPTIMIZATION_BACKLOG.md |
| 6. 规则、状态、报告 | 建立本地AGENTS、PROJECT_STATUS、交接与完成报告；记录固定助手选项要求 | 客户端实际选项未核实；不宣称由文件完成了设置切换 |

核源码、golden、主testbench和HLS配置与继承B3字节相同；compare_b2.cpp只改include到本包baseline，未改核ABI、数值顺序、错误语义或Cosim depth。
