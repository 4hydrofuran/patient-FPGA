# A12 PL模式与原Owner接口：无板进展及剩余项（2026-10-26）

已完成本轮PL模式候选的无板接线、目标验证、A53交叉构建和审阅包。**尚不能说只剩上板**：新短提示词仍未通过内容门槛，常驻交互SERVICE及真实应用请求路由仍未实现；板端故障恢复、独立安全释放、性能和最终验收均没有新增通过结论。

## 本轮修改

协调器现在留在原Owner所在的父进程，原生worker为其直接子进程；沿用原租约与两把锁的同一open-file-description。另设明确CPUProvider和BoardProvider，PC JSON不能构造Board权限；Board路径要求原Owner、注册root ARM64和原有live-source门禁。正常native退出只进入等待原Owner.finish，不由新协调器恢复平台或释放设备。

启动前提取原start_worker的资产、模型完整SHA与预算检查，逆向AST相同，并安排在完整BO待分配准入之前。原CMA/内存/温度、日志连续性、IRQ、148 BO/72权重/140591104字节、8192对齐、低2GiB和5000次硬上限保留。使用普通前缀和有界日志，没有新增长前缀诊断、全位置logits/状态转储或历史原件扫描。

模式默认严格；空闲边界才允许选择微批。故障立即撤销授权，保留旧unknown/DIRTY和失败输入身份；PC只有持有pidfd确认真实子进程终止后，才允许显式新输入开启严格窗。Board失败保持隔离，恢复必须在本任务外完成，再由具有新租约、完整原门禁及明确恢复范围的原Owner绑定新的严格窗。没有自动恢复、重试、旧请求重放或CPU回退。

取消先撤销共享页再等待日志锁。若取消发生在private_closed已核验之后，保留关闭ACK握手使native正常退出，但窗口仍判失败。构造器拒绝不合法历史时只关闭本次本地FD，保留DIRTY及原日志；反例由3个遗留FD改为0。以上均不构成物理释放证明。

## 无板验证

- 最终normal04与fallback04的实际Qwen CPU模型原件独立审计通过：正常微批/严格窗各2880次实际CPU计算，grant分别40/2880；token、文本、EOS、末位置logits、warm快照摘要及清理/END/回执/交付门槛与冻结基线一致。失败窗第5次claim被拒绝，旧unknown不清；没有完整中间状态或真实PL结果通过结论。
- 22项元数据/历史策略测试、6项原资产门禁root PC夹具、原Owner worker/finalization接口的PC进程/文件系统代理、取消先于日志锁、关闭握手取消、只读页观察、5项重定位夹具与构造FD反例通过。Owner测试的默认PL检查为显式夹具，不能作为真实板端恢复或释放。
- BEGIN完整记录fsync失败在Popen前拒绝；原DIRTY保留、重启拒绝。干净历史重开默认严格，候选故障锁存和旧输入拒绝保持。
- 新A53 unbound/bound候选后端和只读observer交叉编译通过，未执行。后端相对父件只有3处可逆预处理门禁变化，XRT/BO/sync/start/meta/Y/timeout/poison与数学不改；导出符号与原私有/公共版本表一致，ARM无测试入口，observer只导出一个只读函数。
- 原CPU/native数学DSO、量化对象和A53数学DSO按原SHA复用。历史契约保护、新版配置校验均exit0，旧DRAFT/BOARD NOT_TESTED不追认。

早期构建锚点错误、DrvFs审计镜像权限拒绝、构造FD反例和所有开发模型记录均保留。最终模型证据为normal04/fallback04；其后构造器只改本地拒绝路径，单独验证了旧/新源码的实际FD差值，没有把较早模型实验冒称当前所有行都重跑。

## 交付与后续

审阅包：`evidence/model_pl_A/20261026-pl-mode-v1/pl-mode-offline-review-v1.zip`，SHA `20d0d91830890b3d216dff66f06161b426b4b1f502ccc4f84888abb7b54f4fc5`，逐成员CRC/SHA回读通过。它依赖冻结仓库、原native/math/model及另审固定根路径布局，不是独立部署包，不含模型/sidecar/bitstream或安装恢复、上板执行脚本。具体A53文件、SONAME别名和缺件/篡改拒绝检查见BOARD_BUILD-v2-complete.json及RELOCATION_TEST.json。

原普通资源包SHA仍为`acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，将来首轮仍先运行它；不能直接用新候选替换基线。原失败、父包168文件、公共5契约及历史source/evidence保持性重新核对。

总审计将P0/P1离线准备与尚未完成项分别登记，见COMPLETION_AUDIT.json。三个短提示词仍为20/25、20/25、21/25，未采用。下一项可独立无板推进的是分析保留的8个失败ID并验证新候选，不能降门槛或修改原普通包；SERVICE必须单独设计与接线，三请求窗不代表可连续投入使用。

实际板端时延/CMA收益保持null，当前PC单样本不能推算“输入后几秒应答”。本轮不上板、不SSH、不恢复/释放、不推送。复杂设计、核心实现及验收未委派；DeepSeek未使用，实际模型/effort设置工具不可核实，记unknown。目标仍active。
