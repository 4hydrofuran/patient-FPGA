"""Write task09 reviewable results only after all BOARD audits and closeout proofs."""
from datetime import datetime,timezone,timedelta
import json
from common import ROOT,sha,save
from step09_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    short=j(OUT/'SHORT_AUDIT.json');context=j(OUT/'CONTEXT_AUDIT.json')
    assert short['status']=='PASS_BOARD_TASK09_SHORT' and context['status']=='PASS_BOARD_TASK09_CONTEXT'
    for v in ('short','context'):assert j(OUT/(v.upper()+'_LIFECYCLE_SUPPLEMENT.json'))['status']=='PASS_EXACT_ARCHIVED_LEASE_AND_COMPLETE_FINAL_SCAN'
    assert j(OUT/'POLICY_PC.json')['status']=='PASS_7_POLICY_ROUTES_NO_MODEL_NO_HW'
    preserved=j(OUT/'HISTORICAL_PRESERVATION.json');assert sum(r['files'] for r in preserved)==16202
    summary=dict(status='PASS_A12_STEP09_STATE_CANCEL_BOARD_WITH_LIMITATIONS',updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),physical_domain='PC_AND_BOARD_SEPARATE',default_context=1024,long_input_tokens=1022,long_output_token_limit=2,physical_T=[1,2,4,8],tail_T=1,real_calls=short['actual_calls']+context['actual_calls'],short_real_calls=short['actual_calls'],context_real_calls=context['actual_calls'],diagnostic_real_consumed_outputs=short['diagnostic_real_consumed_outputs'],short_logits_and_raw_states='BIT_EXACT_ACROSS_T_AND_SAME_ARM_S1_S2',default_context_state_fingerprint_and_prefill_logits='MATCH_SAME_ARM_S1_S2_AND_CHUNK8_256',default_context_direct_full_vocab_comparison='ZERO_DIFFERENCE',R0='CLEAR_ALL_RECURRENT_CONV_KV_AND_REPLAY',R1_R2='DISABLED_REJECTED',medical_case_switch='SYN_CP_01_TO_SYN_CP_02_TO_SYN_CP_01_MATCH',cancel='CONFIRMED_COMPLETION_BOUNDARY_NO_NEW_SUBMIT_LATE_RESULT_DISCARDED',cancelled_worker_reuse='REFUSED',post_cancel_new_worker_window='MATCH_BASELINE',policy_items_PC_no_model=7,ARM_startup_negatives=2,negative_exit_code=2,positive_worker_exits=[0,0,0,0],manager_exits=[0,0],normal_default_restore=True,independent_and_delayed_postchecks=True,default_FPGA_enabled=False,fallback='disabled',extension2048='NOT_TESTED',BOARD_inflight_timeout_poison_removal='NOT_TESTED',old_files_preserved=16202,hardware_global_count=None,physical_peak_bytes=None,board_speedup=None,next_step='10_NOT_STARTED',A12_final='NOT_COMPLETE_TASK10_11_PENDING',actual_model_settings='unknown')
    summary['final_scan_observations']={v:{k:j(OUT/(v.upper()+'_LIFECYCLE_SUPPLEMENT.json'))[k] for k in ('full_scan_attempts','incomplete_transient_scans_preserved','final_complete_scan','forced_exit','finalize_ticket_used')} for v in ('short','context')}
    summary.update(state_test_generation='TEACHER_FORCED_TOKENS_10_11',cancel_native_output_limit=64)
    summary['performance_status']='STEP10_NOT_BENCHMARKED_CURRENT_LONG_INPUT_LATENCY_IS_A_PRODUCT_RISK'
    summary['R0_full_prefill_latency_risk']=True
    save(OUT/'SUMMARY.json',summary)
    assert j(OUT/'app_state_pc_02.json')['exit_code']==0
    failures=dict(schema='A12_STEP09_FAILURE_LEDGER_V1',unexpected_execution_failures=[dict(case='Windows_GBK_decoding_UTF8_fixture_in_existing_policy_test',domain='PC',initial_exit_code=1,initial_receipt='app_state_pc_01.json',root_cause='Path.read_text without explicit encoding used GBK on Windows',fix='explicit UTF-8 in system_qwen35/app/default_e2e/test_policy.py',rerun_receipt='app_state_pc_02.json',rerun_exit_code=0,tests=17,status='FIXED_ORIGINAL_FAILURE_PRESERVED')],expected_rejections=[dict(case='native_missing_library_wrong_contract_forbidden_fallback',domain='PC',count=3,expected_exit_code=2,receipts=['missing_library-receipt.json','wrong_contract-receipt.json','forbidden_fallback-receipt.json']),dict(case='required_artifact_missing_wrong_contract',domain='BOARD_ARM_STARTUP',count=2,expected_exit_code=2,receipt='context/readback-v1/run-v1/startup-negative/SUMMARY.json'),dict(case='R1_R2_disabled',domain='PC_AND_BOARD',output='error_state_cleared'),dict(case='safe_boundary_cancel',domain='BOARD',output='CANCELLED_partial_output_unusable_permits_denied_late_result_discarded')],historical_failures_preserved=['step06_cross_ISA_whole_graph_FAIL','step06_first_full_capacity_FAIL','step07_first_manager_closeout_FAIL_actual_minus9','step08_normal_reboot_FSBL_only_cause_unresolved'],local_tooling_notes=['One ad-hoc Python -c command failed with a PowerShell quoting SyntaxError; replaced by checked Python source, no board action occurred.','PC_MATRIX policy collector used uppercase route labels and collected zero; independent POLICY_PC audit executes and validates all seven lowercase actual application routes.'],not_tested=['BOARD_inflight_timeout_POISONED_unknown_DMA_recovery','physical_device_unplug','2048_context_extension','performance_power_physical_total_peak','medical_review'])
    failures['nonpassing_scan_observations_preserved']=summary['final_scan_observations']
    save(OUT/'FAILURES.json',failures)
    table='''| 项目 | 验证域与结果 |
|---|---|
| T1/2/4/8、9-token 尾块、连续 decode | PC + 同板 CPU/PL；40 行全词表 logits、原始混合状态及抽样投影核验通过 |
| R0/reset、两份合成病例 A→B→A、R1/R2 拒绝 | 同板 CPU/PL；清空后重算及 A 重放匹配 |
| 取消、迟到输出、旧 worker 复用拒绝 | BOARD；已完成调用之后、下一次许可之前取消；无新提交，正常关闭 |
| 取消后新请求 | BOARD；完整释放恢复后使用新 worker/新窗口，结果匹配原基线 |
| 默认 1024 上下文 | 同板 CPU/PL；1022 输入 + 2 输出预算，chunk8/256 状态指纹及最终 prefill logits 匹配，进程内全词表差异0 |
| 缺必需产物、错契约版本 | 实际 ARM 程序在设备打开许可前 exit2 拒绝，模型不就绪、不回退 |
| 应用拒绝/澄清策略7条 | PC，模型/硬件调用0；不冒充 BOARD 模型生成 |
| timeout/POISONED/未知 DMA | PC 控制替身31组764项；危险 BOARD 注入 NOT_TESTED |
| 正常释放与独立后验 | 两窗口 worker/manager exit0，默认PL/GDM恢复；无ZOCL/设备用户/锁/active lease |
'''
    report=f'''# A12 第09步报告

第09步在声明范围内通过，可进入第10步有界同板性能比较。实际 PL 调用 {summary['real_calls']} 次，其中短矩阵 {short['actual_calls']} 次、默认上下文 {context['actual_calls']} 次；四种分块共 {short['diagnostic_real_consumed_outputs']} 次输出保存了真实消费者证据。数学、权重、阈值和公共契约未改。

正常分块/会话对照使用固定teacher token `[10,11]`，用于检查状态与数值；取消用例使用最多64 token的有界原生生成。自然语言质量仍引用第08步的独立开发集证据。

“提交一次”按一个SP_LINEAR投影计算任务计。当前24层、每层gate/up/down三个投影，一批token经过完整目标范围通常需要72次提交；一批最多8个token。1022-token输入分128批，prefill9216次，再加一次decode72次，每条长输入9288次。提交次数不是token数或病例数，也不是硬件全局计数；最终数值已与成功完成、job编号及返回状态核对。

{table}

取消位置是同步调用完成后等待下一次提交许可的安全边界，记录中在途数为0；这不证明在途超时、POISONED 或拔除硬件可自动恢复。已取消结果只供审计，`partial_output_usable=false`，不交付；旧 worker 永久拒绝新请求，后续使用全新窗口。没有强杀、强卸载、重启或供电操作。

1024 为应用实际默认配置，固定输入1022 token、最多输出2 token；最后一个输出不再重复推进状态，状态位置另有逐项断言。短矩阵保留原始全词表 logits 和混合状态；长输入受诊断上限约束，保存状态指纹、prefill 指纹及进程内全词表直接比较结果，不宣称保存了长输入完整逐层 dump。2048 扩展未测。

每窗口72份权重仅加载一次，148个显式BO共140591104字节复用；取消后新窗口重新加载属于新生命周期。各窗口结束链已执行，任务10性能比较和11阶段总收口尚未开展，A12尚未整体收口。硬件全局计数、物理总峰值、功耗和加速比均为null，默认FPGA未启用。应用策略模板验证为PC域，医学审核仍未完成。

当前整轮等待包括串行CPU/PL对照、加载、测试监督、日志与恢复，不能直接作为成品单请求时延；其中真实模型计算和PL传输等待仍是实际开销。长输入耗时已提示交互延迟风险，不能承诺最终会明显变快；任务10须用公平的正常模式明确prefill、首token、decode及完整回答耗时，语音整机另计ASR/TTS/播放。

R0每请求清空状态并重新计算完整输入，是当前默认策略的真实成本；成品若继续采用R0，长上下文的这部分等待同样存在，不能当成可关闭的诊断开销。

最终扫描的全部观察次数及短暂不完整记录见SUMMARY的`final_scan_observations`；不完整观察不会被提升为PASS，只有完整FD/VMA/进程复核通过才归档释放。本轮两管理器均正常exit0，未使用finalize专项票据或强制退出。

发现并修复了既有策略测试在Windows默认GBK下读取UTF-8中文fixture失败的问题，仅明确读取编码，17项应用会话/策略测试重跑通过。首次失败、修改前文件和重跑均保留。本轮预期失败/拒绝及所有原始日志见 `FAILURES.json`。任务6两项旧FAIL、首次收口失败和任务8 FSBL启动失败均保留；此前八批16202个封存文件逐字节核对通过。细项见 `SHORT_AUDIT.json`、`CONTEXT_AUDIT.json`、两份 `LIFECYCLE_SUPPLEMENT.json`、`PC_MATRIX.json`、`POLICY_PC.json` 和状态矩阵。
'''
    (OUT/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    (OUT/'STATE_MATRIX.md').write_text('# A12 task09 状态矩阵\n\n'+table,encoding='utf-8',newline='\n')
    status=j(ROOT/'docs/PROJECT_STATUS.json');status['a12_step09_state_cancel_20261024']=summary;status['stage']='A12';status['stage_status']=summary['status']
    (ROOT/'docs/PROJECT_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    paragraph=f"2026-10-24 A12第09步完成（PC/BOARD分域、保留限制）：T1/2/4/8及尾块、连续decode、R0/reset、两份合成病例切换重放、R1/R2拒绝通过；同板CPU/PL短logits和原始混合状态逐位一致。默认1024上下文以1022输入+2输出预算验证chunk8/256，状态/最终prefill指纹匹配，进程内全词表差异0。真实PL共{summary['real_calls']}次；完成边界取消后禁止新submit、丢弃迟到结果、旧worker不可复用，正常恢复后新窗口匹配基线。实际ARM两项启动拒绝exit2、无设备打开许可/静默回退；策略7条为PC无模型。两窗口正常exit0并独立/延时复核释放恢复；旧FAIL及16202历史文件保留。2048、危险BOARD在途超时/POISONED/拔除未测，默认FPGA关闭，性能/物理总峰值null；10/11未做。报告 `evidence/model_pl_A/20261024-step09-v1/REPORT.md`。下方为历史快照。\n\n"
    paragraph=paragraph.replace('性能/物理总峰值null','R0长输入交互延迟风险待10实测，性能/物理总峰值null')
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md'):
        p=ROOT/name;p.write_text(paragraph+p.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';s=p.read_text(encoding='utf-8');begin=s.index('### 09｜');end=s.index('### 10｜',begin)
    section=s[begin:end].replace('- [ ]','- [x]')+'2026-10-24：09在分域与边界限制内通过；2048与危险BOARD故障注入保持NOT_TESTED，不追认为通过；详见本轮REPORT/STATE_MATRIX。\n\n'
    p.write_text(s[:begin]+section+s[end:],encoding='utf-8',newline='\n')
    handoff=ROOT/'docs/handoffs/A_A12_STEP09_COMPLETE_20261024.md'
    with handoff.open('x',encoding='utf-8',newline='\n') as f:f.write(report+'\n\n下一步仅任务10：冻结公平的同板性能样本、顺序、时间/调用预算；沿用当前irq2、固定SSH身份和双锁租约。一次正常重启与一次冷启动的旧专项授权均已消费，不得再次自动触发。\n')
    print(json.dumps(dict(status=summary['status'],real_calls=summary['real_calls'],next='10_NOT_STARTED'),ensure_ascii=False))
