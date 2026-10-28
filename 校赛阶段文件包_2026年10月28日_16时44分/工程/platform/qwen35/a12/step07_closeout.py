"""Record a passed single projection and STOPPED finalization without false lifecycle PASS."""
import datetime
import json
from common import ROOT,save
from step07_protocol import OUT


def main():
    a=json.loads((OUT/'AUDIT.json').read_text(encoding='utf-8'))
    assert a['status']=='PASS_SINGLE_GATE_NUMERIC_AND_REAL_CONSUMER_CLOSEOUT_NOT_COMPLETE'
    assert a['lifecycle']['active_lease'] and a['lifecycle']['manager_exit_code'] is None
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    failures=[
      dict(id='native_DSO_protocol',domain='PC_REPRO',original_exit_code=1,problem='Router executable and private backend DSO each start permit sequence at1; old global counter rejects second message',resolution='Separate monotonic sequence lanes plus strict phase/job order in new step07_supervisor; native reproducer fixed exit0 and17 negative checks; 31 backend cases/764checks pass; no math/ABI/kernel change'),
      dict(id='unexecuted_draft',domain='LOCAL_REVIEW',problem='Ready message has no gpu_layers field',resolution='Corrected before upload/board dispatch; field checked on result. Original draft/manifest/archive retained; management PC gate checks pass'),
      dict(id='audit_01',domain='OFFLINE_AUDITOR',exit_code=1,problem='execution_kind is in ready/route reports, not top-level result',resolution='Read actual schema; raw records unchanged; audit_03 exit0'),
      dict(id='audit_02',domain='OFFLINE_AUDITOR',exit_code=1,problem='Overstrict whole-kernel-log hash equality rejected appended debug rfkill message',resolution='Pinned prior gated log and existing kernel diagnostic/continuity gate: one new debug line, no new diagnostic. No warning waiver or changed math threshold; audit_03 exit0'),
      dict(id='BOARD_FINALIZATION',domain='BOARD_LIFECYCLE',status='UNRESOLVED_STOPPED_OWNER_RETAINED',
           problem='Window.finish single full-process scan rejected PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT after defaultPL/GDM restore; failed scan raw snapshot was not saved',
           verified='S1/S2 workers normalexit0; testPL removed/ZOCL unloaded/defaultPL+GDM restored; later full scan complete/no FD/VMA users; unchanged boot. Manager27132/startticks2110722 has one sleeping thread, no children/XRT/device FDs, retains two canonical locks and active lease',
           cause_limit='Transient process churn is suspected but exact incomplete scan cannot be reconstructed. Current code parks forever without recovery IPC; editing source cannot resume it',
           disposition='No new board operations after read-only stopped snapshot. No signals/kill/unlock/lease stealing/reboot. Further model work suspended; controller/lease closeout requires separate reviewed handling'),
      dict(id='step06_deferred',domain='HISTORICAL',status='FAILURES_PRESERVED_DEFERRED_BY_USER',items=['PC/ARM whole-graph mismatch','First full-range conservative capacity check FAIL'],resolution='Neither blocked this same-board single-gate experiment; broad reassessment not run')]
    save(OUT/'FAILURES.json',failures)
    status=dict(status='SINGLE_PROJECTION_PASS_FINALIZATION_STOPPED',updated_beijing=now,
       functional='PASS_BOARD_L00_GATE_REAL_MODEL_CONSUMPTION',single_MLP='NOT_TESTED',step07_overall='PARTIAL_NOT_COMPLETE',
       scope='l0_gate',actual_calls=3,T=[8,1,1],jobs=[1,73,145],weight_loads=1,
       numeric='BIT_EXACT_SAME_BOARD_S1_S2',downstream_nodes=72,projection_records=36,logit_rows=10,
       mixed_state='BIT_EXACT',same_previous_step06_S1=True,explicit_BO_peak_bytes=2162688,
       physical_peak_bytes=None,hardware_global_count=None,board_speedup=None,resource=a['resource'],
       lifecycle=a['lifecycle'],authorization_window='STOPPED_DO_NOT_REUSE',
       current_board='DEFAULT_PL_AND_GDM_RESTORED_ZOCL_ABSENT_NO_DEVICE_USERS_OWNER_LOCKS_AND_LEASE_RETAINED',
       manager_pid=27132,manager_start_ticks=2110722,wrapper_pid=27125,
       no_forced_termination=True,no_additional_computation=True,step08='NOT_STARTED',
       deferred_failures=a['deferred_failures'],model_settings='unknown',subagents=0,
       contract_changed=False,B_core_changed=False,model_math_changed=False,default_FPGA_enabled=False,
       report='evidence/model_pl_A/20261023-step07-single-v1/REPORT.md',committed=False,pushed=False)
    save(OUT/'SUMMARY.json',status)
    report='''# A12 第07步：l00 gate 单投影实板结果与停止交接

执行跨北京时间2026-10-23/24；目录和窗口保留开始时的20261023标识，实际时间以收据为准。

**单投影真实计算、图消费和数值验证通过；最终管理器/锁租约收口失败，本轮停止，第07步整体未完成。** 本轮按用户范围只跑l00 gate，没有扩展三个MLP投影或24层，也没有重跑A11。前述跨ISA整图和首次完整容量FAIL保留，按用户指示暂缓统一评估。

## 已经跑通的部分

- 固定host key/网卡地址的SSH新鲜检查：machine-id摘要、boot `8422f92f-d01f-4849-ad19-6e66b640a9ad`、`6.8.12-a10irq2`、XRT2.18库哈希、默认PL/GDM、温度/内存、完整FD/VMA、双锁与租约符合前置。新包根`/var/lib/kv260-a12/step07-single-20261023-v1`；未覆盖旧包或全局默认。
- 使用相同新ARM64模型程序、模型/sidecar/模板、固定tokens1..9/teacher10,11、2线程/context1024/物理T8/R0，依次运行板上S1与S2。新程序仅加入逐次完成证据，CPU数学/调度、公共契约、B核均未改。ARM程序SHA `18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4`。新S1 logits/混合状态与第06步S1也逐位一致。
- **实际3次PL调用，T=8/1/1，job=1/73/145，1次权重加载。** job跨CPU调用增长，不能伪造为连续1/2/3。逐次ERT实读state4(COMPLETED)，64字节私有meta中magic/build/job/status/done/per-call count/算法权重字节均核对；per-call count=1不是全局硬件计数，全局计数仍null。
- 每次返回Y摘要连接到真实模型本次输入、投影输出，以及`ffn_swiglu-0`/`GLU`消费者；消费者读前摘要一致并确认执行后返回。不是A11捕获数据回放，不用CPU golden填输出。
- **同板S1/S2：10行完整词表logits、36份抽样投影输入/输出（层0/3/4/23共12组×3执行）、72个已列出的下游节点及20312900字节混合状态均逐位一致。** 72是诊断节点数，不代表72个投影已走PL。每次结果前状态清空、位置-1；算子/整图阈值未改。原始X/Y、节点、logits、状态、meta及独立审计保留。
- 6个显式BO/峰2162688B，均8192对齐、group3、低2GiB窗口且互不重叠；一对权重常驻、IO复用。116次板状态读回最低MemAvailable2909924KiB、CMA443632KiB，最高33.308°C。S1/S2进程HWM770656/786000KiB。没有测完整物理峰值或加速比。
- 新原生exe/DSO许可反例与修复回归通过；新图同数学/丢弃消费者拒绝通过；31个后端控制场景764检查和包内释放顺序检查通过。PC拒绝检查不冒充BOARD故障注入；本轮未注入DMA挂死/复位。

## 本轮阻塞：计算结束后，管理器未能收口

S1 worker27145、S2 worker27399均正常exit0。完整设备释放检查后，测试PL普通remove、ZOCL普通rmmod、默认PL load及GDM start均exit0，并读回默认PL/GDM恢复。随后`Window.finish()`的一次完整进程扫描被`PROCESS_SCAN_INCOMPLETE_OR_WRONG_BOOT`拒绝，进入保留状态。

这是本轮收口实现的缺口：最终扫描只做一次，失败快照没有写盘；保留循环没有受控恢复入口。后来独立扫描完整且boot未变，因此疑似GDM恢复时的短暂进程变化，但**无法证明首次扫描具体缺项**，不能把首次失败改成PASS。当前进程正在旧代码的循环中，修改磁盘文件不会使它恢复执行；没有尝试调试器注入、强杀、解锁别人的OFD或删除活动租约。

最后独立快照确认：

- **manager27132，startticks2110722**，一个睡眠线程，无子进程、XRT映射或设备FD；wrapper27125仍等待它。manager退出码null。
- 默认PL operating/GDM active，ZOCL不存在；全进程扫描完整，无计算设备FD/VMA占用。内核相对最后已审阅日志仅新增一条rfkill调试信息，既有连续性/诊断门禁通过。
- 两把规范锁仍归27132持有：`/var/lock/kv260-a1/deployment.lock`、`/run/lock/patient-qwen-linear.lock`。`/var/lock/kv260-a1/active/lease.json`仍保留本窗口记录；这是隔离保留状态，不能复用提交许可。

按“重大问题超过10分钟无法解决则中止报告”的约束，定位到当前版本无法受控恢复后停止新增板端操作，在时限内取回原始证据；后续仅完成离线审计/报告封存。计算通过不等于生命周期通过，**不签整体PASS，不继续三个投影或第08步**。板端快照不代表持续监控。

## 保存的失败及修复

1. 原管理器把exe和私有DSO各自从1开始的序号当全局单序列，原生PC反例exit1；新独立管理器按两条单调序列并严格检查阶段/job，原生修复exit0、17负检查。先修再上板，旧源码不改。
2. 本地未执行草稿错误读取ready.gpu_layers，上传前修正为检查结果字段；草稿清单/脚本/归档保留。
3. audit_01误读结果顶层execution_kind，audit_02把日志摘要相等误当连续性门槛；依据实际schema和既有内核门禁修正，audit_03 exit0。原始板数据不改、门槛不放宽。
4. BOARD最终锁租约收口失败尚未解决。见`FAILURES.json`和`readback-v1/stopped-snapshot-v1.json`；不自动再次运行模型。

## 下一步安全收口范围（本轮未执行）

先重新核对上述boot、PID/startticks、无子进程/设备/XRT、双锁/租约及完整内核门禁，确认快照仍成立。为后续管理器补“保留失败扫描、只读有界重查、显式受控恢复并正常退出”的入口并PC测试。当前旧进程没有该入口，不能靠修改脚本声称修好；如何定向结束这一个仅持锁的旧管理器须单独审阅决定，不能擅自强杀/偷锁/删租约。之后重新证明无人持锁，归档隔离租约，再独立读回。默认PL/GDM已恢复，收口无需重跑计算、装卸PL或驱动，更不需要重启/刷写。

原A11与01—06封存证据原样保留；未修改公共契约/数学、未提交推送、未启用子代理。实际模型设置unknown。完整执行收据、CPU/PL原始结果、失败、哈希清单见本目录。
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    header='2026-10-24 A12第07步单投影：l00 gate 3次真实PL调用T8/1/1，job1/73/145，Y被GLU真实消费；同板S1/S2的10行logits、36份抽样投影、72诊断节点、混合状态逐位一致。两worker正常exit0，默认PL/GDM恢复、ZOCL无/设备FD-VMA无；最终扫描拒绝后manager27132/startticks2110722保留双锁/active lease，无受控恢复入口。本轮STOPPED，07整体未完成，三个MLP投影/08未执行；后续先安全收口管理器，不能复用旧许可。两个06历史FAIL按用户指示保留待评估。报告 `evidence/model_pl_A/20261023-step07-single-v1/REPORT.md`。以下均为历史快照。'
    p=ROOT/'docs/PROJECT_STATUS.json';old=json.loads(p.read_text(encoding='utf-8'))
    new={'role':old['role'],'a12_step07_single_20261024':status};new.update({k:v for k,v in old.items() if k!='role'})
    new['stage']='A12';new['stage_status']='IN_PROGRESS_SINGLE_PROJECTION_PASS_FINALIZATION_STOPPED_LOCKS_LEASE_RETAINED'
    p.write_text(json.dumps(new,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name in ('docs/status/A.md','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md'):
        p=ROOT/name;s=p.read_text(encoding='utf-8').splitlines(keepends=True);s.insert(1,'\n'+header+'\n');p.write_text(''.join(s),encoding='utf-8',newline='\n')
    p=ROOT/'docs/AI_ASSISTANCE.md';s=p.read_text(encoding='utf-8').splitlines(keepends=True)
    s.insert(1,'\n2026-10-24 使用xilinx-suite/llama-cpp技能，按用户授权限定单投影，隐藏认证、固定host key、新包/双锁/租约执行。原生DSO许可反例先修复，增加逐次ERT/meta证据。计算通过，收口代码缺口导致停止；未强杀/偷锁/删除租约/扩大范围/启用子代理，实际模型设置unknown。'+header+'\n')
    p.write_text(''.join(s),encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';s=p.read_text(encoding='utf-8')
    start=s.index('### 07｜');end=s.index('### 08｜');section=s[start:end]
    section=section.replace('- [ ] 先选择 l00 单投影，再接通 l00 gate/up/down；输入必须来自本次真实模型执行，输出必须返回本次真实图消费者，不能复用 A11 捕获数据充当模型执行。',
       '- [x] l00 gate 单投影：本次真实模型输入、真实PL返回Y与GLU消费关联通过（3调用）；原始数值/状态与同板S1逐位一致。\n- [ ] 扩大到 l00 gate/up/down（三个投影本轮未执行）。')
    section+='2026-10-24 更新：单投影功能/数值通过，最终manager/锁租约收口失败并STOPPED；本节其他条目不追认为完整通过。见本轮REPORT，下一步先处理27132持锁管理器；08不具备条件。\n\n'
    s=s[:start]+section+s[end:]
    s+='\n## 9. 第07步单投影执行与停止更新\n\n'+header+'\n'
    # Current stage gets a first-line update; older chronological notes remain intact.
    lines=s.splitlines(keepends=True);lines.insert(1,'\n'+header+'\n');p.write_text(''.join(lines),encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP07_SINGLE_STOPPED_20261024.md'
    with handoff.open('x',encoding='utf-8') as f:f.write('# A12单投影停止交接\n\n'+header+'\n\n单投影证据通过，生命周期仍未闭合。原始快照：本轮readback-v1/stopped-snapshot-v1.json。独立快照时manager只有一线程、无子进程/设备/XRT；wrapper27125等待。两把锁及活动租约仍保留，严禁据此继续计算、删除租约或假记正常退出。当前代码无受控恢复入口，编辑源文件不能唤醒旧实例。先按REPORT最后一节单独处理收口，再讨论扩大范围；不重跑A11、不重启刷写。\n')
    print(json.dumps(dict(status=status['status'],manager_pid=27132,overall_PASS=False)))


if __name__=='__main__':main()
