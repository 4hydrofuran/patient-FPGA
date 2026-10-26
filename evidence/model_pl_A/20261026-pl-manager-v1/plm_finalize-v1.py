"""Seal this progress stage, preserve previous failures and report the remaining full scope."""
from datetime import datetime,timezone
import json
import subprocess
import sys
from pathlib import Path
from plm_evidence import ROOT,OUT,PARENT,read,save,sha,pin

KEY='a12_pl_manager_protocol_offline_20261026'
HANDOFF='docs/handoffs/A_A12_PL_MANAGER_PROTOCOL_OFFLINE_20261026.md'
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')
def main():
    before=read(OUT/'PROJECT_STATUS.json.before');assert KEY not in before
    for name in DOCS:assert (ROOT/'docs'/name).read_bytes()==(OUT/(name+'.before')).read_bytes(),name
    protected=[]
    for row in read(OUT/'BASELINE.json')['files']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'] and p.stat().st_size==row['bytes'],row['path'];protected.append(row)
    older=read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']
    for row in older:assert sha(ROOT/row['path'])==row['sha256']
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1';assert sha(probe/'bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    baseline=read(probe/'BASELINE.json')
    for row in baseline['parent_files']:assert sha(Path(baseline['parent_bundle'])/row['path'])==row['sha256']
    for row in baseline['contract_files']:assert sha(row['path'])==row['sha256']
    for label,script in [('HISTORICAL_CONTRACT_GUARD','scripts/release/check_contracts.py'),('QWEN35_CONFIG_GUARD','scripts/release/qwen35_config.py')]:
        cmd=[sys.executable,script];r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True)
        save(OUT/(label+'.json'),dict(command=cmd,cwd=str(ROOT),exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));assert r.returncode==0
    review=read(OUT/'ARTIFACT_REVIEW.json');package=read(OUT/'PACKAGE_REVIEW.json');roarm=read(OUT/'OBSERVER_ARM-v2.json.receipt')
    assert review['status']=='PASS_PLM_PC_PROTOCOL_AND_A53_COMPILE_ONLY'
    assert package['status']=='PASS_REVIEW_ZIP_ALL_BYTES_ROUNDTRIP' and sha(ROOT/package['archive']['path'])==package['archive']['sha256']
    assert roarm['status']=='PASS_A53_RO_OBSERVER_COMPILE_ONLY' and sha(roarm['library'])==roarm['sha256']
    assert read(OUT/'UNIT_POLICY_RESULT-v2.json')['tests']==11
    a=read(OUT/'suite02-strict/RESULT.json');b=read(OUT/'suite02-batch/RESULT.json')
    assert a['claims']==b['claims']==2880 and a['private_messages']==2881 and b['private_messages']==41
    assert a['legacy_sequences']==b['legacy_sequences']==dict(router=2,backend=73)
    activation=dict(domain='PC_ACTUAL_XRT_BACKEND_CONTROL_DOUBLE_PROTOCOL_AND_A53_COMPILE_ONLY',production_enabled=False,
        BOARD='NOT_TESTED',board_operations=0,ARM_runtime='NOT_EXECUTED',ARM_open='HARD_DISABLED_BEFORE_DEVICE_OPEN',
        real_device_generation_approval='UNBOUND',actual_model_route_hooks='NOT_IMPLEMENTED',actual_Board_health_lease_dual_lock_binding='NOT_IMPLEMENTED',
        PL_mode_coordinator='NOT_IMPLEMENTED',actual_model_windows=0,actual_FPGA_calls=None,clinical_answers_delivered=0,
        original_resource_probe_replaced=False,release_authority=False,automatic_replay=False,board_latency_saving_s=None,board_CMA=None)
    save(OUT/'ACTIVATION.json',activation)
    next_work=[
        dict(id='REAL_MODEL_ROUTE',work='Derive actual Qwen route/frontend private bootstrap and request begin/end hooks; connect the real-model controller to dual lanes without changing public ABI or mathematical path; independently validate full consumer/result behavior offline',BOARD_required=False),
        dict(id='DEVICE_GENERATION',work='Implement independently checked live boot/lease/dual-lock/driver/kernel/BO-generation approval consumption; current context facts and PC recipe remain UNBOUND and cannot enable ARM',BOARD_required=False),
        dict(id='PL_MODE',work='Connect reviewed PL manager and real-model lifecycle to mode coordinator; preserve unknown-inflight quarantine and explicit new-window fallback gates',BOARD_required=False),
        dict(id='BOARD',work='Separate recovery/safe-release confirmation and fresh original safety gates before a newly authorized unchanged ordinary resource probe; no automatic board work',BOARD_required=True)]
    save(OUT/'NEXT_WORK.json',dict(goal_status='active',remaining=next_work,blocked_condition_repeated=False))
    completion=read(PARENT/'COMPLETION_AUDIT.json')
    for row in completion['requirements']:
        if row['id']=='PL_BACKEND_LIFECYCLE':row.update(private_control_protocol='IMPLEMENTED_PC_XRT_DSO_AND_ATOMIC_PAGE_TESTED',
            real_runtime_model_route_binding='NOT_IMPLEMENTED',device_generation_approval='UNBOUND',evidence=HANDOFF)
    completion.update(previous_turn_classification='progress',current_turn_classification='progress',whole_goal_achieved=False,
        goal_status='active',next_safe_action=next_work[0]['work'])
    completion['requirements'].append(dict(id='PL_MANAGER_PROTOCOL',requirement='Dual-lane manager, inherited atomic writer, bounded grants and request persistence',
        offline='PC_DSO_WIRE_17_PLUS_17_SCENARIOS_11_POLICY_TESTS_AND_ACTUAL_MANAGER_DEATH',
        ARM_build='BACKEND_WRITER_FULL_PROTOCOL_OBJECT_AND_RO_OBSERVER_COMPILE_ONLY',
        actual_model_route_hooks='NOT_IMPLEMENTED',BOARD='NOT_TESTED',production_enabled=False,evidence=HANDOFF))
    save(OUT/'COMPLETION_AUDIT.json',completion)
    report=f'''# A12 PL manager 双通道协议：无板控制验证（2026-10-26）

本轮把上阶段实际 XRT 后端派生候选接到了真正运行的 manager、继承 memfd 原子页、旧许可 helper 和新微批通道。完成两组各17个整窗场景（普通构建与 sanitizer 构建）、最终普通/sanitizer整窗复测、11项原子授权页/文件故障检查，以及两次 manager 真实退出实验。已有官方2026.1 SDK完成A53后端、writer、强制完整协议编译对象及仅只读观察库构建；未执行ARM制品。**仍不是完整模型/PL集成或板端验收。目标 active。**

没有上板、SSH、恢复、刷写、部署、释放、推送或修改B/HLS/公共数学/ABI；原普通资源包、安全门槛和既有失败保留。

## 实现与实际范围

旧 `supervisor_gate.hpp` 的 production 许可正文保持，分别在 router helper DSO 和真实后端派生 DSO 内实际执行 SO_PEERCRED、序列和 allow 交换。PC XRT double 编译仅去掉旧 header 的测试 bypass，使旧通道也真实走socket。router和backend分别按原phase分序列：router open/close为1/2，backend device_open及72次weight_load为1..73，不能混用各自静态序列。**这里验证的是旧 Route 所用许可 helper，不是整个 Qwen Route 类或模型图。**

独立SOCK_SEQPACKET私有通道绑定原生PID/start ticks、实际打开的control transport context事实、随机open nonce及SHA。manager通过私有native writer C API原子操作继承4096字节memfd；Python不直接写原子字。每个请求绑定冻结摘要和新代次，最多3请求，单段最多72次、窗口上限5000，R0/warm/hit的预算仍为1512/648/864。实际控制fixture走1440/648/792次，合计2880；固定6个decode控制round不冒充真实模型EOS或回答。

native本地Gate在BO传输前保留IO/扣一次额度，启动前再次检查，并在原meta/Y/超时/ERT门槛后才提交。新Control还在缓存额度内逐次核对T；同一请求代次只能bind一次。未用额度不被当成完成，未知IO不清零。weight卸载/close仅允许3个请求完成后的实际idle维护阶段，不能在请求间隙提前释放。故障POISONED、旧输出不可消费、所有权继续保留。

BEGIN先持久化再激活页并发送请求；GRANT日志持久化后才提高页limit，经新的健康fence复核紧邻发送allow。END必须通过原生完成/计数/状态核验，先失效请求授权，再完成END、独立receipt和健康交付fence；END字节齐全不能证明fsync成功或可交付。所有故障锁存并保留DIRTY，无自动重放、释放或恢复。

日志硬限4096条/4MiB/单条8192字节。每次追加只核对所拥有的FD/marker、当前追加字节和范围；完整历史按请求边界有界读取，不按每次投影/许可重扫。健康observer独立50ms观察，仅PC boot、活pidfd、原MemAvailable≥1114112KiB及本地持锁/marker；CMA为null，**没有模拟板端CMA、温度、驱动或板卡租约健康**。现有HealthFence仍限两个授权消费线程、250ms新鲜度、无旧快照复用；双通道由单个service线程处理，另一消费者为请求控制线程。

启动/请求边界对实际映射的probe/backend/router读取当前maps、核对dev/inode，并通过原FreshCheckedFile持有只读FD、重新读取全部当前字节核SHA；不靠mtime verdict缓存。子进程清除继承的LD_/旧SP_A12等入口环境。未知资源/失败不因进程退出而获板端释放许可。

## 结果与限制

| 同样2880次control调用 | cap1严格控制对照 | cap72候选控制 |
| --- | ---: | ---: |
| 计算GRANT数 | 2880 | 40 |
| 私有消息（含一次bind） | 2881 | 41 |
| 旧通道消息 | 75 | 75 |
| 总控制消息 | 2956 | 116 |
| 日志条数 | {a['journal_records']} | {b['journal_records']} |
| 日志字节 | {a['journal_bytes']} | {b['journal_bytes']} |

所有正常控制窗口为148个XRT stub BO、72份小型合成权重、零哨兵输出；N/K为2的控制fixture不是Qwen权重、矩阵数学、Csim、FPGA仿真、性能或真实前缀等价验证。没有新模型答案，不能据这些耗时换算板端输入到应答的秒数。原真实CPU模型结果仍按旧阶段保留；本轮没有把control窗口冒充模型窗口。

两组17场景各含cap1/cap72正常窗口和15故障：BEGIN/GRANT/END/receipt的fsync失败、GRANT/END慢日志后过期、错误请求摘要、旧通道重复open、缓存第5次claim后撤销、NaN Y、start异常、timeout、提前卸载、缓存额度内T变化、旧请求代次复用。故障控制结果交付均为0；未知资源保留，完整错误字节和DIRTY保留。独立审计实际读取私有原件及镜像字节、严格事件语义、冻结请求/T计划/范围、原native meta64字节和receipt/交付fence，完整END不被追认为成功。普通和sanitizer的最终当前Python源码又各跑一完整窗口，结果一致。

ASan/UBSan用于probe/backend/router；manager native writer另由UBSan检查。保留未知所有权的故障窗口关闭leak统计，未关闭地址/未定义行为错误检测；stderr未出现对应诊断。11项原子writer/文件I/O检查另覆盖无绑定、错误身份/摘要、startup拒绝grant、72及5000上限、重复grant/未消耗额度拒绝END、3请求代次限制、撤销/健康时间、缺API/geometry错误FD关闭、零进展写、完整END/receipt但fsync失败，以及边界实际重新读mmap改动后的日志字节。helper级零grant/空完成测试不提供请求交付批准。

manager真实退出实验在外层先取得两个活pidfd及SCM_RIGHTS页/pipe引用，RW页引用立即换为RO并关闭RW副本。原生第5次claim后，manager直接os._exit；原生拒绝该次start，只产生前4次stub start，caller Y不变，148个stub BO在错误报告中仍持有。manager退出后、原生仍活着时继承的协调锁实际BlockingIO；原生之后合作exit2，RO页仍显示claims5+revoked+unknown，DIRTY和失败包保留，同目录重入拒绝。没有强杀、close/unload或把PC进程终止当成板端DMA停止。两次实验均通过，最终一次使用严格仅导出read函数的observer。

## 保留的失败与修复

- `normal-01`：三个消费者超出原HealthFence两个线程上限，在claims0被拒绝；改为单service线程处理双通道，没有放宽上限。
- `normal-02`：handler提取时漏带lane变量，在启动许可前失败；旧源码、原件和退出码保留，修复后完成整窗。
- 真正重现早期v2缺少缓存T核对：第二次投影T改变仍被旧control窗口误判通过。`counterexample-cached-T`及命令exit1保留并明确NOT_ACCEPTED；v4在第二次调用前拒绝，claims/stub start均1、0结果交付。旧的“PASS control”不作为任何验收通过。
- 只读观察库初版泄露额外STL弱符号，独立审计拒绝。另建v2库用匿名export map只留read函数，旧库/旧审计/失败保留；v2完成PC退出实验与A53仅编译。没有修改已记录的旧二进制。
- 补齐初始化错误中新建无绑定页FD的关闭，未知/在途页仍拒绝关闭；11项最终检查和当前源码正常窗口通过。

## 制品和下一步

独立审阅包：`{package['archive']['path']}`，SHA `{package['archive']['sha256']}`。仅供审阅；Python依赖仓库冻结模块，ELF保留原私有WSL构建RPATH，不是可独立部署安装包。无权重/真bitstream/长诊断原件/上板脚本。包逐成员CRC和SHA回读通过。

原普通 `bundle-v2.zip` SHA仍为 `acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa`，恢复并确认安全释放后的首轮板测仍先用它，本候选不替换它。

**仍有无板工作：** 实际Qwen Route/frontend的私有bootstrap和请求begin/end接入、真实模型controller到双通道的闭环；独立live boot/lease/双锁/driver/kernel/BO-generation批准消费；PL模式协调器与未知在途/严格新窗口回退验证。当前PC context事实和固定recipe保持UNBOUND，不是设备代次批准。ARM在device_open前硬返回UNSUPPORTED，私有请求API非PC编译也UNSUPPORTED，不能由JSON开启。

BOARD NOT_TESTED，SERVICE=false，板端CMA和时延收益均null；新短提示词仍NOT_ACCEPTED，最终数值/生命周期/A12 step11/长期及医学验收不追认。复杂核心、设计和证据验收未委派；未使用DeepSeek，实际模型设置unknown。两项仓库guard均exit0，其他状态条目按原值保留，目标继续active。
'''
    with (ROOT/HANDOFF).open('x',encoding='utf-8') as f:f.write(report)
    entry=dict(status='PRIVATE_PLM_PROTOCOL_PC_XRT_VERIFIED_A53_COMPILE_ONLY',handoff=HANDOFF,evidence=OUT.relative_to(ROOT).as_posix(),
        regular_scenarios=17,sanitized_scenarios=17,final_current_source_windows=2,policy_tests=11,actual_manager_death_tests=2,
        actual_model_windows=0,control_calls_per_normal_window=2880,control_messages_cap1=2956,control_messages_cap72=116,
        ARM_build='BACKEND_WRITER_FULL_PROTOCOL_RO_OBSERVER_COMPILE_ONLY',actual_model_route_hooks='NOT_IMPLEMENTED',
        real_device_generation_approval='UNBOUND',PL_mode_coordinator='NOT_IMPLEMENTED',production_enabled=False,BOARD='NOT_TESTED',board_latency_saving_s=None,goal_status='active')
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps({KEY:entry,**before},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    note=f'\n\n## A12 PL manager协议无板进展（2026-10-26）\n\n实际派生XRT后端双通道/继承原子页/请求日志接通：普通与sanitizer各17整窗、最终2整窗、11策略检查、2次manager真实退出通过。2880控制调用保持，消息2956→116；非模型或板端时延。缓存T旧版反例和其他失败保留，原普通包不变。实际模型route/设备代次/PL模式接入仍未完成，ARM入口禁用，BOARD未测、目标active。见 `{HANDOFF}`。\n'
    for name in DOCS[1:]:
        with (ROOT/'docs'/name).open('ab') as f:f.write(note.encode('utf-8'))
        assert (ROOT/'docs'/name).read_bytes().startswith((OUT/(name+'.before')).read_bytes())
    assert {k:v for k,v in read(ROOT/'docs/PROJECT_STATUS.json').items() if k!=KEY}==before
    save(OUT/'PRESERVATION.json',dict(status='PASS',baseline_files=protected,old_source_pins=older,parent_files=len(baseline['parent_files']),contracts=len(baseline['contract_files']),
        original_probe_ZIP_sha256=sha(probe/'bundle-v2.zip'),other_status_entries_exact=len(before),old_governance_text_preserved_as_prefix=True,
        B_HLS_public_math_and_ABI_changed=False,board_contacted=False,pushed=False))
    sources=sorted(p for p in (ROOT/'platform/qwen35/a12').iterdir() if p.is_file() and (p.name.startswith('plm_') or p.name=='test_plm_policy.py'))
    evidence=sorted(p for p in OUT.rglob('*') if p.is_file())
    save(OUT/'FINAL_REVIEW.json',dict(status='PLM_PROTOCOL_OFFLINE_VERIFIED_GOAL_ACTIVE',recorded_at=datetime.now(timezone.utc).isoformat(),source=[pin(p) for p in sources],
        evidence=[pin(p) for p in evidence],governance=[pin(ROOT/'docs'/n) for n in DOCS]+[pin(ROOT/HANDOFF)],
        verification_layer=activation['domain'],BOARD='NOT_TESTED',production_enabled=False,whole_goal_achieved=False,goal_status='active'))
    print('PLM_PROTOCOL_OFFLINE_VERIFIED_GOAL_ACTIVE')
if __name__=='__main__':main()
