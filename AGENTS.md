# KV260 三人协作工程

本仓库根目录是 `D:\Patientqwen`。A 负责平台、运行时和最终集成；不代写 B/C 模块。
现有 `originalpatienqwen/`、`KV260Paper/`、`deliverables/` 只读，不纳入新工程 Git，不复制权重或凭据。

## 所有权

- A：`runtime/`、`quant/`、`platform/`、`scripts/release/`、`third_party/llama.cpp/`、`bench/runtime/`。
- B：`fpga/`、`reference/`、`bench/hw/`。
- C：`app/`、`cases/`、`quality/`、`bench/e2e/`、`paper/`。
- A0 仓库治理由 A 维护：根目录治理文件、`.github/`、`docs/adr/A-*`、`docs/status/A.md`、`docs/handoffs/A*`。
- `contracts/` 由 A 维护，A/B/C 同一内容哈希评审后才可冻结；无评审只能是 DRAFT。
- B/C 只写自己的 status、独立 handoff；A 不替他们签核，也不建立假评审。
- 仅 A 合并 main 或发布；本地规则不是托管平台强制权限。

## 技术及证据

Vivado/Vitis/HLS 固定 2026.1，完整 build 与平台以 `platform/toolchain.lock.json` 为准。
唯一板级主线为官方 kv260_base + 匹配 Linux/XRT。HLS .xo 由 B 交付，A 链接和板测。
原 8B 只保留为电脑教师/对照；端侧 Qwen2.5-0.5B-Instruct，24 层 MLP 为目标硬件覆盖。
整数同数学参考 bit-exact；PC 测试、Csim、cosim、布局布线、真实板测分开记录。
fpga_required 不静默回退；未测值用 null 并说明原因，不能用主机计数冒充硬件完成。
共同样例只用于契约互认，不是 B 的独立 golden，也不是 A2 量化导出器。

## 当前约束

用户于 2026-09-26 明确板卡 10 月 7 日以后才到；9 月 30 日 G1 真实板测不可达，保持 NOT_TESTED。
到板前仅做无需板卡的 A 任务。B/C 地址和远程 Git 未提供，不猜地址、不扫描网络。
账户、许可证、采购、供电改变、刷写/格式化和对外发布需另行人工确认。
板测先确认身份并由 A 发放唯一租约；本地分散锁不能构成跨三台电脑的排他锁。

## 模型使用

沿用用户全局路由：默认 gpt-5.6-sol / high，禁止 terra、medium；不因执行包建议而自动改模型。
不能核实当前实际模型时记录 unknown，不声称提示词已切换。
不自动创建子代理或代表 B/C 执行任务。

## 每阶段

先读契约、自己的 status 和最新 handoff。只实施当前阶段或已明确授权的无板工作。
先运行 `python scripts/release/check_contracts.py`，再跑修改相关测试。
写实际命令、退出码、日志/产物哈希、验证层级和失败项；不得标记没有证据的 PASS。
