"""Derive reviewable C01 reports/state; audit historical bytes without rewriting them."""
import difflib
import hashlib
import json
import re
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
CROOT=ROOT.parent
EVIDENCE=ROOT/'evidence/c01'


def read(path): return json.loads(path.read_text(encoding='utf-8'))
def write(path,data): path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    report=read(EVIDENCE/'thread_comparison/report.json')
    chosen=report['selected_pc_threads'];summary=report['summaries'][str(chosen)]
    commands=read(EVIDENCE/'first/commands.json')
    if any(r['exit_code'] for r in commands): raise ValueError('Stage commands failed')
    log=(EVIDENCE/'first/unittest.log').read_text(encoding='utf-8')
    if 'Ran 49 tests' not in log or not log.rstrip().endswith('OK'): raise ValueError('Expected actual 49-check result')
    rows=[json.loads(s) for s in (EVIDENCE/'thread_comparison/raw.jsonl').read_text(encoding='utf-8').splitlines()]
    first=[r for r in rows if r['threads']==chosen and r['repeat']==0]
    explanations={'1978':'一九七八','20':'二十','70':'七十','1979':'一九七九','116':'一百一十六','36':'三十六','12':'十二'}
    annotations=[];details=[]
    for row in first:
        reference=row['reference_text'];hyp=row['response']['text']
        for match in re.finditer(r'[0-9]+',reference):
            number=match.group();spelling=explanations.get(number)
            annotations.append(dict(recording_id=row['recording_id'],reference_numeral=number,
                chinese_representation_observation=spelling,
                spelling_present_in_actual_hypothesis=spelling in hyp if spelling else None,
                reference_occurrences=reference.count(number),
                observed_chinese_spelling_occurrences=hyp.count(spelling) if spelling else None,
                status='ENGINEERING_TEXT_OBSERVATION_NOT_AUDIO_HUMAN_VERIFICATION',
                effect_on_primary_cer='NONE'))
        differences=[dict(op=op,reference=reference[a:b],hypothesis=hyp[c:d])
            for op,a,b,c,d in difflib.SequenceMatcher(None,reference,hyp,autojunk=False).get_opcodes() if op!='equal']
        details.append(dict(recording_id=row['recording_id'],reference_text=reference,hypothesis=hyp,
            cer=row['cer'],key_items=row['key_items'],display_differences=differences,
            difference_alignment='DISPLAY_ONLY_NOT_CER_ALIGNMENT',
            warnings=row['response']['warnings'],human_review_status='PENDING'))
    write(EVIDENCE/'error_analysis.json',dict(execution_kind='PC_REAL',input_kind=report['input_kind'],
        student_quality='NOT_TESTED',student_cer=None,observed_public_slice_cer=summary['observed_public_slice_cer'],
        reference_chars=summary['reference_chars'],errors=summary['errors'],
        distinct_audio=len(first),distinct_texts=len({r['reference_text'] for r in first}),
        key_items=summary['key_items'],numeric_annotations=annotations,details=details,
        observations=['Eight literal numeral count failures include Arabic/Chinese representation differences; primary CER unchanged',
            'English parenthetical names and acronyms remain in reference; no spoken-only reference editing',
            'Same generic term count can remain while a full medical entity is wrong or missing',
            'Negation literal count is not a semantic or false-positive-negation audit',
            'Uncalibrated confidence is null; human listening/transcripts/clinical review remain pending']))
    write(EVIDENCE/'failures_and_limits.json',dict(retained_attempts=[
        dict(attempt='Initial sandbox network probe',exit_code=1,status='NETWORK_DENIED_WINERROR_10013',
             evidence='Original tool output; this entry is a factual summary, not a reconstructed raw log'),
        dict(attempt='GitHub release metadata',status='HTTP_403_RATE_LIMIT',evidence='sources/github_release.failed.json'),
        dict(attempt='System.Speech script',exit_code=1,status='EXECUTION_POLICY_BLOCKED',evidence='synthetic_generation.log'),
        dict(attempt='System.Speech process-only retry',exit_code=1,status='VOICE_SELECTION_NULL_REFERENCE',evidence='synthetic_generation_retry.log'),
        dict(attempt='System.Speech local access',exit_code=1,status='VOICE_UNAVAILABLE',evidence='synthetic_generation_local_access.log'),
        dict(attempt='SAPI sandbox',exit_code=1,status='HRESULT_0X80045040',evidence='synthetic_generation_sapi.log',failed_file='failed_sapi_first_input.wav'),
        dict(attempt='SAPI local access',exit_code=1,status='CLASS_NOT_REGISTERED',evidence='synthetic_generation_sapi_local_access.log'),
        dict(attempt='Guessed individual public audio URL',exit_code=1,status='HTTP_404',evidence='public_audio_acquisition.log'),
        dict(attempt='Original 24 kHz through strict ASR validation',exit_code=1,status='BAD_SAMPLE_RATE',evidence='public_audio_archive_acquisition.log'),
        dict(attempt='Normalization in elevated process',exit_code=1,status='NUMPY_API_NOT_VISIBLE_IN_ELEVATED_PROCESS',evidence='public_audio_normalized_acquisition.log'),
        dict(attempt='Default-sandbox offline normalization',exit_code=0,status='PASS',evidence='public_audio_offline_preparation.log')],
        own_student_recordings=0,successfully_generated_windows_speech=0,
        selected_asr_failures=sum(r['status']!='SUCCESS' for r in rows),onnx_license='REVIEW_PENDING',
        diagnostics_scope='Observed failures; elevated dependency visibility cause not claimed fully diagnosed'))
    status=read(CROOT/'PROJECT_STATUS.json')
    status.update(stage='C01',stage_status='PC_ENGINEERING_COMPLETE_QUALITY_AND_LICENSE_PENDING',
        stage_gate='PASS_PC_ENGINEERING; PUBLIC_SLICE_MEASURED; HUMAN_QUALITY_AND_LICENSE_PENDING',
        updated_at='2026-10-02',domains_scope='C01 real ASR in Windows PC; public restored-speech slice only. No student, final quality, ARM64 or board acceptance.',
        evidence_scope='Real pinned ASR, 49 checks, 126 measured decodes, raw public-slice CER/errors/timing/memory; not human semantic acceptance.',
        next_action='Collect authorized independent student development/final recordings and verify transcripts/critical semantics; confirm ONNX export license. C02 TTS is a separate next stage.',
        pending_inputs=['Authorized student audio/transcripts/speaker split remain absent; 48-script plan unchanged',
            'ONNX export license statement unresolved; user has no additional reference',
            'Human semantic review, noise/decimal/question coverage, independent final quality pending',
            'Board access/window and ARM64 remain unknown/not tested; not a blocker to PC engineering'])
    status['domains'].update(pc='PASS_REAL_ASR_ENGINEERING',quality='PUBLIC_RESTORED_DEV_SLICE_MEASURED_NOT_ACCEPTED',
        latency='PC_WHOLE_WAV_COMPUTE_MEASURED; STREAMING_AND_AUDIBLE_NOT_TESTED')
    status['C01']=dict(workspace='voice_C',execution_kind='PC_REAL',real_asr=True,real_tts=False,
        streaming_public_api=False,tests_run=49,tests_passed=49,tests_skipped=0,
        inherited_c00_tests=35,new_tests=14,model_id=read(ROOT/'assets/asr/model.lock.json')['model_id'],
        revision=read(ROOT/'assets/asr/model.lock.json')['revision'],selected_pc_threads=chosen,
        runs_total=len(rows),runs_per_thread=42,run_failures=0,run_timeouts=0,
        public_dev_audio=14,public_dev_unique_texts=12,public_input_type='MODEL_RESTORED_FLEURS_R_24K_TO_16K',
        public_observed_cer=summary['observed_public_slice_cer'],reference_chars=606,cer_errors=148,
        literal_key_items=summary['key_items'],own_student_recordings=0,student_cer=None,
        human_semantic_review='PENDING',compute_ms_p50=summary['compute_ms_p50'],compute_ms_p95=summary['compute_ms_p95'],
        rtf_p50=summary['rtf_p50'],rtf_p95=summary['rtf_p95'],peak_rss_bytes=summary['peak_rss_bytes'],
        memory_scope='WORKER_PROCESS_LIFETIME_PEAK',audible_latency_ms=None,
        onnx_export_license='REVIEW_PENDING',license_answer='暂无补充，先保留待确认',
        default_voice_replaced=False,A_delivery='NOT_SENT',board='NOT_TESTED')
    for path in ['docs/handoffs/C01.md','voice_C/C01_README.md','voice_C/evidence/c01/first/commands.json',
                 'voice_C/evidence/c01/thread_comparison/report.json','voice_C/evidence/c01/error_analysis.json']:
        if path not in status['evidence']: status['evidence'].append(path)
    write(CROOT/'PROJECT_STATUS.json',status)
    live=CROOT/'docs/status/C.md';previous=live.read_text(encoding='utf-8')
    history=previous[previous.index('以下为2026-10-01旧版'):]
    live.write_text('# 成员C状态\n\n2026-10-02（北京时间）。当前阶段 C01，指导 docs/plan_qwen35。真实离线中文 ASR 已在本机运行，PC_ENGINEERING_COMPLETE_QUALITY_AND_LICENSE_PENDING。\n\n49 项检查通过（C00 原 35 + 新 14），14 个公开修复语音音频/12 种文字，1/2/4 线程各 42 次，共 126 次成功，无运行失败/超时，输出一致。唯一开发配置 2 线程；compute p50/p95 592.0/1145.0 ms，RTF 0.0464/0.0588，worker 峰值约 146.4 MiB。字面 CER 24.42%，数字字面计数 8/8 不一致；其它关键项字面计数一致不能证明语义正确。\n\n公开 CC-BY-4.0 FLEURS-R 中文 dev 原始 24 kHz 留档后低通转 16 kHz；不是学生录音/完整数据集/最终测试。自己的 48 条脚本仍未采集授权，学生 CER=null、语义审核待办。ONNX 导出/外发许可 REVIEW_PENDING，用户暂无补充。初始网络/Windows 合成/404/采样率/进程依赖问题与失败文件均保存。\n\nTTS、公开流式、ARM64、BOARD、实际首音、整机/能耗仍未测；没有发送 A 或替换默认语音。助手实际选项未核验。C00 原证据/录音计划与旧 C0/C1 冻结内容保留；新增 ASR 在独立 voice_C 中，不读取病例/评分/Qwen/其他成员工程。\n\n入口 docs/handoffs/C01.md、voice_C/C01_README.md、PROJECT_STATUS.json；命令/退出码 evidence/c01/first/commands.json；原始转录/测量 thread_comparison/raw.jsonl，错误分析和完整性审计分别 error_analysis.json/history_integrity.json。下一步授权录音/人工语义/导出许可，后续 C02 按新指令启动。\n\n'+history,encoding='utf-8')
    agents=CROOT/'AGENTS.md';text=agents.read_text(encoding='utf-8')
    if '当前C01交接' not in text:
        agents.write_text(text+'\n当前C01交接：`docs/handoffs/C01.md`、`voice_C/C01_README.md`。真实 ASR 本机工程检查通过；公开修复语音开发片段的 CER 不是学生/医学/板端验收。自己的录音仍为零，ONNX 外发许可待确认。C00 原证据不可覆盖；当前回归用 unittest，不再运行会重写 C00 manifest 的阶段脚本。\n',encoding='utf-8')
    allowed={'voice_C/README.md','voice_C/voicec/audio.py','voice_C/voicec/client.py',
        'voice_C/voicec/worker.py','voice_C/tools/benchmark_asr.py','PROJECT_STATUS.json','docs/status/C.md','AGENTS.md'}
    old=read(EVIDENCE/'c00_before_changes.json');unchanged=[];changed=[]
    for row in old['files']:
        path=CROOT/row['path'];actual=digest(path)
        if actual==row['sha256']: unchanged.append(row['path'])
        else:
            if row['path'] not in allowed: raise ValueError('Unexpected C00 change: '+row['path'])
            changed.append(dict(path=row['path'],old_sha256=row['sha256'],new_sha256=actual,reason='C01 adapter extension or living status update'))
    if digest(EVIDENCE/'c00_before_changes.json')!=digest(ROOT/'evidence/c00/artifact_manifest.json'):
        raise ValueError('C00 historical manifest was overwritten')
    legacy=read(CROOT/'bench/e2e/c1/artifact_manifest.json');legacy_count=0
    for row in legacy['files']:
        if row['path']=='docs/status/C.md': continue
        if digest(CROOT/row['path'])!=row['sha256']: raise ValueError('Historical C1 file changed')
        legacy_count+=1
    guide=CROOT/'docs/plan_qwen35'
    checks=read(guide/'PACKAGE_SHA256.json')
    for name,expected in checks.items():
        if digest(guide/name)!=expected: raise ValueError('Guidance changed: '+name)
    model=read(ROOT/'assets/asr/model.lock.json')
    for row in model['files']:
        if digest(ROOT/row['path'])!=row['sha256']: raise ValueError('Model asset changed')
    wheels=read(ROOT/'assets/wheels/wheels.lock.json')
    for row in wheels:
        if digest(ROOT/row['path'])!=row['sha256']: raise ValueError('Wheel changed')
    write(EVIDENCE/'history_integrity.json',dict(status='PASS',c00_prior_manifest_unchanged=True,
        c00_existing_files_unchanged=len(unchanged),unchanged_paths=unchanged,explicit_changes=changed,
        old_c1_immutable_files_verified=legacy_count,guidance_declared_hashes_verified=len(checks),
        model_files_verified=len(model['files']),wheel_files_verified=len(wheels),
        c00_original_recording_plan_unchanged=True,historical_scores_not_relabelled=True))
    write(EVIDENCE/'verification.json',dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        status='PASS_PC_ENGINEERING; QUALITY_AND_LICENSE_PENDING',execution_kind='PC_REAL',
        commands=commands,tests=dict(run=49,passed=49,skipped=0),
        repeated_decodes=dict(run=126,success=126,failures=0,timeouts=0),
        pc='PASS',quality='PUBLIC_SLICE_MEASURED_NOT_ACCEPTED',student_quality='NOT_TESTED',
        board='NOT_TESTED',aarch64='NOT_TESTED',power='NOT_TESTED',audible_latency='NOT_TESTED',
        hls_domains='NOT_APPLICABLE',license='REVIEW_PENDING',source_commit=None))
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not {'.venv','__pycache__','spool'}.intersection(p.relative_to(ROOT).parts)
        and p!=EVIDENCE/'artifact_manifest.json']
    paths += [CROOT/'PROJECT_STATUS.json',CROOT/'AGENTS.md',CROOT/'docs/status/C.md',CROOT/'docs/handoffs/C01.md']
    entries=[dict(path=p.relative_to(CROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(paths)]
    write(EVIDENCE/'artifact_manifest.json',dict(stage='C01',scope='LOCAL_AUDIT_NOT_A_RELEASE_PACKAGE',
        execution_kind='PC_REAL',board='NOT_TESTED',license='REVIEW_PENDING',
        excluded=['.venv','__pycache__','spool','this self-referential manifest'],files=entries))
    print('C01 local audit sealed:',len(entries),'files; C00 history preserved; old C1:',legacy_count,'guide:',len(checks))


if __name__=='__main__': main()
