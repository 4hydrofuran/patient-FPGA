# KV260 三人协作工程

## 当前生效规则：Qwen3.5 A-DESIGN-1.0（2026-10-02 用户授权）

本节覆盖下方历史规则中冲突的模型、分工、契约签核与日历要求；其余安全、证据、路径规则继续生效。下方旧规则保留供恢复旧工程，不能阻断新版默认实现。

- 当前入口为 `docs/PROJECT_STATUS.json`、`docs/DESIGN_GAP.md`、`docs/DECISIONS.md`、`docs/TEST_MATRIX.md`、`docs/AI_ASSISTANCE.md`。唯一主阶段提示词为 `docs/plan_qwen35/KV260_Qwen35_A_详细设计增强任务包_20261002/KV260_Qwen35_A_设计增强包_20261002/03_A_系统实现与验证_阶段提示词_措辞精简版.md`；同目录12为设计、13为导入/修复流程。旧任务包和archive仅留档，不混用。先读本角色阶段、公共接口、状态和最近失败，不递归读取其他成员工程；根据真实未通过项接续，不按日期推断、不重做已通过A00。
- 板端目标为 `Qwen/Qwen3.5-0.8B`，文本、非思考模式。revision/运行时commit须在A01实际审计后锁定；旧8B与0.5B原地保留，不能作为新模型验证。
- A负责新版完整默认系统：模型、默认计算与语音、病例评分、部署、实验和材料。新版代码使用 `system_qwen35/`、`modules/linear_A/`、`modules/voice_A/`、`config/qwen35/`、`platform/qwen35/`、`bench/qwen35/`。B/C候选分别使用 `modules/linear_B/`、`modules/voice_C/`，实际工程路径未知；不改旧B/C所有权目录。
- 新版契约基准是 `contracts/qwen35/` 及其中 `contracts.lock`，由任务包字节复制并校验。缺B/C签名或候选不阻断本地实现；旧 `contracts/` 草案不被改写为已签核。公共软件ABI不是旧B2核私有metadata；变更公共数学/协议须保存最小反例并显式修订，不可静默改动。
- 默认计算A、语音A；候选只按验收维护窗口选择。缺候选不下载、不回退；缺默认产物明确NOT_IMPLEMENTED，不能宣称系统已启动。
- 2026-10-03 用户本轮明确覆盖 A06：从指定 GitHub 接收 B 核，在 `hw/linear_B_received/<版本>/` 独立保存；A 只作 ABI/数值/证据验收，不另写 HLS 核、不合并 B 整仓。只有源码/XO/metadata/必需仿真闭环后才冻结 `hw/linear_A/KERNEL_SOURCE.json`；未接收状态必须 `accepted=false`。本轮 A06 使用 High，覆盖旧 A06 Extra High 要求；实际设置无法核实时仍记 unknown。
- 该轮后续分工：A07 由 A 实现 XRT BO、同步、核调用、meta 与安全恢复并链接平台；不等待 B 完整调用库。B 维护计算核及其缺件/缺陷修复。A11 实板验收、A12 模型真实消费 PL 结果仍独立，不用 PC/Csim 代替。上述覆盖旧 RA01 的 XRT 所有权仅限新版 Qwen3.5 路线，历史代码原样保留。
- 2026-10-03 后续用户明确“不让B弄了，你自己补全”：A接手本次A06剩余修复与接收补测，不再以等待B修工具为前置。原B交付保持只读，A修订存独立工具/派生文件并标维护者；不另造替代核、不更改公共数学或抹去失败。provider继续记录B，不代B签核。许可证官方重新绑定仍由用户完成，实际未运行的本地Csim不因该授权自动通过。
- 固定2026.1与官方KV260路线，复用工具/SDK，不重装、不全局升级依赖、不用开发机 `-march=native` 交叉构建A53。安装失败先定位。
- 每阶段分开PC/Csim/Cosim/综合/实现/交叉构建/BOARD；未测NOT_TESTED、数值null。不得伪造模板回退、硬件计数、医学审核、波形、功耗和论文录用。保留失败，不删例或放宽门槛。
- 必需无板工作先完成。10月15日仅计划实板起点，实际到板且前置通过才执行；10月30日交付、31日缓冲。B/C候选计划10月14日电脑包、22日板测包，日期不是完成证据。
- 刷写先确认准确设备、备份、恢复并获专项授权；登录、采购、录音/真实音频授权由用户处理。音频默认不长期留存，不输出令牌、密码、私钥、许可证正文，不擅自推送远程。
- 历史项目模型请求为GPT-6 Astra / Standard；用户最新会话级模型路由优先，不自动切换设置。阶段建议A04/A05/A07/A12采用Extra High（xhigh），其余阶段High（含2026-10-03重新指定的A06）。不启用子代理；不能读取实际设置时记unknown，不声称已经切换。不修改B/C设置。
- A-DESIGN-1.0只补当前阶段P0/P1缺口；P2列为可选，不清空历史PASS。`design/qwen35/`仅为设计规格/推导，不代表运行时已消费配置，不代表板端可用内存或性能；实际BOARD保持NOT_TESTED/null。公共契约与fixtures保持字节不变。
- 每阶段先跑旧 `scripts/release/check_contracts.py` 作为历史保护检查，再跑 `scripts/release/qwen35_config.py` 的新版校验与阶段测试。历史require-frozen不作为新系统开工门槛。

## 历史规则（冲突项以上方为准）

