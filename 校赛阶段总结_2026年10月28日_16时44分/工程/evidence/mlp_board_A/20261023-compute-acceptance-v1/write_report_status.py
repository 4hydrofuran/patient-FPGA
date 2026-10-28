import datetime,hashlib,json,re,shutil
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
read=lambda p:json.loads(p.read_bytes())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
a=read(E/'AUDIT.json');result=read(E/'readback-v3/worker-result.json');state=read(E/'readback-v3/state.json')
assert a['all_bit_exact'] and a['real_submissions']==23
observations=[]
for line in (E/'readback-v3/worker.stdout.jsonl').read_text().splitlines():
    r=json.loads(line)
    if 'process_observation' not in r:continue
    p=r['process_observation'];kv=lambda text:{k:int(v) for k,v in re.findall(r'^([A-Za-z_]+):\s+(\d+) kB$',text,re.M)}
    status=kv(p['status']);smaps=kv(p['smaps_rollup']);mem=kv(p['meminfo'])
    report=r.get('report',r.get('post_load_report',{}))
    observations.append(dict(event=r['event'],weight=r.get('weight'),monotonic_ns=r['monotonic_ns'],
        VmRSS_KiB=status.get('VmRSS'),VmHWM_KiB=status.get('VmHWM'),PSS_KiB=smaps.get('Pss'),
        CMA_total_KiB=mem.get('CmaTotal'),CMA_free_KiB=mem.get('CmaFree'),
        explicit_bo_charged_bytes=report.get('owned_bo_charged_bytes')))
resource=dict(domain='BOARD',observations=observations,explicit_peak_charged_bytes=a['explicit_bo_peak_charged_bytes'],
    explicit_io_charge_bytes=212992,allocation_alignment_bytes=8192,explicit_budget_bytes=4194304,
    explicit_BO_creations_host_counter=14,physical_bo_peak_bytes=None,implicit_XRT_BO_bytes=None,
    production_full_model_memory_bytes=None,
    accounting='PSS/RSS include process mappings; CMA-free changes are system-wide. Do not sum PSS + CMA + explicit BO bytes.',
    scope='one reusable IO workspace plus one resident weight pair; not a full-model resident memory budget')
(E/'RESOURCE_ACCOUNTING.json').write_text(json.dumps(resource,indent=2)+'\n',encoding='utf-8')
table=['| 算子 / N×K | T1 中位数 | T8 中位数 | T3 | 冷权重总加载 |','|---|---:|---:|---:|---:|']
for op in ('gate','up','down'):
    rows={r['T']:r for r in a['performance'] if r['operator']==op};r=rows[1]
    table.append(f"| {op} / {r['N']}×{r['K']} | {r['median_service_ms']:.3f} ms | {rows[8]['median_service_ms']:.3f} ms | {rows[3]['median_service_ms']:.3f} ms | {r['weight_cold_total_ms']:.3f} ms |")
