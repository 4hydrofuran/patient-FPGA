# B00 完成报告与接续清单

日期：2026-10-02，Asia/Shanghai。工作目录：`D:\KV260-project-HLS\b_qwen35`。
分支：`b/qwen35-compute`，基线提交 `ae977f59ca0629f81e7ca8d4c7370984ca5407e1`。
结论：B00 接续与独立测试工程门槛 PASS；客户端 Sol/High/Standard 实际选项未核实，已记录为待确认备注。

## 清单

独立检查无需 A 运行时、病例或 C 语音服务；历史与新增证据分离。
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


## 改动路径

- `AGENTS.md`、`README.md`、`PROJECT_STATUS.json`：范围、入口与分域状态。
- `src/`、主testbench、golden、`hls_config.cfg`：从B3原样继承；`tb/compare_b2.cpp`仅改头文件路径到本包`baseline/b2/src/`，自带旧核对照。
- `contracts/`、`fixtures/`、`docs/plan_qwen35/`：原样公共规格、手算字节与计划副本。
- `run_b00.ps1`、`tests/interface/`、`tests/numerical/`：独立电脑检查；`run_b3.ps1`仅调整baseline路径到本包。
- `docs/b00/INTERFACE_AUDIT.md`、`test_plan.json`、`OPTIMIZATION_BACKLOG.md`、`B00_CHECKLIST.md`：接口、seed/负例和唯一主线。
- `evidence/history/`：B2/B3冻结ZIP、B3原报告/清单、B2新旧清单和保护指纹。
- `reports/`、`logs/`、`docs/handoff/HANDOFF.md`：本轮证据和交接。

## 执行与退出码

独立入口：`powershell -NoProfile -ExecutionPolicy Bypass -File .\run_b00.ps1`，在上述工作目录执行，最终退出码0。

| 检查 | 执行方式 | 最终退出码 | 结果 |
|---|---|---:|---|
| C头文件 | gcc -std=c11 -Wall -Wextra -Werror -pedantic -fsyntax-only tests/interface/header_probe.c | 0 | PASS |
| C++与私有meta | g++ -std=c++17 -Wall -Wextra -Werror -pedantic -fsyntax-only tests/interface/header_probe.cpp | 0 | PASS |
| 公共固定字节 | fixture_replay.exe | 0 | 3事务、32输出检查；错误不改Y/成功计数 |
| 继承native全回归 | run_b3.ps1 -Target native | 0 | 21事务、75963整数部分和、7712浮点输出 |
| 旧B2同输入对照 | run_b3.ps1 -Target baseline | 0 | 15合法case通过 |
| task package/契约锁 | 32项文件SHA + 锁映射hash校验 | 0 | PASS |
| B3历史证据 | 8项清单hash + 7份收据输入hash/退出码 | 0 | PASS |
| 历史保护与备份 | 51文件前后hash、2个ZIP复制SHA与CRC | 0 | PASS |
| 干净目录独立复现 | 仅从B00源码包解压后run_b00.ps1 | 0 / PASS | 0 / PASS |

首次fixture_compile退出1（collect2/CreateProcess辅助程序路径问题），不是数值失败。干净重建还发现Windows PowerShell模块路径、UTF-8脚本缺BOM和旧baseline头文件外部路径三项可复现问题；已分别明确加载本机工具模块、保留UTF-8 BOM、改为本包baseline include。失败日志/收据保存在 evidence/b00/attempt_first 和 clean_attempt_first/second/third；未删除失败记录，未改编译器安装或全局环境。

## 分域结果

PC（B00接口/固定样例/继承回归）：PASS。旧B3 Csim/综合/Cosim/XO：历史PASS，原样留存，本轮未重跑。
新模型两种形状PC/Csim/Cosim、布局布线、ARM64、BOARD、模型质量、板端时延和功耗：NOT_TESTED。
公共动态库：NOT_IMPLEMENTED（B04）；只完成声明兼容检查。客户端指定选项：UNVERIFIED。

## 未决项与下一步

1. 客户端实际模型/思考强度/速度无法由工程文件确认；目标选项已写入规则和状态，不宣称已锁定。
2. 原b2_manifest记录较早，保留它但本轮B2源码核对以20260929冻结manifest为准。
3. B01调整新形状T8的X/Y仿真窗口：两种目标最大28672元素；当前4864不足。若验证全部容量T8，需要38912元素。
4. B01按 `0x20261002 + shape_index*256 + T` 固定seed，生成gate/up与down的T1..8，使用独立dense参考；加舍入、A8 -128、非有限/非正scale与padding负例。
5. 真实模型revision和权重未获取，后续固定revision/文件hash；无需A运行时、病例或C语音才能推进。
6. B03权重复用/双缓冲；B04完整C ABI库、XRT/超时生命周期、xclbin链接与ARM64构建；板测按前置门槛进入。

本次未改旧工程、未修改核数学/ABI、未运行Vitis或上板。新规则为项目本地规则，不宣称完成额外的托管治理迁移；已安装技能未修改。