本仓库根目录是 `C:\Patientqwen`，WSL 源码路径为 `/mnt/c/Patientqwen`。A 负责平台、运行时和最终集成；不代写 B/C 模块。
2026-09-26 用户授权整体迁移；`D:\Patientqwen` 是迁移前保留副本，不再用于开发。运行中的项目 WSL 位于 `C:\WSL\KV260-A-2204`；仓库 local 下原位置的 VHD 仅为冷备份，不得注册或启动第二个同名实例。
现有 `originalpatienqwen/`、`KV260Paper/`、`deliverables/` 只读，不纳入新工程 Git，不复制权重或凭据。

## 所有权

- A：模型运行时/S1 CPU/激活量化/图接入、平台配套；保留 `runtime/`、`quant/` 的既有审计工具、`platform/`、治理检查脚本及 `bench/runtime/`，以下细分目录例外优先。
- B：`fpga/`、`reference/`、`bench/hw/`。
- C：`app/`、`cases/`、`quality/`、`bench/e2e/`、`paper/`。
- 2026-10-01 用户授权 RA01 正式重排：B 唯一维护 `runtime/xrt_linear/`（BO、sync、调用、meta、超时隔离）、`platform/b_kernel/`（B核链接）、`bench/hw/`（独立板测）；C 唯一维护 `quant/exporter/`（生产 W4A8 sidecar）、`scripts/release/product/`（安装/恢复/发布编排），并保留应用与评测职责。这是本仓库路径约定，不代表已获 B/C 工作目录或接收确认；不搬走旧代码。
- A 不再是生产导出器、算子级 XRT 和应用打包的实现作者。旧 A-vadd 主机/链接仅作平台 smoke 参考，不扩展为第二套 W4A8 XRT 库。
- A0 仓库治理由 A 维护：根目录治理文件、`.github/`、`docs/adr/A-*`、`docs/status/A.md`、`docs/handoffs/A*`、`docs/replan_20261001/`（用户执行包原样留档）。
- `contracts/` 由 A 维护，A/B/C 同一内容哈希评审后才可冻结；无评审只能是 DRAFT。
- B/C 只写自己的 status、独立 handoff；A 不替他们签核，也不建立假评审。
- 仅 A 合并 main 或发布；本地规则不是托管平台强制权限。

## 技术及证据

Vivado/Vitis/HLS 固定 2026.1，完整 build 与平台以 `platform/toolchain.lock.json` 为准。
唯一板级主线为官方 kv260_base + 匹配 Linux/XRT。B交付HLS/XRT算子库，负责本核离线链接和独立板测；A负责平台/G1、模型接入和兼容复核，不代跑全部B/C实验。
原 8B 只保留为电脑教师/对照；端侧 Qwen2.5-0.5B-Instruct，24 层 MLP 为目标硬件覆盖。
整数同数学参考 bit-exact；PC 测试、Csim、cosim、布局布线、真实板测分开记录。
fpga_required 不静默回退；未测值用 null 并说明原因，不能用主机计数冒充硬件完成。
共同样例只用于契约互认，不是 B 的独立 golden，也不是 A2 量化导出器。

## 当前约束

最新计划为 2026-10-01 至 10-07 无板，最早 10-08 上板，10-30 交付、10-31 缓冲；计划不是证据。9 月 30 日 G1 未通过的历史不追认，BOARD 继续 NOT_TESTED。
到板前仅做无需板卡的 A 任务。B/C 地址和远程 Git 未提供，不猜地址、不扫描网络。
账户、许可证、采购、供电改变、刷写/格式化和对外发布需另行人工确认。
板测先确认身份并由 A 发放唯一租约；本地分散锁不能构成跨三台电脑的排他锁。

## 模型使用

本项目按用户 2026-10-01 明确要求：A 固定 GPT-6 Astra / High / Standard；B/C 按重排包各自固定 GPT-6.1 Sol / High / Standard。覆盖本项目旧 Sol 路由；不自动切模型、强度、速度，不购买 API、不启用自动子代理。文本或配置不能证明当前会话已切换。
不能核实当前实际模型时记录 unknown，不声称提示词已切换。
不自动创建子代理或代表 B/C 执行任务。

## 每阶段

先读契约、自己的 status 和最新 handoff。只实施当前阶段或已明确授权的无板工作。
先运行 `python scripts/release/check_contracts.py`，再跑修改相关测试。
写实际命令、退出码、日志/产物哈希、验证层级和失败项；不得标记没有证据的 PASS。


## 用户最新模型分工（2026-10-25，覆盖旧模型路由与禁止委派的冲突项）
- 复杂、重要、含糊、多步骤、设计、调试、评审、验证及跨文件任务使用 GPT；不启用 Fast 或 Ultra。
- 简单、琐碎、范围明确且可独立验收的格式转换、文本提取、分类、重复文档整理及小型机械修改，优先通过 deepseek-delegate MCP 的 call_deepseek_sub_agent 调用 DeepSeek。
- 只发送完成子任务必需的最小文本，不发送凭据、许可证、真实患者资料或整仓库。DeepSeek 仅返回文本/补丁，由 GPT 检查并应用；不授予文件或命令执行权限。
- 不委派公共数学/ABI、HLS/XRT核心逻辑、架构决策、医学判断、证据验收或对外发布。发现复杂性即交回 GPT。
- 若 MCP 不可用或缺少密钥，明确报告未使用 DeepSeek，不伪称调用成功；必要工作由 GPT 继续。