report=f'''# A11 实板数值、含搬运服务时间及正常恢复验收（2026-10-23）

结论：**PASS_WITH_LIMITATIONS**。独立窗口 `a11-mlp-20261023-v3` 完成冻结23次有效调用（手算1、尾块/双scale1、真实gate/up/down各7），另有一次T=0的非法参数检查，返回SP_BAD_ARGUMENT=1、输出保持哨兵、不可消费、无硬件提交。23份FP32实际Y逐份取回、核SHA并在本机独立重新比较，全部与冻结参考**逐字节一致**，最大绝对/相对误差0。原atol=1e-4、rtol=1e-5门槛保留。完整单次生命周期与计算后正常释放/恢复通过；A12未启动。

## 实际性能

{chr(10).join(table)}

T1/T8每形状各3次，T3各1次；表中中位数保留首个常驻调用，不删除样本。剔除首个常驻调用后的T1暖态中位数：gate 5.284378、up 5.278933、down 5.086416 ms（各2次）；T8均为常驻后调用。`AUDIT.json.performance` 包含全部样本、min/max和暖态组，不计算小样本p95。

服务时间包含激活量化、原生ABI输入复制/BO同步、参数设置/提交/完成轮询、meta同步校验、输出同步/数值保护和返回复制；冻结参考比较、诊断、许可等待、磁盘导出在计时外。冷权重总加载包含文件读取、调用方复制及原生加载；原生加载分别25.209/25.034/25.057 ms。每次调用的native细分时间完整保存；submit-to-completion是主机测量，不能称纯核周期时间。

真实权重复制约2 ms、sync调用约0.03 ms，后者不是PL读取DDR的有效带宽测量，不能据此导入design_budget或宣称几十GB/s。未测PL/DDR有效带宽、AXI字节、硬件周期、CPU同路径加速比均null。未运行额外优化或压力测试，不把单层服务时间换算为完整模型tokens/s。

## 先审查并修复的失败释放路径

此前引擎把所有错误统一停车。新路径只允许以下正常退出：open明确返回错误且未产生context；或已经确认READY、job/build/meta/完成数正确、BO范围/复用/账面及调用方保护字完整，但独立数值/量化比较失败。后一类保存原始Y和失败ledger，停止后续调用，获得独立`abort_close`父许可，依次unload/close；失败结果使用`FAILED_CLOSED_A11_MINIMAL`并据实际提交数记账，不宣称矩阵成功。管理器仍须waitpid(exit0)、完整FD/VMA扫描、refcount0、内核/健康门禁后才能普通卸载与恢复。

超时、POISONED、错误build/job、保护字异常、关闭失败、未知完成、内核异常或设备残留继续隔离，不kill、不强制卸载、不重放。新增可信failed-result验证协议与父许可规则，并在Linux真实子进程/flock/日志fixture中验证数值失败正常恢复，额外提交/假成功/身份篡改/残留VMA/refcount均拒绝。没有在板上故意制造挂死DMA，超时隔离验证域为PC。

代码：`platform/qwen35/a11/mlp_engine.py`、`manager_support.py`、`compute_result.py`、`prepare_compute_bundle.py`；标准打包入口`prepare_bundle.py`已指向新完整路径。派生管理器/边界独立存入`bundle-v2/`，原受保护A10/旧计算/原open包不改。复用原native ARM64库SHA `4d30d6dfb744aa47e0ce4a3faf5a6f685a1ee88fbeb6fe5c241c2dbed7990e38`，不改公共ABI/数学/核/驱动/内核。

## 验证和证据

- PC：旧契约、新配置各exit0；引擎14方法通过；完整恢复编排11方法通过；最终前置扫描断言1方法通过；修正后的包清单、标准入口与离线实板审计均exit0。真实量化与冻结参考复用，不用mock数值冒充BOARD。
- BOARD：boot `{a['boot_id']}`，内核`{a['kernel']}`，manifest `{a['manifest_sha256']}`。实际23调用、5次权重加载，四IO BO始终复用，每个权重集合warm期间地址/handle不变，无重复上传；14为显式BO的主机创建计数，不是硬件完成计数。有效调用均由原生ERT完成、内核meta的build/job/状态/输出大小检查后返回，report中的per-call计数是host-seeded私有字段，不冒充全局硬件计数。
- worker17974、manager17873均正常exit0。释放前完整FD/VMA/refcount门禁通过，随后普通恢复默认PL/GDM并归档租约、释放双锁；生命周期约32.580秒（含管理/日志/许可，非算子时延）。74.899秒后独立读回扫描完整：FD0/VMA0、ZOCL absent、双锁无人持有、active lease absent、默认PL applied、FPGA operating、GDM active，worker/manager均已退出。
- 生命周期温度采样最高31.661°C；独立后验29.158–32.376°C。已有action-scoped overlay属性/IRQ枚举advisories保留；无新增未审查内核诊断。
- 证据：`readback-v3/actual-job-01.f32`至`actual-job-23.f32`、worker-result/完整stdout、lifecycle、kernel原文、review/profile/退出/独立state均逐文件hash取回；`audit_01.json`记录本机独立审计命令和exit0。`RESOURCE_ACCOUNTING.json`保留进程PSS/RSS/CMA与BO双账，不相加。

显式BO峰值charge为2162688字节（约2.063MiB），4MiB上限、8192对齐和逐BO低2GiB检查均执行；这不是隐式XRT/全系统/完整模型的物理峰值，物理BO峰值仍null。冻结vectors manifest内的旧proposed_allocation只是历史方案，实际资源以本次report/profile/账面为准。

## 保留的失败和限制

首次计算窗口v2在任何GDM/PL/核动作前被`verify_bundle`拒绝：新打包器按文件名排除manifest，误排除嵌套vectors/manifest.json。已修正为只排除根manifest，并在打包时真正调用verify_bundle。本地旧bundle和板端v2/exit1保留，未复用消费过的启动记录；新v3包全部校验后执行。首轮PC管理测试仅旧扫描事件名断言失败，改为检查真实不完整扫描被保留、两个完整观察先于修改；失败日志保留。初次只读preflight记录PROCESS_SET_CHANGED，未冒充完整扫描；执行入口有界重采并保留全部样本，正式维护仍使用严格门禁。

没有硬件integer-debug导出接口，内部整数和无法BOARD直接观察；FP32输出与独立参考bit-exact不冒充整数探针结果。仅小样本描述性服务时间，无p95/长稳/功耗/架构优化/完整模型PL通过声明。新板端故意超时/复位恢复未测，PC隔离测试与正常BOARD计算后恢复分域记录。仍使用当前已验证irq2启动，不改启动配置、不重启/刷写/升级，不提交或推送。

下一步：A11目标层数值与含搬运服务验收已完成；审查A12完整模型消费PL输出的独立前置与资源预算。本轮不自动进入A12，不将本次候选提升为生产默认。所有旧失败与A00—A17历史保留。
'''
(E/'REPORT.md').write_text(report,encoding='utf-8')
handoff=ROOT/'docs/handoffs/A_A11_COMPLETE_20261023.md'
handoff.write_text('# A11 实板验收交接（2026-10-23）\n\n'+report.split('## 实际性能')[0].split('\n',1)[1]+'\n'+chr(10).join(table)+'\n\n最新证据：`evidence/mlp_board_A/20261023-compute-acceptance-v1/REPORT.md`、`AUDIT.json`、`RESOURCE_ACCOUNTING.json`、`SEAL.json`。\n\n标准本地打包入口：`python -B platform/qwen35/a11/prepare_bundle.py --out <新目录>`。已消费v2/v3不得重放；板端默认PL/GDM已恢复，无锁/租约/设备残留。A12未开始。完整模型物理内存/功耗/长稳/硬件整数探针/故意超时BOARD恢复仍未测，不能把本阶段结果转写成完整模型性能。\n',encoding='utf-8')
paths=['docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','design/qwen35/target_results.json']
backup=E/'governance_before';backup.mkdir(exist_ok=False)
for n in paths:
    p=backup/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,p)
