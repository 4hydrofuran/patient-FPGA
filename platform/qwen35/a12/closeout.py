"""Record only observed A12 01-05 results; preserve A11 and all failed receipts."""
import datetime
import json
from pathlib import Path
from common import ROOT,EVIDENCE,sha,save


def prepend(path,text):
    data=path.read_bytes().decode('utf-8');first,rest=data.split('\n',1)
    path.write_bytes((first+'\n\n'+text+'\n'+rest).encode('utf-8'))


def main():
    checks=['contracts_01','config_01','baseline_01','pc_build_02','pc_build_04','arm_build_01','arm_build_02',
            'graph_02','control_01','supervisor_01','adapter_02','window_01','native_gate_01',
            'canonical_02','trace_audit_01','session_01','bundle_tests_01','package_01','package_selftest_01']
    for name in checks:
        r=json.loads((EVIDENCE/(name+'.json')).read_text())
        assert r['exit_code']==0,name
    failures=[]
    descriptions={
        'pc_build_01':'Missing OpenSSL dev header. Reused stable SHA256 C ABI already used by A05; no package install.',
        'pc_build_03':'Compilation succeeded; post-build receipt refused existing PC_BUILD.json. Preserved failure and changed later receipt naming to per-version.',
        'graph_01':'Consumer verification after in-place GLU observed overwritten input. Fixed to verify input before and confirm execution after; original case and full matrix passed unchanged tolerances.',
        'adapter_01':'Wrong existing Python venv lacked jinja2. Used existing system Python with original installed jinja2; no installation.',
        'canonical_01':'Actual original A05 model run passed; new postprocessor expected absent state_fingerprint key. Reused saved raw logits/state and compared byte-exactly without rerunning or weakening validation.'}
    for name,description in descriptions.items():
        r=json.loads((EVIDENCE/(name+'.json')).read_text());assert r['exit_code']!=0
        failures.append(dict(receipt=name+'.json',exit_code=r['exit_code'],resolution=description))
    save(EVIDENCE/'FAILURES.json',dict(failures=failures,discovery_errors='See BASELINE.json inspection_failures',
        samples_deleted=False,tolerances_relaxed=False,board_actions=0))
    package=json.loads((EVIDENCE/'PACKAGE_CHECK.json').read_text())
    summary=dict(status='PASS_A12_01_05_PC_AND_CROSS_BUILD_BOARD_PENDING',
        steps={'01':'PASS_PC_BASELINE_FROZEN','02':'PASS_CROSS_BUILD_NOT_ARM_EXECUTION',
               '03':'PASS_DERIVED_BUDGET_NOT_BOARD_QUALIFICATION','04':'PASS_PC_IMPLEMENTED_CANDIDATE',
               '05':'PASS_PC_TESTS_AND_STATIC_PACKAGE'},
        next_step='06_FRESH_BOARD_PREFLIGHT_AND_SAME_BOARD_S1',
        A12_overall='IN_PROGRESS_NOT_BOARD_ACCEPTED',BOARD='NOT_TESTED',
        A11='PASS_WITH_LIMITATIONS_PRESERVED',contract_changed=False,B_core_changed=False,
        model_settings='unknown',board_connections=0,board_writes=0,device_submissions=0,
        package_manifest_sha256=package['manifest_sha256'],candidate='release/a12_preboard_20261023_v1',
        controls=dict(cases=31,checks=764),linux_supervisor_tests=7,app_tests=4,window_owner_tests=4,
        bundle_negative_tests=4,graph_cases=8,graph_and_canonical='BIT_EXACT_LOGITS_AND_HYBRID_STATE',
        explicit_full_model_BO_charge_derived_bytes=140591104,full_model_physical_peak_bytes=None,
        hardware_global_count=None,PL_DDR_bandwidth=None,board_speedup=None,
        passed_receipts=checks,failures='FAILURES.json',committed=False,pushed=False)
    save(EVIDENCE/'SUMMARY.json',summary)
    inputs=[ROOT/'artifacts/qwen35-0.8b/source/chat_template.jinja',ROOT/'models/model.lock.json',
            ROOT/'quant/qwen35_tensor_map.json',ROOT/'models/sidecar_A/qwen35-v1/manifest.json']
    save(EVIDENCE/'FINAL_INPUTS.json',{str(p.relative_to(ROOT)):sha(p) for p in inputs})
    text='''# A12 01—05 无板准备报告（2026-10-23）

结论：**01—05 的 PC 实现、验证及交叉构建完成；A12 整体仍在进行，BOARD NOT_TESTED。**

## 产物与通过范围

| 步骤 | 结果与证据 |
|---|---|
| 01 起点/门槛 | A11 456 项封存核对、修改前件与差异保存；模型/契约/输入/容差冻结，见 BASELINE.json、ACCEPTANCE.json、FINAL_INPUTS.json |
| 02 ARM64 | 复用 2026.1 SDK，在新队列目录从最终 A05 源码重建 llama；最终模型、CPU 库、XRT2.18 候选及四个运行库共 7 产物通过 ELF/ABI/ISA 审计。见 ARM_BUILD_FINAL.json；没有 ARM 执行 |
| 03 预算 | 单投影/单 MLP/24 层分别冻结；T8、128 prompt/2 output 上界为 17/51/1224 次，权重加载 1/3/72 次；显式 BO charge 2162688/6062080/140591104 B。见 RESOURCE_CALL_BUDGET.json；这不是板端物理内存证明 |
| 04 接入 | 精确 72 张量真实图回调接私有 Route；未选部分仍为 S1 W4A8。CPU/PL 内部符号隔离；父许可、双锁/新租约候选、保留隔离、无 kill 关闭和应用适配器已实现 |
| 05 验证 | 8 个真实 PC 模型场景：S1、单投影、单 MLP、24 层、T1/2/4、丢弃输出反例。成功比较 logits/混合状态逐位一致，另与原 A05 v8 逐位一致；反例被拒绝。见 graph-v2/SUMMARY.json、CANONICAL_COMPARISON.json |

PC_MATH_DOUBLE 调用真实 CPU 数学来验证路由和图消费者，不冒充 FPGA_REAL。关联 trace 包含实际输入/输出 SHA、shape/stride、job、epoch/执行号与消费者节点；T8 全图 216 次、T1 720 次、T2 432 次、T4 288 次均有消费证据。硬件全局计数为 null。

31 个 XRT 控制替身场景/764 检查覆盖原故障矩阵、新调用上限、72 常驻句柄与第 73 次加载拒绝；不是数值或 BOARD 证明。Linux 真实子进程/锁/取消 7 方法、应用身份/状态 4 方法、窗口双锁/租约所有权 4 方法、嵌套清单/篡改/假 BOARD 拒绝 4 方法通过。另实际 C++ SO_PEERCRED/borrowed flock 与 Python manager 联调通过。

实际 PC native 同进程 reset、换输入/病例重放、R1 拒绝、权重不重复加载通过；首 token 后 SIGUSR1 取消得到 CANCELLED、部分输出不可交付、混合状态清空并正常退出，未 kill。见 SESSION_REGRESSION.json、CANCEL_REGRESSION.json。

## 候选与边界

候选 `release/a12_preboard_20261023_v1/` 包含 ARM 库/进程、来源、派生代码、固定 B 位流、契约与证据。主任务包实际 verify_bundle 和包内 selftest 均通过；manifest SHA256 见 PACKAGE_CHECK.json。禁用配置保留 allow_device_access=false，授权未内置，未覆盖全局默认 manifest/selection。原模型和 sidecar 仍在原处，没有复制进包。

Window/OwnedWorker 提供后续平台入口所需的所有权/许可部件；真实 PL 准备/默认恢复编排、板端启动/资源与完整模型生命周期仍须在 06 以后联调验收。本次的 PC 组件测试不代表 BOARD 释放、超时恢复或平台准备已通过。

完整模型物理峰值、XRT 隐式分配、同板 CPU 对照、ARM 执行、PL 消费/数值、整体速度和收益均未测。PSS/CMA/BO 不相加，算子 1e-4/1e-5 与整图 0.002/0.0002 阈值未放宽。没有追加 HLS 核或 P2 优化，没有改原 B 交付、公共数学、内核、系统库、默认启动或旧 A11。A11 的既有 PASS_WITH_LIMITATIONS 保留。

## 失败保留与修复

所有失败见 FAILURES.json 和对应 command receipts：缺开发头、重复收据名、原地 GLU 观察时点、误用 Python venv、旧输出缺新增诊断字段。旧源码/失败包/graph-v1/原日志均保留；各问题已定位并复核。没有通过删除样本、修改容差或假造硬件结果收口，没有超过 10 分钟仍未解决的重大阻塞继续执行。

所有实际 argv、退出码、完整输出在本目录 *_01.json/*_02.json 等收据；编译细节保存在队列工作目录 stdout/stderr，ARM_BUILD_FINAL.json 给出真实目录及产物哈希。PC 模型诊断时间不作为性能数据。

下一步仅第 06 步：新鲜板端身份/内核/资源与同板 S1 验证，满足预算后再开第 07 步。旧 boot/PID/租约/窗口不重放。本轮板端连接/写入/计算均 0；无提交/推送，实际助手设置 unknown。
'''
    (EVIDENCE/'REPORT.md').write_text(text,encoding='utf-8')
    path=ROOT/'docs/PROJECT_STATUS.json';status=json.loads(path.read_text(encoding='utf-8'))
    status={'role':status['role'],'a12_preboard_20261023':dict(summary,report='evidence/model_pl_A/20261023-preboard-v1/REPORT.md'),**status}
    status['stage']='A12';status['stage_status']='IN_PROGRESS_PREBOARD_01_05_COMPLETE_BOARD_PENDING'
    path.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    note='2026-10-23 A12 01—05：PC 实现与交叉构建完成，BOARD NOT_TESTED。原 A11 PASS_WITH_LIMITATIONS 保留；下文 A12 未开始等为历史快照。8 个模型图场景与原 A05 v8 对照的 logits/混合状态逐位一致，丢弃输出被拒绝；31 控制场景/764 检查、Linux/应用/窗口/包门禁通过，最终 ARM64 候选和静态包完成。完整模型 BO 140591104B 仅推导；硬件数值、物理峰值、速度仍 null。失败保留，默认配置未启用；下一步 06。报告 `evidence/model_pl_A/20261023-preboard-v1/REPORT.md`。'
    for relative in ('docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/status/A.md'):
        prepend(ROOT/relative,note)
    prepend(ROOT/'docs/DECISIONS.md','2026-10-23 用户授权执行 A12 01—05 并允许必要板端连接/读写；同一重大问题超过 10 分钟仍未解决时中止。本轮采用独立候选和无板优先，先冻结 A11/原 CPU 入口，再补 ARM64、显式范围预算、模型消费证据和保留所有权协议；未连接板卡。CPU/PL 内部符号隔离，消费者核验使用执行前输入与执行后确认以兼容原地 GLU；不放宽数学或容差。G0 本机准备完成，06 新板前置与实板功能/恢复仍未验收，不自动推进 07。')
    prepend(ROOT/'docs/AI_ASSISTANCE.md','2026-10-23 使用 xilinx-suite 与 llama-cpp 技能复用固定 2026.1/最终 A05 源码，完成 A12 01—05 的独立 PC 实现/测试/交叉构建和候选封装。凭据未使用或落盘，无板连接、子代理、模型设置切换声明、提交推送。实际设置 unknown；原失败/旧 PASS 与所有用户修改保留。报告与收据 `evidence/model_pl_A/20261023-preboard-v1/`。')
    plan=ROOT/'docs/A12_STEP_PLAN_20261023.md';data=plan.read_text(encoding='utf-8')
    old='本文件是接续 A11 的执行计划。本轮仅阅读、核对和编写计划，未实施 A12、未连接板卡；A12 的执行状态仍为 `NOT_STARTED`，下列执行项均未勾选。计划不把旧测试重新记为本轮测试，也不改变既有默认模块。'
    data=data.replace(old,'本文件最初于 2026-10-23 编写。用户随后授权执行 01—05，现已完成这些步骤的 PC 实现、验证和交叉构建；06—11 未执行，BOARD NOT_TESTED。完整证据与限制见 `evidence/model_pl_A/20261023-preboard-v1/REPORT.md`；勾选仅对应标明验证域，不表示实板通过。既有默认模块未变。')
    start=data.index('### 01｜');end=data.index('### 06｜')
    data=data[:start]+data[start:end].replace('- [ ]','- [x]')+data[end:]
    data=data.replace('| A12 | 尚未开始；完整模型尚未证明消费 PL 输出，完整模型板端速度、内存和加速比未验收 |',
        '| A12 | 01—05 PC/交叉构建完成；06—11 未执行。完整模型板端消费、数值、速度、内存与加速比仍未验收 |')
    data=data.replace('## 6. 本次计划编写的实际核验','## 6. 最初计划编写时的核验（历史）')
    data += '\n## 7. 01—05 执行更新\n\n2026-10-23：01—05 已按验证域完成，状态 `PASS_A12_01_05_PC_AND_CROSS_BUILD_BOARD_PENDING`；新失败与修复见报告和 FAILURES.json。第 06 步尚未开始，完整模型 BOARD 保持 NOT_TESTED/null。候选包 `release/a12_preboard_20261023_v1/` 静态核验通过，默认设备访问关闭。\n'
    plan.write_text(data,encoding='utf-8')
    handoff=ROOT/'docs/handoffs/A_A12_PREBOARD_01_05_20261023.md'
    handoff.write_text('# A12 01—05 无板交接（2026-10-23）\n\n'+note+'\n\n真实工程 C:\\Patientqwen，分支 codex/a12-preboard-20261023，保留全部修改、无 commit/push。固定契约不变。当前入口为 PROJECT_STATUS 顶部 a12_preboard_20261023，A11 交接保留为已完成前置。\n\n后续先读本轮 REPORT.md、SUMMARY.json、FAILURES.json、RESOURCE_CALL_BUDGET.json、ARM_BUILD_FINAL.json 和 PACKAGE_CHECK.json；按计划从 06 新鲜板前置与同板 S1 开始。候选包不是已安装或可直接授权运行证明，所需模型资产根 /opt/patient-qwen 未在本轮核实。\n\n01—05 中 PC_MATH_DOUBLE 不是 PL，任何硬件计数/收益仍 null。板端连接权限来自本轮用户请求，但本轮未使用凭据。不可复用旧 boot/PID/launch/租约；不重做已通过 A10/A11，不自动重启、刷写或强杀。\n',encoding='utf-8')
    print(json.dumps(dict(status=summary['status'],next_step=summary['next_step'])))


if __name__=='__main__':main()
