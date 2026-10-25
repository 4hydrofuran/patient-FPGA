# 普通资源探测无板准备报告

状态：PC_PREPARED_UNBOUND；BOARD NOT_TESTED。没有板卡连接、部署或恢复，新增PL调用0，CMA改善和板端时延null。

最终包为`bundle-v2.zip`，清单为`bundle-v2/manifest.json`，记录为`PACKAGE-bundle-v2.json`。完整交接见 [A12无板交接](C:/Patientqwen/docs/handoffs/A_A12_RESOURCE_PROBE_PREBOARD_20261025.md)。

## 实现

新增A私有policy、case、observer、plan-only入口和可复现准备工具；另有Linux控制测试及真实x86 CPU流程验证工具。源文件快照在`source/`。从v3冻结包独立派生，不修改父包或暂停CMA候选。

仅R0/warm/hit三请求；旧107/70/37-token输入；所有重型诊断关闭。完成数、权重和BO几何仍使用原验收约束；前缀完整性和实际PL结果核验留在未改字节的原生库。新增观察边界保留原资源阈值和前缀规划余量，有界记录，发送前拒绝，失败锁存不自动恢复。

板端控制器保持UNBOUND拒绝，剔除旧顶层可执行控制入口和旧preflight身份，不附计算授权、传输助手或执行驱动。它需要未来新鲜审查和单独绑定。

## 命令与结果

以下在`C:/Patientqwen`执行。WSL命令均指定现有`KV260-A-2204`，没有创建/注册另一实例。

| 命令 | 退出码 | 实际结果与范围 |
| --- | ---: | --- |
| `python scripts/release/check_contracts.py` | 0 | 历史PC静态保护PASS，DRAFT保持 |
| `python scripts/release/qwen35_config.py` | 0 | 新版配置PASS；后端PRESENT_UNVERIFIED，BOARD未测 |
| `python -B platform/qwen35/a12/resource_probe_prepare.py` | 0 | 初版bundle-v1及ZIP准备完成 |
| `python3 -B platform/qwen35/a12/test_resource_probe.py --evidence evidence/model_pl_A/20261025-resource-probe-v1/pc-tests-01` | 0 | 初版18项PC控制测试通过 |
| `python3 -B platform/qwen35/a12/resource_probe_native_pc.py --evidence /mnt/c/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/native-PC-01` | 0 | 初版实际CPU原生流程通过，未测PL |
| `python -B platform/qwen35/a12/resource_probe_prepare.py --destination evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2` | 0 | 最终bundle-v2准备；修正旧计时cache标签 |
| `python3 -B platform/qwen35/a12/test_resource_probe.py --evidence evidence/model_pl_A/20261025-resource-probe-v1/pc-tests-02 --bundle evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2` | 0 | 20项PC控制测试通过 |
| `python3 -B platform/qwen35/a12/test_resource_probe.py --evidence evidence/model_pl_A/20261025-resource-probe-v1/pc-tests-03 --bundle evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2` | 0 | 最终21项通过，新增禁止板端/进程副作用的包隔离导入验证 |
| `python3 -B platform/qwen35/a12/resource_probe_native_pc.py --bundle /mnt/c/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2 --evidence /mnt/c/Patientqwen/evidence/model_pl_A/20261025-resource-probe-v1/native-PC-02` | 0 | 最终实际CPU流程通过，普通末位置输出一致、自然EOS与内容检查通过、无原始诊断、worker exit0 |

控制测试只用明确的PL/owner替身；真实模型测试只运行x86 CPU。它们不代表ARM原生执行、真实PL/CMA或故障恢复验证。原生ARM程序及HLS/XO/位流均未重编；既有交叉构建证据按原范围保留。

最终普通模型比较不含完整内部混合状态重验，该项NOT_RETESTED；最终数值与性能总验收未完成。真实CPU计时保存在native-PC-02，不能换算A53或写成10秒板端目标通过。

## 完整性与历史

BASELINE.json冻结父包清单与契约长度/SHA；STATIC_REVIEW.json确认168个父文件、5个契约文件不变，46个关键运行载荷相同，正常释放/恢复代码段逐字节不变，ZIP CRC通过。未删除原证据或旧包。

本轮实现验证命令均通过；一次只读环境探查在WSL找不到rg及所猜的pc04本地库路径而退出1，未安装依赖，改用既有BUILD记录和实际进程maps定位库。不是模型或板端失败，不改写历史测试状态。

实际模型设置无法独立核实，记unknown；未委派公共数学/ABI、XRT、架构或证据验收。本轮没有需要独立机械委派的子任务，未调用DeepSeek。