status=read(ROOT/paths[0]);role=status.pop('role')
entry=dict(a,report=E.relative_to(ROOT).as_posix()+'/REPORT.md',audit=E.relative_to(ROOT).as_posix()+'/AUDIT.json',
    resource_report=E.relative_to(ROOT).as_posix()+'/RESOURCE_ACCOUNTING.json',handoff=handoff.relative_to(ROOT).as_posix(),
    history_rule='Newest captured state supersedes all lower historical current-state claims; not live monitoring. Old failures preserved.')
status=dict(role=role,a11_acceptance_20261023=entry,**status)
status.update(stage='A11',stage_status='PASS_WITH_LIMITATIONS',updated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    blockers=[],blocker_scope='A11 real MLP numeric/service/normal release passed with recorded limitations. Remaining hardware observability and later product/full-model tasks are not silently passed.',
    next_action='Review A12 independent prerequisites and full-model PL-consumption/resource plan. A11 23-call numeric/service/release complete; do not replay consumed v2/v3 or auto-start A12.',
    a11_domains=dict(pc='PASS_FAILURE_RELEASE_AND_ENGINE',aarch64_build='REUSED_PINNED_A11_NATIVE_AND_QUANT_ARTIFACTS',board='PASS_23_FP32_BIT_EXACT_WITH_LIMITATIONS',
                     csim='NOT_RERUN_REUSED_A06',cosim='NOT_RERUN',synthesis='NOT_RERUN',implementation='NOT_RERUN',power='NOT_TESTED'))
