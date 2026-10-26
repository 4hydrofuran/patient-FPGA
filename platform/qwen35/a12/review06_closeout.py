"""Publish two-failure disposition; preserve old failures and task07 acceptance."""
import datetime
import json
from common import ROOT,save
from review06_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    a=j(OUT/'AUDIT.json');assert a['status']=='PASS_STEP06_REVIEW_NO_REMAINING_BLOCKER_FOR_CONTROLLED_STEP08'
    for name in ('contracts_01','config_01','prepare_02','numerics_01','loadonly_pc_01','policy_pc_01',
                 'package_01','source_review_01','upload_01','download_01','audit_01'):
        assert j(OUT/(name+'.json'))['exit_code']==0,name
    for name in ('preflight_01','stage_01','launch_01','readback_01','status_01','delayed_01'):
        assert j(OUT/name/'receipt.json')['exit_code']==0,name
    actual=a['full_residency']['actual_residency_reserve'];pre=a['full_residency']['pre_allocation_admission']
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    status=dict(status=a['status'],updated_beijing=now,
       cross_ISA='FAIL_REPRODUCED_ACCEPTED_LIMITATION_NOT_WAIVED',numeric_blocker_for_step08=False,
       independent_reference_cases=17,independent_real_PL_outputs=9,same_board_reference_required=True,
       original_full_capacity='FAIL_PRESERVED',new_full_capacity='PASS_BOARD_72_WEIGHTS_148_BO_ACTUAL_RESIDENCY',
       capacity_blocker_for_step08=False,actual_explicit_BO_bytes=140591104,
       CmaFree_all_weights_resident_kib=actual['memory_kib']['CmaFree'],CmaFree_required_kib=98304,
       additional_Cma_margin_above_required_kib=actual['memory_kib']['CmaFree']-98304,
       manager_pid=33628,wrapper_pid=33621,manager_exit=0,worker_exits=[0,0],
       active_lease=False,held_locks=False,default_PL_restored=True,GDM_active=True,ZOCL_absent=True,
       model_kernel_submissions_this_review=0,full_model_PL_computation='NOT_TESTED',step08='NOT_STARTED',
       stage08_decision='ELIGIBLE_FOR_NEW_CONTROLLED_WINDOW_AFTER_FRESH_GATES',
       conditions=a['remaining_conditions'],new_artifact_cache_and_capacity_policy='PC_TESTED_AND_USED_BY_THIS_BOARD_PROBE',
       model_math_changed=False,thresholds_relaxed=False,contract_changed=False,B_core_changed=False,
       default_FPGA_enabled=False,physical_peak_bytes=None,speedup=None,subagents=0,model_settings='unknown',
       report='evidence/model_pl_A/20261024-step06-review-v1/REPORT.md',committed=False,pushed=False)
    save(OUT/'SUMMARY.json',status)
    failures=[
       dict(id='step06_cross_ISA',domain='HISTORICAL_AND_OFFLINE_REPLAY',status='FAIL_REPRODUCED_PRESERVED_NOT_WAIVED',
            problem='PC/x86 and ARM whole graph logits exceed original .002+.0002*abs(ref)',
            resolution='First amplifying A8 boundary reproduced (1.49999046->1 versus1.50001919->2). Eight CPU-origin and nine real PL same-input outputs independently bit-exact. Use matched same-board S1/S2 for step08; do not require or claim cross-ISA equivalence',
            limit='Specific upstream non-MLP instruction causing floating differences not identified; cross-ISA portability remains a limitation'),
       dict(id='step06_first_capacity',domain='HISTORICAL_BOARD',status='ORIGINAL_FAIL_PRESERVED_NEW_SEPARATE_FULL_RESIDENCY_PASS',
            original_cma_after_hypothetical_BO_kib=79416,unchanged_required_kib=98304,
            resolution='Exact artifact cache fsync/fadvise, fresh stage-aware reserve check, actual allocation/upload72weights148BO and normal close validated in new window; no threshold relaxation or global cache clearing',
            new_actual_CmaFree_kib=actual['memory_kib']['CmaFree']),
       dict(id='prepare_01',domain='LOCAL_GENERATOR',exit_code=1,
            problem='Ambiguous text anchor occurred in both check and commit methods; assertion rejected derivation',
            resolution='Narrowed unique check-method anchor; prepare_02 passed before remote deployment; no device operation'),
       dict(id='early_preflight_not_dispatched',domain='LOCAL_COMMAND',exit_code=1,
            problem='Transport file had not been generated after prepare_01 failed; Python could not open it',
            resolution='No SSH execution occurred; first actual preflight_01 reserved after prepare_02'),
       dict(id='loadonly_expected_denial',domain='PC_NATIVE_EXECUTABLE_DSO_NEGATIVE_TEST',actual_child_exit=1,
            status='EXPECTED_PASS_REJECTION',problem='Deliberate submit after72loads rejected by control policy',BOARD_injection=False)]
    save(OUT/'FAILURES.json',failures)
    summary='2026-10-24 第06步两项遗留失败复核完成：跨PC/ARM整图FAIL复现并保留，17组同输入独立标量复算（含9次真实PL输出）逐位一致，同板S1/S2为第08步唯一硬件数值基准，该跨ISA限制不阻断08。新独立窗口实际驻留72份权重、148个BO共140591104B，group3/低2GiB/不重叠/8192分配对齐均通过；驻留CmaFree263136KiB，高于98304KiB门槛，首次容量FAIL不追改。精确7份归档哈希核对后fsync/fadvise，文件保留，无全局清缓存。管理端禁止所有submit，本轮模型核提交0；worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。两项均不再阻断受控进入08，但下一窗口须新鲜身份/内核/完整BO/资源门禁并验证全范围真实消费；08尚未启动，物理峰值/加速比null。报告 `evidence/model_pl_A/20261024-step06-review-v1/REPORT.md`。下方为历史快照。'
    report=f'''# A12 第06步遗留失败复核与第08步影响判断

**两项遗留失败均不再阻断受控进入第08步。** 旧失败保留原状态；本轮没有启动第08步模型计算，也没有更改数学、模型、契约或容差。

## 1. 跨PC/ARM整图数值FAIL

在原始保存数据上重新比较10行logits，原0.002+0.0002|ref|门槛下仍FAIL（见CROSS_ISA_REPRODUCED.json），不把它改成PASS。首层量化前输入扁平索引3745（row3/k673），ARM归一值1.499990463→量化1，PC1.500019193→量化2；前级极小浮点差落在量化边界两侧，被后续图放大。具体上游非MLP机器指令尚未定位，不能声称跨架构完全一致。

重新调用既有A04独立标量程序，对ARM/PC各4组保存输入，以及第07步3投影×T8/1/1的9组真实PL输入，共17组复算；全部输出逐位相同，最大误差0。9份独立输出还与真实run/job的Y摘要和模型消费者关联。该复算在PC/WSL执行，属于独立参考验证，新增板端计算0；此前第07步同板S1/S2全词表logits/状态/抽样投影逐位一致的封存仍有效。

**对08的影响：不构成硬件实现阻塞，但固定验收基准。** 08必须使用相同板卡、ARM程序、模型/sidecar、输入、线程与调度的S1/S2配对；PC图可作独立分析，不充当ARM硬件整图等价基准。该FAIL仍限制跨架构可复现性，不能将本轮9次首层验证外推为全部72投影已计算通过。算子1e-4+1e-5|ref|、图0.002+0.0002|ref|均保持。

## 2. 首次完整范围容量FAIL

原场景CmaFree216712KiB减去计划BO137296KiB后为79416KiB，低于98304KiB（32MiB底线+64MiB额外余量）；原FAIL继续保留，新的PC门禁回归仍拒绝它。此前v2只有假设扣账，本轮补成真实全量分配验证。

新窗口 `a12-capacity-20261024-v1`，新包 `/var/lib/kv260-a12/step06-review-20261024-v1`；新鲜核对同machine/boot、irq2内核、XRT/默认PL/资产/锁租约。沿用已通过ARM程序SHA `18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4`。先运行单请求CPU teacher-T8（无诊断dump），随后加载真实PL后端并上传全部72份权重，仅等待ready后正常关闭；不给S2发送generate请求。

- 实际72权重、148个显式BO，合计140591104B（约134.08MiB）。逐BO核对group3、8192字节分配charge、低2GiB、非重叠；无假设分配或临时单层替代。
- 分配前CmaFree{pre['memory_kib']['CmaFree']}KiB，扣除尚未分配BO后{pre['CmaFree_after_pending_kib']}KiB，通过98304KiB门槛；MemAvailable同样通过原1GiB底线+64MiB余量。
- 全部权重驻留后CmaFree **{actual['memory_kib']['CmaFree']}KiB**，比门槛多 **{actual['memory_kib']['CmaFree']-98304}KiB**；MemAvailable{actual['memory_kib']['MemAvailable']}KiB。此时现有BO已经反映在实际可用量中，只扣尚未分配部分，不重复扣同一BO。
- 197次健康采样，MemAvailable最低{a['resource']['min_MemAvailable_kib']}KiB、CmaFree最低{a['resource']['min_CmaFree_kib']}KiB、最高{a['resource']['max_temperature_mC']/1000:.3f}°C。S1/S2 RSS HWM为{a['resource']['S1_RSS_HWM_kib']}/{a['resource']['S2_RSS_HWM_kib']}KiB，不能与CMA相加冒充物理总峰值。

**实际改进并使用：** 新增capacity_policy.py，将容量预算按“待分配/已分配”分开；新增精确归档缓存处理，仅对清单固定的7份任务归档做哈希核对、fsync和fadvise(DONTNEED)，保留文件/大小/mtime，不碰模型页、不drop_caches。此次归档操作前后CMA为382228→388756KiB；该差额仅是本次观察，不声称重现了原场景全部缓存变化，也不保证每次能释放固定容量。新包在实际分配前重新运行完整保守门槛，不能只依赖缓存处理。

**对08的影响：这次硬件/环境下已证明完整权重能驻留，不再是未验证阻塞。** 完整模型实际计算、诊断文件、连续生成的瞬时峰值仍未测；08必须在新窗口重新核对资源，在分配后及提交前使用实际CMA/可用内存门禁，诊断文件和新归档缓存也要计入窗口条件。不能把本次一次通过当永久容量保证。

## 3. 本轮安全边界和正常收口

加载专用管理端从许可入口拒绝一切submit，Linux原生可执行文件/私有DSO的“72load后提交”反例被正确拒绝，正常72load/close也通过；派生Window完成7项真实flock/完整扫描/受控恢复PC测试。板端75条许可仅为router_open、device_open、72次weight_load、router_close，无submit，无S2请求文件或完成trace；模型核调用0，硬件全局计数无接口仍null。没有把资源验证写成PL整图计算通过。

管理器33628/包装器33621以及CPU33649/PL33900均已退出；worker和manager实际exit0。完整释放门禁、普通卸载、默认PL和GDM恢复、租约归档/双锁释放通过，独立与延时复核无设备FD/VMA、ZOCL、active lease和锁持有者；归档租约摘要匹配本窗口预期字节。最终扫描一次完整通过，未使用强杀、恢复票据、重启、刷写或故意DMA故障。

## 4. 第08步接续条件

1. 新窗口新鲜读取板身份/boot/irq2内核、XRT/位流/模型身份、无设备用户和唯一租约；不重放本次permit/进程ID。
2. 保留同板S1，固定相同模型、sidecar、输入、线程、物理T和图调度；PC跨ISA FAIL独立保留。
3. 定向处理经过新清单哈希固定的任务归档缓存；分配前扣待分配140591104B，已驻留后使用实读余量，CMA>=98304KiB、MemAvailable>=1114112KiB作为本次完整范围的额外余量门槛。未通过不提交，不能放宽门槛或全局清缓存来追认。
4. 使用普通计算窗口的独立审核组件；本次load-only包明确禁止计算，不可当成08计算许可。真正08仍需逐层/逐job/消费者核对72投影，保存首个分歧、全部失败并正常恢复。
5. 全模型计算峰值、自然连续生成、状态、速度收益仍由08及后续独立验收；本轮物理峰值/加速比null，默认FPGA未启用。

原始验证：NUMERIC_REVIEW.json、CROSS_ISA_REPRODUCED.json、independent-scalar-v1、AUDIT.json、readback-v1/run-v1、loadonly-pc-v1、CAPACITY_POLICY_PC.json。实际命令/退出码：contracts/config、prepare_01/02、numerics_01、loadonly_pc_01、policy_pc_01、package_01、source_review_01、upload/download、audit_01和各SSH reservation/receipt。prepare_01文本锚点断言失败以及未生成transport的本地命令失败保留；均在SSH执行前修复。所有历史封存逐字节核对，不修改旧失败或07通过结果。

无子代理、依赖升级、公共契约/核数学修改、默认切换、提交推送；实际模型和推理强度设置无法读取，记unknown。凭据仅隐藏交互，不入文件。唯一结论是可在重新通过门槛后受控进入08，本轮未启动08。
'''
    with (OUT/'REPORT.md').open('x',encoding='utf-8',newline='\n') as f:f.write(report)
    requirements=dict(status='PREREQUISITE_REVIEW_PASS_NOT_A_LAUNCH_PERMISSION',
       same_board_reference_required=True,original_cross_ISA_fail_preserved=True,
       full_weight_residency='PASS_72_WEIGHTS_148_BO_BOARD',explicit_BO_bytes=140591104,
       pre_allocation_CmaFree_after_pending_required_kib=98304,
       post_allocation_CmaFree_required_kib=98304,MemAvailable_required_kib=1114112,
       next_window_fresh_identity_and_kernel_and_locks_required=True,
       stage08_full_model_computation='NOT_TESTED',this_load_only_bundle_allows_compute=False,
       next_window_components='Explicitly reviewed new manager, ordinary Window v2, same-board S1 and capacity_policy live gate',
       accounting_policy='Deduct only still-pending BO; no RSS/PSS plus CMA summing',
       forbid='No compute from this load-only package; no global cache clearing; no threshold relaxation')
    save(OUT/'STEP08_PREREQUISITES.json',requirements)
    p=ROOT/'docs/PROJECT_STATUS.json';old=j(p)
    current={'role':old['role'],'a12_step06_failure_review_20261024':status,**{k:v for k,v in old.items() if k!='role'}}
    current['stage']='A12';current['stage_status']='IN_PROGRESS_STEP06_FAILURE_REVIEW_COMPLETE_STEP08_FRESH_WINDOW_ELIGIBLE'
    p.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=ROOT/name;s=p.read_text(encoding='utf-8');lines=s.splitlines(keepends=True)
        s=lines[0]+'\n'+summary+'\n\n'+''.join(lines[1:])
        if name.endswith('A12_STEP_PLAN_20261023.md'):
            anchor='### 08｜扩展 24 层、72 个目标投影并验证完整生成（BOARD）'
            s=s.replace(anchor,'### 第06步遗留失败复核（2026-10-24）\n\n- [x] 跨ISA整图失败复现，17组同输入独立复算通过；保留跨ISA限制，08使用同板S1/S2。\n- [x] 完整72权重/148BO实际驻留与原余量门槛通过，本轮模型核提交0；正常释放/独立及延时复核通过。\n- [x] 新增精确归档缓存处理和按已分配/待分配扣账的容量策略，PC测试并在板端探测中消费。\n- [x] 旧FAIL保持，新08窗口须新鲜门禁；完整计算/峰值/收益仍未测。详见 `evidence/model_pl_A/20261024-step06-review-v1/STEP08_PREREQUISITES.json`。\n\n'+anchor)
        p.write_text(s,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP06_FAILURE_REVIEW_COMPLETE_20261024.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as f:
        f.write('# A12 第06步遗留失败复核完成交接\n\n'+summary+'\n\n下一步仅在新的审核窗口进入08；读取REPORT.md和STEP08_PREREQUISITES.json。普通计算窗口使用独立审核的Window v2和最新容量策略，本轮load-only组件/许可不能用于计算。历史跨ISAFAIL与首次容量FAIL均不得覆盖；07已通过的9调用结果保持。板端当前无待收口进程/锁/租约（以本轮独立延时快照为准），后续必须重新实读，不能复用PID或假定资源不变。\n')
    print(json.dumps(dict(status=status['status'],report=status['report'])))

if __name__=='__main__':main()
