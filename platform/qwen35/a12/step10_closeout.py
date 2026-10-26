"""Write task10 results from audited measured data only; leave overall A12 task11 pending."""
import json
from datetime import datetime,timezone,timedelta
from common import ROOT,sha,save
from step10_common import OUT
def j(p):return json.loads(p.read_text(encoding='utf-8'))

def details(variant,name,side):
    return j(OUT/variant/'readback-v1/run-v1'/side/name/'result.json')

if __name__=='__main__':
    baseline=j(OUT/'BASELINE_AUDIT.json');optimized=j(OUT/'OPTIMIZED_AUDIT.json')
    assert baseline['status']=='PASS_BOARD_TASK10_BASELINE' and optimized['status']=='PASS_BOARD_TASK10_OPTIMIZED'
    supplements={v:j(OUT/(v.upper()+'_LIFECYCLE_SUPPLEMENT.json')) for v in ('baseline','optimized')}
    assert all(v['status']=='PASS_EXACT_ARCHIVED_LEASE_AND_COMPLETE_FINAL_SCAN' for v in supplements.values())
    assert j(OUT/'health_micro_01/receipt.json')['exit_code']==0
    micro=j(OUT/'health_micro_01/stdout.txt')
    assert micro['status']=='PASS_READ_ONLY_POST_CLOSEOUT_HEALTH_COMPONENT_TIMING' and len(micro['rows'])==10
    assert micro['accelerator_submissions']==micro['device_opens']==micro['mutations']==micro['signals']==0
    health_reads={k:dict(mean_ms=sum(r[k] for r in micro['rows'])/10,min_ms=min(r[k] for r in micro['rows']),max_ms=max(r[k] for r in micro['rows']))
        for k in ('boot_read_ms','kernel_read_ms','temperatures_total_ms','meminfo_read_ms')}
    assert sum(r['files'] for r in j(OUT/'HISTORICAL_PRESERVATION.json'))==24691
    comparisons=[]
    for a,b in zip(baseline['rows'],optimized['rows'][:4]):
        assert a['id']==b['id']
        comparisons.append(dict(id=a['id'],baseline_cpu_s=a['cpu']['client_complete_s'],baseline_pl_s=a['pl']['client_complete_s'],
            optimized_cpu_s=b['cpu']['client_complete_s'],optimized_pl_s=b['pl']['client_complete_s'],
            PL_before_over_after=a['pl']['client_complete_s']/b['pl']['client_complete_s'],
            same_outputs=True))
    breakdown=[]
    for variant,names in (('baseline',('natural_profile',)),('optimized',('natural_profile','context128_profile','context1024_profile'))):
        for name in names:
            for side in ('s1','s2'):
                r=details(variant,name,side);p=r['request_profile']
                phases=p['phases'];total=r['prefill_ms']+r['decode_ms']
                row=dict(variant=variant,id=name,side=side,total_decode_wall_ms=total,
                    mlp_wall_ms=sum(v['mlp_inclusive_wall_ms'] for v in phases.values()),
                    non_mlp_graph_ms=sum(v['non_mlp_cpu_graph_ms'] for v in phases.values()),
                    host_prepare_ms=sum(v['host_graph_prepare_schedule_ms'] for v in phases.values()),
                    gather_quant_copy_ms=sum(sum(v[k] for k in ('activation_gather_ms','activation_quant_ms','activation_cache_copy_ms','output_copy_ms')) for v in phases.values()),
                    sample_ms=p['sample_ms'],node_profile=p['node_profile'],phases=phases)
                if side=='s2':row['pl_profile']=p['pl_profile']
                row['mlp_fraction']=row['mlp_wall_ms']/total
                breakdown.append(row)
    summary=dict(status='PASS_A12_STEP10_PERFORMANCE_WITH_LIMITATIONS_TASK11_PENDING',
        updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),physical_domain='BOARD_SAME_ARM_CPU_AND_PL',
        real_calls=baseline['actual_calls']+optimized['actual_calls'],baseline_calls=baseline['actual_calls'],optimized_calls=optimized['actual_calls'],
        normal_mode=[r for r in optimized['rows'] if not r['profile']],light_profile_mode=[r for r in optimized['rows'] if r['profile']],
        comparisons=comparisons,breakdown=breakdown,fix_decision=j(OUT/'FIX_DECISION.json'),
        numerical_pairs='MATCH_TEXT_TOKENS_EOS_AND_PREFILL_LOGITS_FINGERPRINT_SAME_ARM',default_context=1024,
        mlp_timing_scope='GATE_UP_DOWN_LINEAR_CUSTOM_CALLBACKS; GLU_ACTIVATION_RESIDUAL_ARE_IN_OTHER_CPU_GRAPH',
        old_files_preserved=24691,normal_restore=True,independent_and_delayed_postchecks=True,
        default_FPGA_enabled=False,fallback='disabled',R0_full_replay=True,actual_model_settings='unknown',
        statistics='SMALL_DESCRIPTIVE_SAMPLE_NO_P95_OR_SIGNIFICANCE',
        startup_external_scope='CONTROLLER_START_CALL_TO_READY; PL_INCLUDES_PRESPAWN_ASSET_PROFILE_CHECKS; NOT_EXACT_FORK_TIMESTAMP',
        true_cold_cache_latency=None,physical_total_peak_bytes=None,device_cycles=None,AXI_measured_bytes=None,power_W=None,
        voice_latency=None,next_step='11_NOT_STARTED',A12_final='NOT_COMPLETE_TASK11_PENDING')
    summary['health_read_micro']=dict(domain='BOARD_CONTROL_READ_ONLY_AFTER_CLOSEOUT',samples=10,components=health_reads,in_model_benchmark=False)
    summary['performance_candidate']='runtime/qwen35_w4a8/a12/PERFORMANCE_CANDIDATE.json'
    save(ROOT/summary['performance_candidate'],dict(status='MEASURED_PRIVATE_CANDIDATE_NOT_DEFAULT',
        source='evidence/model_pl_A/20261024-step10-v1/source-v2',build='evidence/model_pl_A/20261024-step10-v1/BUILD-v2.json',
        bundle='evidence/model_pl_A/20261024-step10-v1/optimized/bundle-v1',
        manifest_sha256=sha(OUT/'optimized/bundle-v1/manifest.json'),default_enabled=False,
        provider='B',maintainer='A',public_contract_changed=False,
        next_use='FRESH_IDENTITY_BUDGET_DUAL_LOCK_LEASE_REQUIRED; CLOSED_TEST_LEASE_MUST_NOT_BE_REUSED'))
    save(OUT/'SUMMARY.json',summary)
    failures=dict(schema='A12_STEP10_FAILURE_LEDGER_V1',unexpected_execution_failures=[dict(
        domain='PC',case='MLP_down_node_name_ffn_out_was_not_in_timing_bucket',first='pc_native_01.json',exit_code=1,
        root_cause='The actual down projection node is ffn_out; the timer classified it as other',
        fix='source-v2 adds ffn_out to the MLP category; numerical sources unchanged',
        rerun='pc_native_02.json',rerun_exit_code=0,status='FIXED_ORIGINAL_BUILD_SOURCE_AND_FAILURE_PRESERVED')],
        transport_failures=[dict(case='interim_read_only_results_snapshot_02',
            receipt='optimized/results_progress_02/receipt.json',exit_code=255,
            observed='Connection closed by 192.168.2.2 port 22 before any snapshot output',
            cause='Precise SSH closure cause not proven; authentication was not observed to complete and snapshot stdout is empty',
            rerun='optimized/results_progress_03/receipt.json',rerun_exit_code=0,
            impact='No compute interruption; independent running monitor and final audited readback retained')],
        slow_samples='All normal and profile samples retained; no sample excluded for being slow',
        first_load='Fresh-process/page-cache state unproven; no global cache flush and no claim of true cold-cache timing',
        historical_failures_preserved=['step06_cross_ISA_whole_graph_FAIL','step06_first_full_capacity_FAIL',
            'step07_first_manager_closeout_FAIL_minus9','step08_FSBL_only_reboot_failure'],
        local_readonly_inspection_notes=['Several initial guessed read paths were absent; corrected using file inventory.',
            'One nested PowerShell/bash/Python inspection command had a quoting parser error; replaced with a saved Python source.',
            'A bounded stdout tail starts in the middle of a JSON line; parsed only complete lines for inspection.'],
        nonfatal_build_warnings='Preserved in real queue stderr: inherited compact C++ formatting, missing private C observer prototype, no Git metadata in build-local source copy',
        final_scans={k:{n:v[n] for n in ('full_scan_attempts','incomplete_transient_scans_preserved','forced_exit','finalize_ticket_used')} for k,v in supplements.items()},
        not_tested=['true cold file cache','2048 context','dangerous BOARD inflight timeout/POISONED/unplug',
            'power','hardware cycles and AXI traffic','whole-system physical peak','voice pipeline','statistical p95'])
    save(OUT/'FAILURES.json',failures)
    lines=['# A12 第10步：同板速度与瓶颈报告','',
      '第10步在冻结的小样本范围内完成。全部病例为合成教学数据，不代表医学审核通过。CPU/PL使用同一A53程序、模型、权重、24层72投影、TILED两线程、物理T≤8、1024上下文和R0。两者均在GDM停止后测量，按CPU→PL顺序执行；没有用重诊断CPU对照制造加速。所有普通模式仅取需要位置的logits，不做全层dump、消费者重trace或状态序列化。',
      '',f"真实PL调用共{summary['real_calls']}次。两窗口均正常退出、完整扫描后恢复默认PL/GDM，并完成独立和延时后验。历史九批24691个文件逐字节核对通过；原FAIL均保留。",'',
      '## 正常模式实际体验','',
      '| 样本 | 输入/输出token | CPU首token/完成 秒 | PL首token/完成 秒 | 本次CPU/PL完成时间比 |',
      '|---|---:|---:|---:|---:|']
    for r in optimized['rows']:
        if r['profile']:continue
        c=r['cpu'];p=r['pl']
        lines.append(f"| {r['id']} | {r['input_tokens']}/{p['output_tokens']} | {c['client_first_token_s']:.3f}/{c['client_complete_s']:.3f} | {p['client_first_token_s']:.3f}/{p['client_complete_s']:.3f} | {r['cpu_over_pl_speedup_request']:.3f} |")
    lines+=['','short是固定teacher token轨迹；natural是真实非思考贪心生成，输出“疼痛在胸骨后。”且EOS确认完成。token不是汉字。首token采用管理端发送请求到实际收到第一token的时间，包含R0清空、输入处理和正常IPC；完成采用收到有效最终结果，包含EOS计算、清空及最终报告。',
      '', '## 轻量分项与长输入','',
      '| 样本 | 输入token | CPU prefill/每decode步 秒 | PL prefill/每decode步 秒 | CPU/PL首token 秒 |',
      '|---|---:|---:|---:|---:|']
    for r in optimized['rows']:
        if not r['profile']:continue
        c=r['cpu'];p=r['pl']
        lines.append(f"| {r['id']} | {r['input_tokens']} | {c['native_prefill_s']:.3f}/{c['native_decode_s']/c['native_decode_steps']:.3f} | {p['native_prefill_s']:.3f}/{p['native_decode_s']/p['native_decode_steps']:.3f} | {c['client_first_token_s']:.3f}/{p['client_first_token_s']:.3f} |")
    lines+=['','128/1022输入为固定token的工作量代理，输出分别4/2个teacher token，不冒充自然长回答。长输入数字是轻量剖面实测，未按短样本开关比率校正成“正常模式”。普通/剖面开关的所有短输入和自然回答样本同时保留，见AUDIT和原始client-timing。',
      '', '## 瓶颈分账','',
      '| 窗口/样本/后端 | MLP线性回调 秒 | 其余CPU图 秒 | 图准备/调度 秒 |',
      '|---|---:|---:|---:|']
    for r in breakdown:lines.append(f"| {r['variant']}/{r['id']}/{r['side']} | {r['mlp_wall_ms']/1000:.3f} | {r['non_mlp_graph_ms']/1000:.3f} | {r['host_prepare_ms']/1000:.3f} |")
    lines+=['','MLP栏仅指gate/up/down三个线性投影的自定义回调，SiLU/GLU、残差等仍在其余CPU图中。回调内部再分线性调用、激活gather/量化/缓存与输出复制。PL线性调用内部再分同步完整服务、管理许可等待和完成报告。`backend.service_ms`不包含许可；`submit_to_confirmed_completion`是主机提交/轮询等待，不能当成纯硬件周期。所有嵌套区间经总耗时校核，不能把父子重复相加。',
      '', '节点时间使用原计算循环的thread0与既有屏障观察，未新增屏障、拆图、禁用融合或读取大输出。输出头、注意力相关投影/完整注意力、线性注意力、卷积及显式状态复制分桶保存在SUMMARY；融合组归首节点。GATED_DELTA_NET内的状态更新与线性注意力融合，独立状态更新时间未单独测得，不能填0或声称纯算子周期。',
      '', '## 已定位并修复的重复开销','',
      '先完成基线窗口和恢复，再按FIX_DECISION启用两项候选改进：私有完成读取器保留相同的完成状态、job/build/meta和错误检查，仅避免每次重复序列化稳定的BO清单；每次许可仍新鲜检查身份、内核、温度和资源并持久记录绑定观察，仅将生命周期中相同的重复健康日志合并至每秒一次，变化或拒绝立即记录。公共软件ABI、B核、数学、阈值、全部BO/租约和未知DMA隔离规则未改。',
      '', '| 样本 | 基线PL 秒 | 修复后PL 秒 | 基线/修复后时间比 |', '|---|---:|---:|---:|']
    for r in comparisons:lines.append(f"| {r['id']} | {r['baseline_pl_s']:.3f} | {r['optimized_pl_s']:.3f} | {r['PL_before_over_after']:.3f} |")
    lines+=['',f"计算结束、释放恢复后另做10次只读部件复测：温度读取均值{health_reads['temperatures_total_ms']['mean_ms']:.3f}毫秒/组三路，内核日志读取{health_reads['kernel_read_ms']['mean_ms']:.3f}毫秒，meminfo读取{health_reads['meminfo_read_ms']['mean_ms']:.3f}毫秒。这些是空闲下的读取成本，不混入模型时间，不代替请求内实际门禁总耗时；原始逐路温度读取见health_micro_01。",
      '', '修复前后CPU/PL输出token、文本、EOS和最终prefill logits摘要均匹配。首次PC分类失败（ffn_out漏计）及原构建、源码、重跑记录保留；31组1041项控制替身验证单列PC域，不冒充硬件数值或性能。',
      '', '## 加载、资源与结论边界','',
      '各窗口ready.json记录进程内模型/sidecar/context加载。startup-timing.json记录管理端启动调用到收到ready，其中PL包含启动前资产复核和私有配置；原字段process_launch不是精确fork时刻，不把它当作纯进程冷加载。文件页缓存冷热未经证明，没有全局drop_caches，不宣称测得真正冷缓存加载。进程最大RSS、MemAvailable/CmaFree最小值、温度和148个显式BO共140591104字节分别保留，不能把RSS与CMA重复相加为物理总峰值。',
      '', '所有样本和慢样本均保留，顺序未随机化，数量不足以报p95或统计显著。表中比率只属于本次同板配对样本。功耗、真实硬件周期、AXI总线字节/有效带宽、整机物理峰值和语音ASR/TTS/播放时延仍为null。',
      '', 'R0每轮重新计算完整输入的成本真实存在，长输入首字等待不能当作诊断开销消除。默认FPGA仍关闭，任务11的A12总收口尚未执行；本轮每个实际窗口的正常结束与资源释放已经完成。',
      '', '原始证据：BASELINE_AUDIT.json、OPTIMIZED_AUDIT.json、FIX_DECISION.json、SUMMARY.json、FAILURES.json、两份LIFECYCLE_SUPPLEMENT，以及两窗口readback-v1中的逐请求结果/计时/许可与生命周期日志。']
    report='\n'.join(lines)+'\n';(OUT/'REPORT.md').write_text(report,encoding='utf-8',newline='\n')
    p=ROOT/'docs/PROJECT_STATUS.json';status=j(p);status['a12_step10_performance_20261024']=summary;status['stage']='A12';status['stage_status']=summary['status']
    p.write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    note=f"2026-10-24 A12第10步完成：同板CPU/PL公平小样本普通模式与轻量分项、完整病例回答及128/1022输入通过独立审计；真实PL {summary['real_calls']}次，重复完成报告/健康日志已按基线定位并在新窗口验证修复，输出token/文本/EOS和prefill摘要匹配。任务09与历史FAIL/24691文件保持；两窗口正常恢复并独立/延时复核。速度、瓶颈和样本时间比见 `evidence/model_pl_A/20261024-step10-v1/REPORT.md`；无p95/统计显著、物理总峰值/功耗/硬件周期/AXI字节仍null。默认FPGA关闭，R0长输入成本保留，A12任务11未完成。下方为历史快照。\n\n"
    for name in ('docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md'):
        p=ROOT/name;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    p=ROOT/'docs/A12_STEP_PLAN_20261023.md';s=p.read_text(encoding='utf-8');a=s.index('### 10｜');b=s.index('### 11｜',a)
    s=s[:a]+s[a:b].replace('- [ ]','- [x]')+'2026-10-24：10按小样本/融合状态/资源测量边界完成；真实冷缓存与硬件周期/AXI/功耗未测，详见REPORT。\n\n'+s[b:]
    p.write_text(s,encoding='utf-8',newline='\n')
    with (ROOT/'docs/handoffs/A_A12_STEP10_COMPLETE_20261024.md').open('x',encoding='utf-8',newline='\n') as f:f.write(report+'\n下一步仅任务11总收口。既有重启/冷启动专项票据均已消费，本轮无新增电源、重启或刷写授权。\n')
    print(json.dumps(dict(status=summary['status'],real_calls=summary['real_calls'],next='11_NOT_STARTED')))
