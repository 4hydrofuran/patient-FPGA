"""Seal authorized C03 engineering scope; explicitly disclose microphone and history gaps."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];CROOT=ROOT.parent;OUT=ROOT/'evidence/c03'


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    if (OUT/'artifact_manifest.json').exists():raise RuntimeError('Never overwrite a historical stage seal')
    if not re.search(r'Ran 89 tests in .*\n\s*OK\s*$',(OUT/'unittest_final.log').read_text(encoding='utf-8')):
        raise ValueError('89 checks must pass with no skips')
    bench=read(OUT/'benchmark/report.json');paced=bench['summaries']['paced'];fast=bench['summaries']['unpaced']
    if (fast['successes'],paced['successes'],fast['same_as_c01'],paced['same_as_c01'])!=(42,14,42,14):
        raise ValueError('Development runs failed or changed text; retain and investigate')
    edges=read(OUT/'edges/report.json');analysis=read(OUT/'analysis.json');scope=read(OUT/'microphone_scope.json')
    if edges['successes']!=21 or edges['failures'] or scope['microphone_opened'] or analysis['pacing']['premature_chunks']:
        raise ValueError('Unexpected edge or pacing scope result')
    commands=[dict(command='.venv/Scripts/python.exe tools/prepare_c03.py',exit_code=0,log='evidence/c03/prepare.log'),
        dict(command='.venv/Scripts/python.exe -m unittest discover -s tests -v (initial inherited tests)',exit_code=0,log='evidence/c03/inherited_regression.log',tests=67,
            adverse_effect='TWO_C02_PROBE_JSON_FILES_OVERWRITTEN; DISCLOSED_AND_NOT_FABRICATED_BACK'),
        dict(command='.venv/Scripts/python.exe tools/smoke_c03.py',exit_code=0,log='evidence/c03/smoke.log'),
        dict(command='.venv/Scripts/python.exe -m unittest discover -s tests -v',exit_code=0,log='evidence/c03/unittest_initial.log',tests=85,
            environment=dict(VOICE_C_TEST_EVIDENCE_DIR='evidence/c03/regression_initial')),
        dict(command='.venv/Scripts/python.exe tools/benchmark_c03.py',exit_code=0,log='evidence/c03/benchmark.log',runs=56),
        dict(command='.venv/Scripts/python.exe tools/collect_c03_edges.py',exit_code=0,log='evidence/c03/edges.log',runs=21),
        dict(command='.venv/Scripts/python.exe -m unittest discover -s tests -v',exit_code=0,log='evidence/c03/unittest_final.log',tests=89,
            environment=dict(VOICE_C_TEST_EVIDENCE_DIR='evidence/c03/regression_final')),
        dict(command='.venv/Scripts/python.exe tools/stream_c03_file.py --wav data/c01_public/<first manifest audio_path> --output evidence/c03/standalone_client',
            argument_note='Input path resolved from first preselected public manifest record in the actual PowerShell command',exit_code=0,log='evidence/c03/standalone_client.log'),
        dict(command='.venv/Scripts/python.exe tools/analyze_c03.py',exit_code=0,log='evidence/c03/analysis.log')]
    write(OUT/'commands.json',dict(working_directory=str(ROOT),python=str(ROOT/'.venv/Scripts/python.exe'),commands=commands,
        journal_scope='TOOL_RETURNED_EXIT_CODES_AND_LOGS; INLINE_BASELINE_AUDIT_IN_TOOL_HISTORY',network='NO_RUNTIME_NETWORK_REQUESTS'))
    write(OUT/'verification.json',dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        status='PASS_AUTHORIZED_PC_ENGINEERING_MICROPHONE_AND_HUMAN_QUALITY_PENDING',execution_kind='PC_REAL',
        tests=dict(run=89,passed=89,skipped=0,inherited_c00_c01_c02=67,new_c03=22),
        development_runs=dict(unpaced=42,paced=14,successes=56,failures=0,timeouts=0,same_as_c01=56),
        additional_endpoint_probes=dict(run=21,success=21,failures=0,synthetic_not_human_quality=True),
        complete_trace_files=len(analysis['trace_checks']),unique_final_policy='PASS',partial_display_only='PASS',
        bounded_queue_and_limits='PASS',half_duplex_recovery='PASS',idle_lease_real_16s_check='PASS',
        microphone='NOT_AUTHORIZED_NOT_TESTED',human_end_of_speech_labels=None,actual_audible_latency_ms=None,
        human_quality='PENDING',aarch64='NOT_TESTED',board='NOT_TESTED',power='NOT_TESTED',stability_2h='NOT_TESTED',
        hls_domains='NOT_APPLICABLE',license='REVIEW_PENDING',A_delivery='NOT_SENT',default_voice_replaced=False,source_commit=None,
        historical_probe_incident='TWO_C02_SELFTEST_JSON_FILES_OVERWRITTEN; OLD_HASHES_RETAINED_EXACT_OLD_CONTENT_NOT_RECOVERED'))
    status=read(CROOT/'PROJECT_STATUS.json')
    status.update(stage='C03',stage_status='PC_ENGINEERING_COMPLETE_MICROPHONE_AND_HUMAN_QUALITY_PENDING',
        stage_gate='USER_AUTHORIZED_NO_MICROPHONE_ENGINEERING_SCOPE_DONE; ACTUAL_RECORDING_AND_FINAL_QUALITY_PENDING',
        updated_at='2026-10-02',domains_scope='Windows PC native incremental ASR, paced public replay and half-duplex worker; no actual microphone or board.',
        evidence_scope='89 checks; 42 unpaced and 14 paced public development replays; 21 endpoint/synthetic probes; complete JSONL traces.',
        next_action='C03 actual microphone validation remains outside current authorization. Human ASR/TTS quality and licenses remain pending before C04 final quality/package acceptance.')
    status['domains'].update(pc='PASS_REAL_STREAMING_ASR_TTS_PROTOCOL_ENGINEERING',
        quality='C01_PUBLIC_SLICE_ONLY; C02_HUMAN_LISTENING_PENDING; C03_MICROPHONE_NOT_AUTHORIZED',
        latency='PACED_FILE_REPLAY_CHUNK_ACK_AND_FINISH_TO_FINAL_MEASURED; HUMAN_SPEECH_END_AND_AUDIBLE_NOT_TESTED')
    status['pending_inputs']=['Authorized personal microphone speech and independent speech-end labels (user declined this stage)',
        'C01 independent authorized student recordings/transcripts and C02 human listening still pending',
        'ASR/Matcha/Vocos ONNX distribution license evidence and Baker non-commercial training-data restriction',
        'Independent final test, physical playback, ARM64 and board window remain pending']
    status['C03']=dict(workspace='voice_C',execution_kind='PC_REAL',streaming_asr=True,real_asr=True,real_tts_available=True,
        opt_in_argument='--stream-config configs/stream.selected.json',chunk_ms=200,sample_rate=16000,encoding='RAW_PCM_S16LE',
        selected_pc_threads=2,endpoint_rule2_seconds=1.2,endpoint_policy='ADVISORY_UNTIL_EXPLICIT_FINISH',
        partial_commit_allowed=False,final_submission='ASR_FINISH_ONLY_ONCE',max_audio_seconds=60,max_chunks=1024,
        native_concurrency=1,queue_limit=2,max_streams_per_process=64,idle_timeout_seconds=15,
        tests_run=89,tests_passed=89,tests_skipped=0,new_checks=22,unpaced_runs=42,paced_runs=14,endpoint_probe_runs=21,
        failures=0,timeouts=0,paced_pcm_chunks=paced['total_pcm_chunks'],unpaced_pcm_chunks=fast['total_pcm_chunks'],
        all_public_final_transcripts_same_as_c01=True,paced_rtf=paced['rtf'],paced_chunk_ack_ms=paced['chunk_ack_ms'],
        paced_finish_to_final_ms=paced['finish_to_final_ms'],paced_peak_rss_bytes=paced['peak_rss_bytes'],
        max_paced_schedule_lag_ms=paced['max_send_lag_ms'],native_endpoint_before_file_end_count=paced['native_endpoint_before_input_end'],
        actual_microphone_test='NOT_TESTED_NOT_AUTHORIZED',user_microphone_answer=scope['user_answer'],
        human_speech_end_latency_ms=None,actual_audible_latency_ms=None,human_quality='PENDING',
        historical_c02_probe_incident='DISCLOSED_TWO_FILES',license='REVIEW_PENDING',A_delivery='NOT_SENT',board='NOT_TESTED')
    for path in ('docs/handoffs/C03.md','voice_C/C03_README.md','voice_C/evidence/c03/verification.json',
                 'voice_C/evidence/c03/benchmark/report.json','voice_C/evidence/c03/edges/report.json',
                 'voice_C/evidence/c03/analysis.json','voice_C/evidence/c03/c02_probe_overwrite_incident.json'):
        if path not in status['evidence']:status['evidence'].append(path)
    write(CROOT/'PROJECT_STATUS.json',status)
    handoff=f'''# C03 本地交接摘要

2026-10-02，北京时间。用户指定“先完成无需麦克风的工程测试，录音暂不授权”。本次授权范围完成，实际麦克风与真人质量仍待办。

实现：显式启用的 SP_VOICE_V1 asr_begin/push/finish、200 ms 原始 PCM、严格 seq/epoch、consumed ACK、仅显示 partial、唯一可提交 final；模型沿用 C01、依赖不升级。
原生端点仅提示，显式 finish 才最终提交；活动流排斥 TTS/整文件 ASR，单任务/两项队列、取消 pending、reset、流资源与 15 秒租约已经验证。

| 电脑工程检查 | 实测 |
|---|---|
| 回归 | 89/89，0 跳过；原有 67 + 新增 22 |
| 加速逐块重放 | 42/42 成功，2889 块，不称实时输入 |
| 按音频原时长重放 | 14/14 成功，963 块，191.2 秒公开开发音频 |
| 最终文字与原 C01 | 56/56 相同，无改善 CER 的声明 |
| 按时长重放 RTF p50/p95/max | {paced['rtf']['p50']:.4f}/{paced['rtf']['p95']:.4f}/{paced['rtf']['max']:.4f} |
| PCM 块 ACK p95/max | {paced['chunk_ack_ms']['p95']:.1f}/{paced['chunk_ack_ms']['max']:.1f} ms |
| finish 到 final p95/max | {paced['finish_to_final_ms']['p95']:.1f}/{paced['finish_to_final_ms']['max']:.1f} ms |
| 按时长重放 worker 峰值 | {paced['peak_rss_bytes']/1048576:.1f} MiB |
| 开发端点/合成短否定探针 | 21/21；没有、不是、停顿续说均保留到 final |
| 真人录音/声卡/板端 | NOT_TESTED，录音未授权 |

finish 到 final 从最后一块已确认后起算，不是独立标注的真人说话结束尾延迟。14 次 paced 只是描述性开发样本；当前最大块 ACK 和进度落后原样保留，尚未做 2 小时稳定性或整机验收。
8/14 个文件在结束前出现原生端点提示；不能单凭文件末尾判断真假端点，故不自动裁剪。0.8/1.2/1.6 秒只做开发比较，保留 1.2 秒提示配置。
短否定由固定 TTS 合成，不能代替真人短否定准确率。partial 不得送入病例、评分或 LLM；主应用仍负责录音、播放和业务提交。

历史异常：首次回归的旧 C02 测试脚本重写两份自测探针 combined_regression.json 与 real_tts_cancel.json。原 hash 保留，原完整内容未恢复，不伪造重建。已修复测试输出路径，后续写 C03；正式 C02 的 138 次测量、WAV、盲听表和全部模型/依赖保持原文件。

入口 [C03_README](../../voice_C/C03_README.md)、[独立客户端](../../voice_C/tools/stream_c03_file.py)；
证据 [verification](../../voice_C/evidence/c03/verification.json)、[commands](../../voice_C/evidence/c03/commands.json)、[重放报告](../../voice_C/evidence/c03/benchmark/report.json)、[端点探针](../../voice_C/evidence/c03/edges/report.json)、[trace 审计](../../voice_C/evidence/c03/analysis.json)；
异常 [覆盖事件](../../voice_C/evidence/c03/c02_probe_overwrite_incident.json)。

没有向 A 发送、没有替换默认语音或启动 C04 发布。C01 真人质量、C02 盲听和权重许可、C03 实际麦克风均须补齐；ARM64、KV260、实际首音、功耗未测。
'''
    (CROOT/'docs/handoffs/C03.md').write_text(handoff,encoding='utf-8')
    live=CROOT/'docs/status/C.md';old=live.read_text(encoding='utf-8');history=old[old.index('以下为2026-10-01旧版'):]
    live.write_text('# 成员C状态\n\n2026-10-02，北京时间。当前 C03，PC_ENGINEERING_COMPLETE_MICROPHONE_AND_HUMAN_QUALITY_PENDING。\n\n已实现显式流式 ASR、严格序号与 epoch、partial 仅显示、唯一 final、ACK 后才能删 PCM、单任务/队列 2、半双工、取消/reset 与 15 秒空闲释放。89 项检查通过；42 次加速逐块与 14 次按音频原时长重放成功，56 次最终文字与 C01 相同；21 次端点/合成短否定探针留档。端点仅提示，不自动截断。\n\n用户本次不授权麦克风录音，实际声卡和板卡未打开。授权学生录音、真人语音结束标注、C02 14 条人工盲听、权重外发许可仍待确认。实际首音、整机、ARM64、板端、2 小时稳定性未测，未向 A 发送或替换默认。\n\n首次 C03 回归曾重写两份 C02 自测探针，原摘要保留，原完整内容未恢复；事件如实记录。已改为可配置新测试输出目录。正式 C02 138 次测量、音频、盲听与 C00/C01/旧 C0/C1 测量保持原内容。入口 docs/handoffs/C03.md、voice_C/C03_README.md、PROJECT_STATUS.json。\n\n'+history,encoding='utf-8')
    allowed={'PROJECT_STATUS.json','AGENTS.md','docs/status/C.md','voice_C/README.md','voice_C/voicec/asr.py',
             'voice_C/voicec/client.py','voice_C/voicec/worker.py','voice_C/tests/test_c02.py'}
    incident=read(OUT/'c02_probe_overwrite_incident.json');probe_paths={r['path']:r for r in incident['affected_files']}
    baseline=read(OUT/'c02_before_changes.json');unchanged=[];changed=[];incidental=[]
    for row in baseline['files']:
        actual=digest(CROOT/row['path'])
        if actual==row['sha256']:unchanged.append(row['path'])
        elif row['path'] in allowed:changed.append(dict(path=row['path'],old_sha256=row['sha256'],new_sha256=actual,reason='C03 extension, safe test output or live status'))
        elif row['path'] in probe_paths:
            if actual!=probe_paths[row['path']]['current_sha256']:raise ValueError('Historical probe changed again after disclosed incident')
            incidental.append(dict(path=row['path'],old_sha256=row['sha256'],new_sha256=actual,reason='UNINTENTIONAL_INITIAL_REGRESSION_OVERWRITE; NOT_EXACTLY_RESTORED'))
        else:raise ValueError('Unexpected historical change: '+row['path'])
    if digest(OUT/'c02_before_changes.json')!=digest(ROOT/'evidence/c02/artifact_manifest.json'):
        raise ValueError('C02 original manifest overwritten')
    legacy=read(CROOT/'bench/e2e/c1/artifact_manifest.json');oldcount=0
    for row in legacy['files']:
        if row['path']=='docs/status/C.md':continue
        if digest(CROOT/row['path'])!=row['sha256']:raise ValueError('Old C1 artifact changed')
        oldcount+=1
    guide=CROOT/'docs/plan_qwen35';guide_hashes=read(guide/'PACKAGE_SHA256.json')
    for name,expected in guide_hashes.items():
        if digest(guide/name)!=expected:raise ValueError('Guidance changed')
    c00=read(ROOT/'evidence/c00/artifact_manifest.json')
    for name in read(ROOT/'evidence/c01/history_integrity.json')['unchanged_paths']:
        original=next(r for r in c00['files'] if r['path']==name)
        if digest(CROOT/name)!=original['sha256']:raise ValueError('Preserved C00 history changed')
    model_counts={}
    for category in ('asr','tts'):
        files=read(ROOT/f'assets/{category}/model.lock.json')['files']
        for row in files:
            if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Model asset changed')
        model_counts[category]=len(files)
    wheels=read(ROOT/'assets/wheels/wheels.lock.json')
    for row in wheels:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Dependency wheel changed')
    write(OUT/'history_integrity.json',dict(status='EXPECTED_SOURCE_UPDATES_WITH_DISCLOSED_TWO_PROBE_OVERWRITES',
        original_c02_manifest_unchanged=True,c02_baseline_files_unchanged=len(unchanged),unchanged_paths=unchanged,
        intentional_changes=changed,incidental_changes=incidental,old_probe_exact_contents_recovered=False,
        formal_c02_performance_audio_and_listening_unchanged=True,c01_measurement_audio_and_assets_unchanged=True,
        c00_preserved_historical_files_verified=27,old_c1_immutable_files_verified=oldcount,
        guidance_declared_hashes_verified=len(guide_hashes),model_files_verified=model_counts,dependency_wheels_verified=len(wheels)))
    excluded={OUT/'artifact_manifest.json',ROOT/'evidence/c03_finalize.log',ROOT/'evidence/c03_seal_check.json'}
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not {'.venv','__pycache__','spool','selftest_latest'}.intersection(p.relative_to(ROOT).parts) and p not in excluded]
    paths += [CROOT/'PROJECT_STATUS.json',CROOT/'AGENTS.md',CROOT/'docs/status/C.md',CROOT/'docs/handoffs/C03.md']
    entries=[dict(path=p.relative_to(CROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(paths)]
    write(OUT/'artifact_manifest.json',dict(stage='C03',scope='LOCAL_AUDIT_NOT_RELEASE; AUTHORIZED_NO_MICROPHONE_ENGINEERING',
        status='ENGINEERING_COMPLETE_MICROPHONE_AND_HUMAN_QUALITY_PENDING',execution_kind='PC_REAL',board='NOT_TESTED',
        historical_probe_incident='DISCLOSED_NOT_RESTORED',excluded=['.venv','__pycache__','spool','selftest_latest','self manifest','evidence/c03_finalize.log','evidence/c03_seal_check.json'],files=entries))
    print('C03 sealed:',len(entries),'files; tests 89; public runs 56; endpoint probes 21; microphone NOT_AUTHORIZED; historical probe overwrites disclosed:',len(incidental))


if __name__=='__main__':main()