(ROOT/paths[0]).write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
common='2026-10-23 最新：A11 PASS_WITH_LIMITATIONS。冻结23次实际调用/5次权重加载，11形状（含真实gate/up/down T1/T8/T3）FP32输出逐字节等于独立参考，最大误差0；T1服务中位数5.109–5.268ms、T8 15.257–16.764ms，均含量化/同步/复制。worker/manager正常退出，独立后验默认PL/GDM恢复，无FD/VMA/ZOCL/锁/active lease。A12未开始；下方NOT_PASSED是历史快照。见`evidence/mlp_board_A/20261023-compute-acceptance-v1/REPORT.md`。'
entries={
 'docs/DESIGN_GAP.md':'## A11 实板验收完成（2026-10-23）\n\nD07/D08/D09：真实输出、分段及含搬运计时、常驻IO/权重复用与正常计算后恢复均有BOARD证据。新增已完成数值失败的正常关闭协议，未知完成/POISONED继续隔离，14引擎+11编排方法PC通过。显式charge峰值2162688B，物理峰值null；硬件整数探针、有效PL/DDR带宽、AXI/周期、p95、长稳及故意超时BOARD恢复仍未测，不用CPU或host计数顶替。'+common,
 'docs/DECISIONS.md':'2026-10-23 用户授权完成A11并直接修复问题：先审查失败路径，再用fresh独立窗口执行完整矩阵。只有确证完成/guards/BO检查正常的数值失败可abort_close后正常退出；超时/未知完成/关闭失败继续保留隔离，父进程waitpid+完整资源门禁后才普通恢复。包清单漏项在硬件前拒绝，修正后新v3通过，不复用旧启动。小样本服务计时不宣称p95、纯核时间或完整模型速度。'+common,
 'docs/TEST_MATRIX.md':'## A11 实板数值与性能（2026-10-23）\n\nPC：契约各0，引擎14、恢复编排11、最终扫描1方法通过，包/标准入口/独立审计0；旧事件名断言失败保留。BOARD：T0非法调用返回1无消费/提交；23有效调用逐文件独立复核bit-exact，job/build/guards/低地址及BO复用检查通过；完整正常退出/恢复/74.899秒独立后验通过。v2缺manifest在硬件前失败保留，v3正式包SHA64f9cc327b006f2ca12d213c159d33d404e7668679144c15e95c6290fcf0bcde。整数debug接口/硬件计数器/长稳/故意超时BOARD仍未测。'+common,
 'docs/AI_ASSISTANCE.md':'2026-10-23 使用xilinx-suite嵌入式流程，复用2026.1/A53与已固定XRT/irq2平台。用户授权完整A11与修复，先PC审查并补数值失败正常关闭，再固定host-key SSH暂存独立包/新租约执行23调用；真实隐藏认证，无凭据落盘。包清单缺项和测试旧事件断言失败保留并修复。无子代理/实际模型设置声明/重启/刷写/强制终止/升级/公共数学ABI修改/提交推送。模型配置unknown，BOARD与PC及未测值分开。'+common,
 'docs/status/A.md':common
}
for n,text in entries.items():
    p=ROOT/n;s=p.read_text(encoding='utf-8');first,_,rest=s.partition('\n');p.write_text(first+'\n\n'+text+'\n\n'+rest.lstrip('\n'),encoding='utf-8')
p=ROOT/'design/qwen35/target_results.json';d=read(p)
d['a11_board_evidence']=dict(status=a['status'],report=entry['report'],audit=entry['audit'],service_ms=a['performance'],
    numerical_max_abs_error=0.0,physical_bo_peak_bytes=None,explicit_bo_peak_charged_bytes=2162688,
    note='Layer diagnostics only; existing whole-product targets/actuals stay independent. Host sync is not measured PL DDR bandwidth.')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(status='REPORT_GOVERNANCE_AND_HANDOFF_WRITTEN',A11=a['A11'],A12='NOT_STARTED')))
