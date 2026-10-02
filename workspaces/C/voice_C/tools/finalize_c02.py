"""C02 local audit and live status; preserve C00/C01 raw evidence, not a release."""
import hashlib,json,re
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CROOT=ROOT.parent
OUT=ROOT/'evidence/c02'


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def main():
    if (OUT/'artifact_manifest.json').exists():raise RuntimeError('Existing stage seal must not be overwritten')
    report=read(OUT/'benchmark_final/report.json');selected=report['selected_config'];summary=report['summaries'][selected]
    log=(OUT/'unittest_initial.log').read_text(encoding='utf-8')
    if not re.search(r'Ran 67 tests in .*\n\s*OK\s*$',log):raise ValueError('Expected all 67 checks pass with no skips')
    rows=[json.loads(s) for s in (OUT/'benchmark_final/raw.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(rows)!=138 or any(r['status']!='SUCCESS' for r in rows):raise ValueError('Unexpected benchmark failures; retain and investigate')
    scripts={r['script_id']:r for r in map(json.loads,(ROOT/'data/c02_scripts/manifest.jsonl').read_text(encoding='utf-8').splitlines())}
    for row in rows:
        if row['text_sha256']!=scripts[row['script_id']]['text_sha256']:raise ValueError('Frozen text changed')
        if digest(ROOT/row['audio_path'])!=row['response']['audio_sha256']:raise ValueError('Measured WAV changed')
        if row['response']['sample_rate']!=22050 or row['response']['cache_hit']:raise ValueError('Rate/cache policy violated')
    hellos=read(OUT/'benchmark_final/hello.json')
    for hello in hellos:
        model=hello['response']['models'][0]
        if model['generation_config']['silence_scale']!=1.0 or model['generation_config']['speed']!=1.0:
            raise ValueError('Actual generation settings mismatch')
    forms=[json.loads(s) for s in (ROOT/'listening/c02/blank_forms.jsonl').read_text(encoding='utf-8').splitlines()]
    for form in forms:
        if form['status']!='PENDING' or digest(ROOT/form['audio_path'])!=form['audio_sha256']:
            raise ValueError('Blind packet must retain pending original files')
        for field in ('listener_id','consent_reference','heard_transcript','intelligibility_score','naturalness_score',
                      'negation_error','number_error','omission','polyphone_error','time_error','symptom_or_term_error'):
            if form[field] is not None:raise ValueError('Human judgment fabricated or forms modified')
    commands=[
        dict(command='.venv/Scripts/python.exe tools/prepare_c02_sources.py',exit_code=None,log='evidence/c02_sources_initial.log',
            note='Source metadata and baseline retained; original exit code not saved in this file'),
        dict(command='.venv/Scripts/python.exe tools/acquire_c02_assets.py',exit_code=1,log='evidence/c02/asset_acquisition.log',result='WINERROR_10054_CONNECTION_RESET'),
        dict(command='.venv/Scripts/python.exe tools/acquire_c02_assets.py',exit_code=0,log='evidence/c02/asset_acquisition_retry1.log',result='PASS'),
        dict(command='.venv/Scripts/python.exe tools/prepare_c02_plan.py',exit_code=0,log='evidence/c02/prepare_plan.log',result='FROZEN'),
        dict(command='.venv/Scripts/python.exe tools/smoke_c02.py (initial)',exit_code=1,log='evidence/c02/smoke.log',result='WORKER_TIMEOUT'),
        dict(command='Direct main/thread Tts probes via python -c',exit_code=0,logs=['evidence/c02/direct_probe.log','evidence/c02/thread_probe.log'],result='PILOT_PAUSE_0_2'),
        dict(command='.venv/Scripts/python.exe tools/debug_c02_worker.py',exit_code=0,log='evidence/c02/worker_timeout_probe.log',diagnostic='evidence/c02/worker_timeout_probe/stderr.log'),
        dict(command='.venv/Scripts/python.exe tools/smoke_c02.py (NumPy startup fix)',exit_code=0,log='evidence/c02/smoke_fixed.log',result='PILOT_PAUSE_0_2'),
        dict(command='.venv/Scripts/python.exe tools/benchmark_c02.py (pilot)',exit_code=0,log='evidence/c02/benchmark.log',result='138_PILOT_RUNS_SUPERSEDED_BY_EXPLICIT_PAUSE_SETTINGS'),
        dict(command='.venv/Scripts/python.exe tools/benchmark_c02.py',exit_code=0,log='evidence/c02/benchmark_final.log',result='138_FINAL_ENGINEERING_RUNS_PASS'),
        dict(command='.venv/Scripts/python.exe tools/prepare_c02_listening.py',exit_code=0,log='evidence/c02/prepare_listening.log',result='14_PENDING_FORMS'),
        dict(command='.venv/Scripts/python.exe -m unittest discover -s tests -v',exit_code=0,log='evidence/c02/unittest_initial.log',result='67_PASS_0_SKIP'),
        dict(command='.venv/Scripts/python.exe tools/collect_c02_aux_asr.py',exit_code=0,log='evidence/c02/aux_asr.log',result='14_AUXILIARY_NOT_HUMAN_QUALITY'),
        dict(command='.venv/Scripts/python.exe tools/smoke_c02.py (explicit GenerationConfig)',exit_code=0,log='evidence/c02/smoke_final.log',result='REAL_SYNTHESIS_PASS'),
        dict(command='.venv/Scripts/python.exe tools/analyze_c02.py',exit_code=0,log='evidence/c02/analysis.log',result='PAIRED_COMPARISONS_AND_LEXICON_AUDIT'),
        dict(command='.venv/Scripts/python.exe tools/finalize_c02.py (first audit)',exit_code=1,log='evidence/c02_finalize.log',
            result='AUDIT_SCRIPT_STOPITERATION: C00 HANDOFF NOT LISTED IN C01 MANIFEST; CHECK AGAINST ORIGINAL C00 MANIFEST')]
    write(OUT/'commands.json',dict(working_directory=str(ROOT),python=str(ROOT/'.venv/Scripts/python.exe'),
        journal_scope='RECORDED_TOOL_EXITS_AND_LOGS; NOT_A_RAW_RECONSTRUCTION_OF_EARLIER_TOOL_OUTPUT',commands=commands))
    write(OUT/'verification.json',dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        status='PASS_PC_ENGINEERING_HUMAN_LISTENING_AND_LICENSE_PENDING',execution_kind='PC_REAL',
        tests=dict(run=67,passed=67,skipped=0,inherited_c00_c01=49,new_c02=18),
        repeated_synthesis=dict(run=138,success=138,failures=0,timeouts=0,retained_pilot_runs=138),
        selected_configuration=selected,pc='PASS_REAL_ASR_TTS_ENGINEERING',human_listening=dict(reviewed=0,pending=14),
        quality='HUMAN_REVIEW_PENDING',real_student_audio='NOT_COLLECTED',actual_audible_latency_ms=None,
        board='NOT_TESTED',aarch64='NOT_TESTED',power='NOT_TESTED',stability_2h='NOT_TESTED',
        hls_domains='NOT_APPLICABLE',license='REVIEW_PENDING',default_voice_replaced=False,A_delivery='NOT_SENT',
        source_commit=None,user_scope='先完成工程测试和待填写盲听表'))
    lock=read(ROOT/'assets/tts/model.lock.json')
    write(OUT/'limitations.json',dict(retained_failures=[
        dict(path='asset_acquisition.log',problem='TLS_CONNECTION_RESET',fixed='PUBLIC_FIXED_ASSET_RETRY'),
        dict(path='smoke.log',problem='WORKER_TIMEOUT',diagnostic='worker_timeout_probe/stderr.log',fixed='NUMPY_STARTUP_PRELOAD'),
        dict(path='pilot_limitations.json',problem='IMPLICIT_GENERATION_PAUSE_0_2',fixed='EXPLICIT_GENERATION_CONFIG_1_0'),
        dict(path='sources/vocos_upstream_repo.failed.json',problem='GITHUB_API_403_RATE_LIMIT',status='CODE_LICENSE_METADATA_STILL_UNVERIFIED'),
        dict(path='native_callback_check.json',problem='PYTHON_DOC_CALLBACK_DIRECTION_INCORRECT_FOR_MATCHA',fixed='MEASURED_1_CONTINUE_0_STOP')],
        unresolved_lexicon_unknown_tokens=read(OUT/'comparison_analysis.json')['lexicon_unknown_tokens'],
        auxiliary_asr_mismatches='SEE_AUX_ASR_REPORT; TTS_AND_ASR_ERROR_CAUSES_NOT_SEPARABLE_WITHOUT_LISTENING',
        human_ratings=0,licenses=dict(baker=lock['baker_export_weight_license'],vocos=lock['vocoder_export_weight_license'],
            training_data=lock['training_data_restriction']),
        runtime_network='NO_NETWORK_API_LOCAL_ASSETS; DEFAULT_RESTRICTED_SANDBOX; NOT_PHYSICALLY_DISCONNECTED',
        board='NOT_TESTED',stability_2h='NOT_TESTED',default_voice_comparison='NOT_TESTED',end_to_end_200_rounds='NOT_TESTED'))
    status=read(CROOT/'PROJECT_STATUS.json')
    status.update(stage='C02',stage_status='PC_ENGINEERING_COMPLETE_HUMAN_LISTENING_AND_LICENSE_PENDING',
        stage_gate='USER_REQUESTED_ENGINEERING_SCOPE_DONE; FULL_PRONUNCIATION_QUALITY_AND_LICENSE_PENDING',
        updated_at='2026-10-02',domains_scope='C02 Windows PC real Matcha Baker/Vocos; no human quality, final test, ARM64 or board acceptance.',
        evidence_scope='67 checks, 138 final short-text syntheses, native WAVs, timing/memory, 14 pending human forms; pilot and failures retained.',
        next_action='Human listening and asset license evidence remain pending. C03 streaming/service engineering is a separate next stage.',
        pending_inputs=['Human transcription/intelligibility/naturalness and critical pronunciation judgments for 14 development WAVs',
            'Baker non-commercial training-data restriction and Baker/Vocos ONNX distribution license evidence',
            'Authorized student recordings for C01 independent quality are still absent',
            'Independent final speech test, actual playback latency, ARM64 and board window remain pending'])
    status['domains'].update(pc='PASS_REAL_ASR_TTS_ENGINEERING',quality='C02_HUMAN_LISTENING_PENDING; C01_PUBLIC_SLICE_NOT_ACCEPTED',
        latency='PC_COMPLETE_WAV_READY_AND_RTF_MEASURED; ACTUAL_AUDIBLE_AND_BOARD_NOT_TESTED')
    status['C02']=dict(workspace='voice_C',execution_kind='PC_REAL',real_tts=True,model=lock['acoustic_model'],revision=lock['revision'],
        vocoder='vocos-22khz-univ.onnx',native_sample_rate=22050,output_format='MONO_PCM16_WAV',
        selected_pc_threads=2,max_num_sentences=1,speed=1.0,silence_scale=1.0,waveform_cache=False,
        tests_run=67,tests_passed=67,tests_skipped=0,inherited_checks=49,new_checks=18,
        measured_runs=138,measured_successes=138,measured_failures=0,measured_timeouts=0,pilot_runs_retained=138,
        authored_dev_scripts=14,primary_runs_per_threads=42,secondary_batch_runs=12,
        compute_ms=summary['compute_ms'],rtf=summary['rtf'],client_ready_ms=summary['client_elapsed_ms'],
        single_sentence_client_ready_ms=summary['single_sentence_client_ready_ms'],peak_rss_bytes=summary['peak_rss_bytes'],
        memory_scope='TTS_ONLY_WORKER_PROCESS_LIFETIME_PEAK',internal_callback_is_client_ready=False,
        audible_latency_ms=None,human_listening_reviewed=0,human_listening_pending=14,
        tts_intelligibility=None,tts_naturalness=None,negation_errors=None,number_errors=None,omissions=None,
        auxiliary_asr_items=14,auxiliary_asr_is_quality_acceptance=False,weight_license='REVIEW_PENDING',
        training_data_restriction=lock['training_data_restriction'],user_listening_answer='先完成工程测试和待填写盲听表',
        default_voice_replaced=False,A_delivery='NOT_SENT',aarch64='NOT_TESTED',board='NOT_TESTED')
    for path in ('docs/handoffs/C02.md','voice_C/C02_README.md','voice_C/evidence/c02/verification.json',
                 'voice_C/evidence/c02/commands.json','voice_C/evidence/c02/benchmark_final/report.json','voice_C/listening/c02/待填写盲听表.md'):
        if path not in status['evidence']:status['evidence'].append(path)
    write(CROOT/'PROJECT_STATUS.json',status)
    live=CROOT/'docs/status/C.md';old=live.read_text(encoding='utf-8');history=old[old.index('以下为2026-10-01旧版'):]
    live.write_text('# 成员C状态\n\n2026-10-02，北京时间。当前 C02，指导 docs/plan_qwen35；PC_ENGINEERING_COMPLETE_HUMAN_LISTENING_AND_LICENSE_PENDING。\n\n真实 ASR 与 Matcha Baker+Vocos TTS 已运行。C02 使用原采样率 22050 Hz mono PCM16，语速和显式暂停比例 1.0，无答案音频缓存。67 项检查全部通过，正式合成 138 次成功，无失败/超时；早期 138 次暂停参数试跑与超时/下载失败保留。当前电脑 TTS 2 线程、批次 1：compute p50/p95/max 438.7/722.8/795.9 ms，RTF 0.1277/0.1512/0.1599，单句完整 WAV 客户端 ready p95 516.2 ms，峰值约 252.8 MiB。\n\n14 条匿名音频和空白盲听表已完成，真人听评 0 条；可懂度/自然度/关键项错误为 null。原词典四条 shei2 警告、辅助 ASR 术语不一致需要核对。Baker 训练数据非商业限制及 Baker/Vocos 导出许可待确认，未外发。板端、ARM64、实际首音、整机与 2 小时稳定性未测。\n\nC01 原 126 次测量、CER 24.42% 和 2 线程配置保持历史结果；C00 48 条本人录音仍未采集授权，不能把合成音频当学生质量验收。入口 docs/handoffs/C02.md、voice_C/C02_README.md、PROJECT_STATUS.json；盲听 voice_C/listening/c02。所有旧证据保留，未向 A 发送或替换默认语音。\n\n'+history,encoding='utf-8')
    allowed={'AGENTS.md','PROJECT_STATUS.json','docs/status/C.md','voice_C/README.md',
             'voice_C/voicec/worker.py','voice_C/voicec/client.py','voice_C/voicec/audio.py'}
    baseline=read(OUT/'c01_before_changes.json');unchanged=[];changed=[]
    for row in baseline['files']:
        path=CROOT/row['path'];actual=digest(path)
        if actual==row['sha256']:unchanged.append(row['path'])
        elif row['path'] in allowed:changed.append(dict(path=row['path'],old_sha256=row['sha256'],new_sha256=actual,reason='C02 adapter extension or live status'))
        else:raise ValueError('Unexpected C01 change: '+row['path'])
    if digest(OUT/'c01_before_changes.json')!=digest(ROOT/'evidence/c01/artifact_manifest.json'):
        raise ValueError('Historical C01 manifest overwritten')
    legacy=read(CROOT/'bench/e2e/c1/artifact_manifest.json');oldcount=0
    for row in legacy['files']:
        if row['path']=='docs/status/C.md':continue
        if digest(CROOT/row['path'])!=row['sha256']:raise ValueError('Old C1 artifact changed')
        oldcount+=1
    guide=CROOT/'docs/plan_qwen35';guidechecks=read(guide/'PACKAGE_SHA256.json')
    for name,expected in guidechecks.items():
        if digest(guide/name)!=expected:raise ValueError('Guidance changed')
    c00_baseline=read(ROOT/'evidence/c00/artifact_manifest.json')
    if digest(ROOT/'evidence/c01/c00_before_changes.json')!=digest(ROOT/'evidence/c00/artifact_manifest.json'):
        raise ValueError('Historical C00 manifest overwritten')
    for oldpath in read(ROOT/'evidence/c01/history_integrity.json')['unchanged_paths']:
        original=next(r for r in c00_baseline['files'] if r['path']==oldpath)
        if digest(CROOT/oldpath)!=original['sha256']:raise ValueError('Preserved C00 history changed')
    for category in ('asr','tts'):
        for row in read(ROOT/f'assets/{category}/model.lock.json')['files']:
            if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Model asset changed')
    wheels=read(ROOT/'assets/wheels/wheels.lock.json')
    for row in wheels:
        if digest(ROOT/row['path'])!=row['sha256']:raise ValueError('Dependency wheel changed')
    write(OUT/'history_integrity.json',dict(status='PASS',historical_c01_manifest_unchanged=True,
        c01_prior_files_unchanged=len(unchanged),unchanged_paths=unchanged,explicit_live_or_source_changes=changed,
        c00_preserved_historical_files_verified=27,old_c1_immutable_files_verified=oldcount,
        guidance_declared_hashes_verified=len(guidechecks),asr_assets_and_selected_config_unchanged=True,
        c01_raw_data_and_measurements_unchanged=True,dependency_wheels_verified=len(wheels),
        c00_authorization_and_recording_plan_unchanged=True,qa_answers_not_used=True))
    unsealed={OUT/'artifact_manifest.json',ROOT/'evidence/c02_finalize_retry1.log',ROOT/'evidence/c02_seal_check.json'}
    paths=[p for p in ROOT.rglob('*') if p.is_file() and not {'.venv','__pycache__','spool'}.intersection(p.relative_to(ROOT).parts)
           and p not in unsealed]
    paths += [CROOT/'PROJECT_STATUS.json',CROOT/'AGENTS.md',CROOT/'docs/status/C.md',CROOT/'docs/handoffs/C02.md']
    entries=[dict(path=p.relative_to(CROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(paths)]
    write(OUT/'artifact_manifest.json',dict(stage='C02',scope='LOCAL_AUDIT_NOT_A_RELEASE_PACKAGE',
        status='ENGINEERING_COMPLETE_HUMAN_QUALITY_AND_LICENSE_PENDING',execution_kind='PC_REAL',board='NOT_TESTED',
        excluded=['.venv','__pycache__','spool','self manifest','evidence/c02_finalize_retry1.log','evidence/c02_seal_check.json'],files=entries))
    print('C02 local audit sealed:',len(entries),'files; C01 preserved:',len(unchanged),'old C1:',oldcount,
          'guide:',len(guidechecks),'tests: 67; syntheses: 138; human ratings: 0')


if __name__=='__main__':main()
