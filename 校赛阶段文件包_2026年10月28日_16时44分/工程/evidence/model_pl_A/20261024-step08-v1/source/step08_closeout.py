"""Publish task08 hardware, numerical, language and lifecycle results separately."""
import datetime
import json
from common import ROOT,sha,save
from step08_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    d=j(OUT/'DIAGNOSTIC_AUDIT.json');g=j(OUT/'GENERATION_AUDIT.json');q=j(OUT/'DEV_QUALITY.json')
    assert d['status']=='PASS_BOARD_ALL_24_LAYERS_216_REAL_CONSUMED_OUTPUTS'
    assert g['status']=='PASS_BOARD_ALL_FROZEN_DEV_PAIRED_GENERATION'
    assert j(OUT/'GENERATION_CALL_ACCOUNTING.json')['status']=='PASS_ACTUAL_COUNTS_MATCH_PINNED_FINAL_LOGITS_GRAPH'
    supplements={v:j(OUT/(v.upper()+'_LIFECYCLE_SUPPLEMENT.json')) for v in ('diagnostic','generation')}
    assert all(a['status']=='PASS_EXACT_ARCHIVED_LEASE_AND_COMPLETE_FINAL_SCAN' for a in supplements.values())
    assert d['lifecycle']['normal_restore'] and g['lifecycle']['normal_restore']
    assert j(OUT/'BOOT_RECOVERY_AUDIT.json')['status']=='RECOVERED_IRQ2_AND_VOLATILE_NETWORK_DEFAULT_BOOT_UNCHANGED'
    for name in ('contracts_01','config_01','health_pc_01','pc_graph_01','audit_diagnostic_01','audit_generation_01','diag_lifecycle_01','gen_lifecycle_01','quality_01','call_accounting_01','preservation_01','recovery_audit_01'):
        assert j(OUT/(name+'.json'))['exit_code']==0,name
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    status=dict(status='PASS_A12_STEP08_FULL_MODEL_BOARD_WITH_LIMITATIONS',updated_beijing=now,
        physical_domain='BOARD',layers=24,projections=72,diagnostic_real_consumed_outputs=d['actual_calls'],
        diagnostic_numerics='BIT_EXACT_MATCHED_BOARD_S1_S2',generation_model_requests=len(g['cases']),
        generation_real_calls=g['actual_calls'],generation_pairs='TOKENS_TEXT_EOS_STATE_PREFILL_FINGERPRINT_MATCH',
        policy_template_items=q['policy_templates'],policy_template_domain='PC_NO_MODEL',
        language_quality_status=q['status'],language_checker_counts=q['model_checker_counts'],
        raw_language_failures_preserved=True,model_EOS=q['model_EOS_count'],
        weight_loads_per_window=72,steady_explicit_BO_count=148,explicit_BO_bytes=140591104,
        normal_restore_both_windows=True,default_PL_restored=True,GDM_active=True,ZOCL_absent=True,
        final_scan_attempts={v:a['full_scan_attempts'] for v,a in supplements.items()},
        active_lease=False,held_locks=False,manager_and_workers_exit_zero=True,
        default_boot_changed=False,temporary_network_unsaved=True,warm_reboot_stall='PRESERVED_UNRESOLVED_CAUSE',
        original_task06_failures='PRESERVED',cross_ISA_equivalence='FAIL_PRESERVED',
        natural_per_call_Y_trace='DISABLED_NORMAL_MODE_DIAGNOSTIC216_VERIFIED',
        default_FPGA_enabled=False,medical_review='PENDING_NOT_CLAIMED',physical_peak_bytes=None,
        hardware_global_counter=None,speedup=None,step09='NOT_STARTED',subagents=0,model_settings='unknown',
        report='evidence/model_pl_A/20261024-step08-v1/REPORT.md',committed=False,pushed=False)
    save(OUT/'SUMMARY.json',status)
    failures=[dict(id='prepare_01',domain='PC',exit_code=1,problem='Transcript source text/final missing',resolution='Typed final transcript prepared; prepare_02 passed'),
        dict(id='ssh_before_recovery',domain='TRANSPORT',exit_code=255,problem='Default1036 kernel had no direct IPv4',resolution='Authorized temporary irq2 cold boot and unsaved NM profile restored connection'),
        dict(id='uart_network_01',domain='READONLY_TRANSPORT',exit_code=2,problem='Existing reader rejected login prompt',resolution='Explicit prompt-verified hidden UART login'),
        dict(id='restore_once_01',domain='PRE_REBOOT_GUARD',problem='Canonical tmpfs lock absent after boot',resolution='Safe root O_CREAT/NOFOLLOW/exclusive lock initialization; this failed attempt sent no reboot'),
        dict(id='normal_reboot_fsbl',domain='BOARD_BOOT',problem='One actual normal reboot produced only FSBL prefix; no U-Boot/Linux observed',resolution='User-authorized one manual cold cycle restored irq2; warm reset cause not fixed; raw failure retained'),
        dict(id='cold_wait_01',domain='UART_WAIT',problem='No fresh power-on log in first300sec passive window',resolution='No bytes/boot commands sent; re-armed before user-reported one cold cycle'),
        dict(id='network_prefix_scope',domain='LOCAL_GENERATOR',exit_code=1,problem='Dot-sourced param reset OutputPath',resolution='Reserve input before source; no UART command from this rejected invocation'),
        dict(id='network_pin_reservation',domain='LOCAL_GENERATOR',exit_code=1,problem='Exclusive old pin file already exists',resolution='Kept old pin and wrote distinct v2/v3/v4 receipts'),
        dict(id='network_empty_ipv4',domain='UART_ROOT_GUARD',exit_code=1,problem='ip -j -4 with no IPv4 returned empty list',resolution='Read exact eth0 link and filter inet; failure occurred before address addition'),
        dict(id='network_ip_cleared',domain='BOARD_NETWORK',exit_code=255,problem='NetworkManager removed raw volatile ip addr addition',resolution='One new unsaved NM manual profile; stable pinned SSH afterward'),
        dict(id='generation_time_budget_v1',domain='UNEXECUTED_DRAFT',problem='Original1200sec total/120sec receive insufficient for measured guarded full graph',resolution='Explicit time-only v2 saved before any dev execution; original workload47736permits/17requests/24output limit and resource/numeric gates unchanged'),
        dict(id='static_final_02',domain='LOCAL_READONLY_CHECK',exit_code=1,problem='Exclusive STATIC_REVIEW.json already exists',resolution='Added explicit distinct output-name; original retained, static_final_03 passed'),
        dict(id='powershell_parse_01',domain='LOCAL_READONLY_CHECK',exit_code=1,problem='Default process script execution policy rejected the parser script before running',resolution='Used process-only ExecutionPolicy Bypass for reviewed parse-only script; no system policy change; powershell_parse_03 passed'),
        dict(id='powershell_parse_02',domain='LOCAL_READONLY_CHECK',exit_code=1,problem='Child Windows PowerShell lacked Get-FileHash cmdlet',resolution='Used portable .NET SHA256 without installation or module changes; powershell_parse_03 passed'),
        dict(id='final_scan_transient_reads',domain='BOARD_FINALIZATION_OBSERVATION',attempts={v:a['full_scan_attempts'] for v,a in supplements.items()},problem='Process-set/FD-table changes can reject an incomplete observation',resolution='Every rejected observation retained. V2 accepts only a later fresh complete no-users scan; normal exit and independent archived lease hash verified. No failed scan promoted to PASS'),
        dict(id='dev_raw_quality',domain='BOARD_MODEL_LANGUAGE',status=q['status'],counts=q['model_checker_counts'],token_limit_without_EOS=q['model_token_limit_without_EOS'],resolution='Raw outputs and checker decisions retained; no replacement or automatic CPU/template fallback'),
        dict(id='step06_failures',domain='HISTORICAL',status='PRESERVED',resolution='No edits to old evidence or thresholds; same-board S1/S2 used as already reviewed')]
    save(OUT/'FAILURES.json',failures)
    text=(f'2026-10-24 A12第08步完成（有限范围、保留限制）：24层72投影完整诊断，216次真实PL返回Y及消费者核验通过；逐层输入输出、节点、10行logits和混合状态与同板S1逐位一致。冻结开发集17条同板CPU/PL自然生成配对通过，PL实际{g["actual_calls"]}次；7条策略模板单列为PC无模型，原始语言检查{q["model_checker_counts"]}，医学审核未完成。每窗口72份权重只加载一次、148BO共140591104B复用；两窗口worker/manager正常exit0，默认PL/GDM恢复，独立及延时复核无ZOCL/设备用户/锁/active lease。一次正常重启仅FSBL的失败保留，专项授权冷启动恢复irq2，默认启动文件不变；直连使用未保存NM配置。06旧FAIL保留；正常生成关闭逐调用Y诊断账，216次重诊断证明单列。默认FPGA未启用，物理峰值/硬件全局计数/加速比null；09未启动。报告 `evidence/model_pl_A/20261024-step08-v1/REPORT.md`。下方为历史快照。')
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/A12_STEP_PLAN_20261023.md'):
        p=ROOT/name;old=p.read_text(encoding='utf-8');p.write_text(text+'\n\n'+old,encoding='utf-8',newline='\n')
    p=ROOT/'docs/PROJECT_STATUS.json';current=j(p)
    assert 'a12_step08_full_model_20261024' not in current
    current={'a12_step08_full_model_20261024':status,**current};current['stage']='A12';current['stage_status']=status['status']
    p.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';plan=p.read_text(encoding='utf-8')
    start=plan.index('### 08｜');end=plan.index('### 09｜',start)
    plan=plan[:start]+plan[start:end].replace('- [ ]','- [x]')+plan[end:]
    p.write_text(plan,encoding='utf-8',newline='\n')
    resources={name:a['lifecycle'] for name,a in (('diagnostic',d),('generation',g))}
    report=f'''# A12 第08步：全模型真实PL消费与自然生成

状态：{status['status']}。执行日期（北京时间）：{now}。

## 实板结果

诊断窗口覆盖24层gate/up/down共72投影，实际216次真实PL调用，job1—216，每投影T8/1/1。逐次ERT=4、build0xB3030002、raw64Bmeta、job回显、原始Y摘要与GLU/残差消费者关联全部通过。不是仅有调用而未消费。原始216份输入/输出、10行全词表logits、诊断节点和20312900B混合状态与同板同一ARM产物S1逐位一致；算子1e-4+1e-5*abs(ref)、整图.002+.0002*abs(ref)门槛未改。PC反事实丢弃Y仍被拒绝。

自然生成使用冻结开发集，17条模型请求，输入PC/ARM分词一致，每条最多24个输出token，final-logits、物理ubatch上限8、R0清空状态；完整17条同板S1/S2的token、文字、EOS、prefill末logits指纹和最终状态指纹一致。实际PL提交{g['actual_calls']}次，详见GENERATION_AUDIT.json。正常模式关闭逐调用消费者账以避免重诊断二次方拷贝，不能把自然生成每次调用称为已保存Y哈希；重诊断216次消费者证据单独成立。正常final-logits仅请求末位置；当前固定运行时embeddings_nextn_masked未启用，在最后MLP/norm之后选择输出行，MLP仍按全部实际microbatch执行。每条实际完成数与72*(ceil(prompt_tokens/8)+decode_calls)独立核对；不声称省略了最后层MLP。正常生成每层/每调用实际T未逐项留账，不据此宣称09尾块矩阵通过。源码快照见SCHEDULING_SOURCE_qwen35.cpp，调用分账见GENERATION_CALL_ACCOUNTING.json。

7条策略拒绝/澄清模板来源为PC既有策略，不算作BOARD模型生成；模板比例7/24。模型原始有限语法检查：{q['model_checker_counts']}，EOS{q['model_EOS_count']}/17，24token上限但无EOS项：{q['model_token_limit_without_EOS']}。失败或不确定原文及事实、否定、数字核对逐项保存在DEV_QUALITY.json；不替换原文、不以模板或CPU掩盖。有限检查器不是医学审核，医学审核保持PENDING。

## 资源和正常收口

两个独立窗口均实际加载72份权重一次，148显式BO共140591104B；group3、8192字节分配charge、低2GiB、逐BO非重叠、请求前后地址/活权重不变与加载计数稳定通过。稳态不按token重传权重。资源余量与健康采样：

```json
{json.dumps(resources,ensure_ascii=False,indent=2)}
```

两窗口CPU/PL worker与manager实际exit0；完整FD/VMA/refcount门禁、普通卸载、ZOCL退出、默认PL与GDM恢复、唯一租约归档及双锁释放通过；独立及延时复核均确认无设备用户和已知进程。最终收口扫描尝试次数为{status['final_scan_attempts']}，进程集合/FD表变化导致的不完整读数原样保留，仅后续真正完整的no-users扫描被接受；另用身份、manager start_ticks、期限和预算独立重建租约JSON字节，归档SHA与两次独立后验一致，详见两个LIFECYCLE_SUPPLEMENT。未使用强杀、强卸载、复位或故意DMA故障。主机许可/完成计数不冒充硬件全局计数。

## 恢复与保留失败

起始板卡已回默认1036且无IPv4，未提交模型计算。专项授权的一次正常重启仅观察到FSBL前缀，未进入U-Boot/Linux，失败原文保留、根因未查明。经用户专项授权和实际一次拔电等待5秒再上电，固定COM5捕获启动；RAM加载irq2 FIT及三个组件校验通过后只发送一次临时bootm。未saveenv、未刷写、默认image.fit/boot.scr哈希与前件一致。新boot86e4938b-0f65-4166-9237-c547b67e1451，内核6.8.12-a10irq2。

原始ip addr添加被NetworkManager清除，SSH中途超时保存。改为明确save no/autoconnect no/never-default的临时NM连接，D-Bus Unsaved=b true；没有写永久网络配置。首次空IPv4处理IndexError、脚本参数作用域和排他收据生成失败均保留，见FAILURES.json及network-failed-*。已读回root重启前门禁与唯一systemctl调用收据。

新内核基线已有189行诊断（旧接受快照260行），含既有X.509、pinctrl、TPM等启动限制；比较差异仅X.509告警CPU/寄存器变化，原始日志不删，不称无告警内核。新窗口只接受既有精确动作例外，其余新诊断闭锁。

生成原草稿总1200秒/单次120秒未经执行；短诊断实测PL prefill约32.4秒、decode约26.2秒，表明整套17对正常生成需要更长时间。执行前另存generation-budget-v2.json（总18000秒/接收1200秒），保留原稿，47736总许可/17请求/每条24输出以及所有资源/温度/数值门槛不变。期限到达仍只取消后续交付，不授权kill或释放未知DMA。

## 限制与下一步

06跨ISA整图FAIL、首次容量FAIL与07旧收口FAIL/-9均保留；本轮使用已审阅的同板S1/S2基准。默认计算manifest仍CPU_REFERENCE，未启用默认FPGA；未改公共契约、数学、核、模型或sidecar。物理总峰值、硬件周期/全局计数、功耗、加速比均null。运行耗时含大量诊断/耐久门禁记录，不作为10步公平性能结论。09状态/分块/取消矩阵未执行，10性能和11最终A12收口未完成，医学审核未完成。

全部旧13240文件逐字节保护检查与新封存见HISTORICAL_PRESERVATION.json/SEAL.json。未自动切换模型（实际设置unknown）、未启用子代理、未提交或推送。
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP08_COMPLETE_20261024.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as f:f.write(text+'\n\n'+report)
    print(json.dumps(dict(status=status['status'],actual_diagnostic_calls=216,actual_generation_calls=g['actual_calls'],model_requests=17,quality=q['status']),ensure_ascii=False))
