# A10 工作进程退出边界

## 收尾后PC补测（2026-10-23）

新增`test_idle_integration_pc.py`贯通真实构造器、日志、租约双锁、PC子进程waitpid与释放编排；板命令和观测全部显式替身，不加载XRT。8项新增、相关81项Linux方法exit0，首次夹具排序错误保留。最新静稳修复已封入独立v4候选，无review、未部署；没有新的COM5/SSH访问。A10仍未通过，下一板测需要新明确授权。报告`evidence/board_platform/A10_20261023_controller_integration_pc_v1/REPORT.md`，下方是历史窗口快照。

## 最新边界（2026-10-23，本轮已收尾）

真实irq2启动后，控制器在第一次PL命令前因日志字段冲突/进程扫描竞争停止，native worker未运行。仅收尾经专项授权并独立核验；非空载或计算后释放PASS。最新完整相关Linux73方法通过，含实际日志/PS节点识别/有界pre-PL静稳；静稳修复未打包或上板，不能重放旧v1/v2/v3。具体见`evidence/board_platform/A10_20261023_isolated_idle_v1/FINAL_REPORT.md`。下方62方法/尚待启动均为先前快照。

## 接续实现（2026-10-23，后续窗口）

下方为初次组件交付时的历史快照，原“尚未实施”已由 `isolated_idle_worker.py`、`isolated_idle_trial.py`、`isolated_idle_policy.py` 及两个隔离启动入口补齐。新的worker只绑定七个空载XRT函数，没有BO或RunStart路径；管理方不导入native库，持有独立租约与双锁并隔离GDM。测试替身只在PC使用，不随包部署。

完整编排与已有门禁Linux62方法通过；Windows54方法中50通过/4个POSIX跳过。新原始证据根 `evidence/board_platform/A10_20261023_isolated_idle_v1/`；新包已root独立暂存并验哈希，BOARD生命周期尚未运行，计算后释放仍未证明。后续实际结果见 `docs/handoffs/A_A10_ISOLATED_IDLE_20261023.md`，不能复用历史授权或把PC通过当板测。

## 初次PC组件交付快照（保留原边界）

2026-10-23；不改 HLS、数学、XRT 库或内核；不重放历史 N32。

## 已实施

- `xrt_worker_boundary.py`：以新解释器进程启动经审阅的 worker，关闭继承 fd，不在管理进程导入 XRT；保留 `Popen` 实体，用 `wait` 确认确切子进程正常退出。仅接受本窗口 boot/lease/request/manager/worker 身份完全一致的无计算正常关闭回执。管理方必须直接启动实际解释器，不能使用另起子进程的 Windows venv redirector、后台 shell 或 daemon。
- 输出/错误写新建文件，不用可能塞满的未读管道。工作进程超时、非零退出、回执缺失/错配、日志失败均调用管理方的不可返回隔离函数。不强杀、不重试、不自动释放租约或双锁。已超时的实例后续即使退出也不能重新变成成功。
- `accelerator_release_gate_v2.py`：在确切退出后检查全进程设备 fd 与 VMA（含 deleted）、ZOCL 引用严格整数 0、同 boot、完整扫描、连续内核门禁为真。缺字段、权限不足、进程/表项变化、未知引用或旧快照都拒绝。不得解除原内核门禁的失败锁存。
- 卸载预检通过不等于已经卸载；本组件没有 PL/module、重启或计算命令。一个普通 `/proc` 快照也不是原子排他锁，不能替代管理方租约/双锁、图形服务与其他消费者隔离；特别的设备别名须明确纳入。

## 尚未实施/未验证的接入

本次不是完整 `run_refcount_step5.py` 的替换品。以下工作仍需在独立新入口实施与审阅，不能导入/执行证据目录里的历史 executor：

1. 为无计算 native worker 实现固定参数协议；只做 XRT 初始化/已授权上下文打开关闭，不实现 BO 或 RunStart 分支。XRT 只能由该 worker 加载。
2. 为新窗口实现实际 boot、来源哈希、租约、双锁、其他消费者隔离的 `guard`。管理进程持续持锁，不能把隔离异常当普通异常退出；`quarantine` 必须保留管理进程与锁。测试中的异常仅用于 PC 替身，不能照搬上板。
3. 接入既有连续 `MinimalGate` 与前后完整日志检查，提供新鲜扫描与实际 `/sys/module/zocl/refcnt`。先确认新正常 1036 恢复资产，禁止复用 1015 哈希或已消费的 boot/lease/PID。
4. 经明确授权后，才在新干净 irq2 窗口做一次无计算打开/关闭/进程退出/卸载/默认恢复。当前 `BOARD=NOT_TESTED`。若需要计算后验证，必须单独明确范围；无计算通过不能代替计算后通过。

## worker 协议

管理方追加 `--a10-boundary-request <JSON>` 和 `--a10-boundary-result <新路径>`。请求包含 `protocol=a10-isolated-idle-worker-v1`、`boot_id`、`window_id`、`lease_sha256`、`request_sha256`、`manager_pid`。

worker 在普通关闭全部句柄后，以独占新建文件写回同一身份，增加实际 `worker_pid`、`status=NORMAL_CLOSED_NO_COMPUTE`、布尔 `normal_handles_closed=true`、整数 `real_submissions=0`、整数 `explicit_bo_allocations=0`，然后正常退出。只有该退出真实被管理进程收割，才进入释放预检。回执本身不证明 native 动作；未来 worker 的逐步 XRT 日志仍必需。

## PC 验证

Windows 新组件 18 方法：16 通过，2 个 POSIX 锁方法明确跳过。WSL Linux 同组件全部 18 方法通过；连同既有内核门禁、最小门禁和捕获测试共 44 方法通过，退出 0。包含真实 PC 子进程、Linux flock 不继承及超时双锁保留、收到的实际残留 VMA 快照拒绝卸载。

首轮 Windows 退出 1：venv redirector 的 PID 与实际解释器不同，身份检查正确拦截；保留失败，测试改为直接启动 `sys._base_executable`，未放宽生产身份条件。测试替身没有 XRT/设备访问。

证据：`evidence/board_platform/A10_20261023_peer_intake/worker_boundary_pc_01.json`（失败）、`worker_boundary_pc_03.json`、`worker_boundary_wsl_02.json`。未作性能收益声明。
