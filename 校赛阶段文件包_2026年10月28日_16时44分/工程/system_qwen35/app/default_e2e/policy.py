"""Startup registry, profiles and trace schema; never probe or open hardware."""
import json, time, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
CONTRACT='83bd402b39350710d8689d50f79296e9625e9c75ccb0ecee145f08067c4ee3b6'
THREAD_ENV={x:'1' for x in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}
STAMPS=('input_submitted_ns','speech_end_ns','asr_final_ns','llm_start_ns',
        'llm_first_token_received_ns','sentence_checked_ns','tts_ready_ns',
        'playback_submit_ns','first_effective_sound_ns','playback_complete_ns','end_ns')

class HardwareUnavailable(RuntimeError):pass

def registry(mode='cpu_same_math',linear='A',voice='A'):
    if mode=='fpga_required':
        raise HardwareUnavailable('HARDWARE_UNAVAILABLE: no accepted/deployed KV260 profile; no device opened and no CPU fallback')
    if mode not in ('cpu_same_math','no_hardware'):raise ValueError('Unknown execution mode')
    if linear!='A' or voice!='A':raise RuntimeError('OPTIONAL_MODULE_NOT_ACCEPTED: explicit candidate selection is unavailable; automatic switching disabled')
    result={'mode':mode,'linear':'A','voice':'A','actual_backend':'CPU_REFERENCE',
            'degradation':'OPTIONAL_B_C_NOT_USED_DEFAULT_A','fallback':'disabled',
            'candidate_activation':'MAINTENANCE_WINDOW_ONLY_NOT_IMPLEMENTED', 'modules':{}}
    for kind,name in [('linear','linear_A'),('voice','voice_A')]:
        p=ROOT/'modules'/name/'manifest.json';m=json.loads(p.read_text())
        if m.get('api_version')!=1 or m.get('contract_sha256')!=CONTRACT or m.get('execution_kind')!='CPU_REFERENCE':
            raise RuntimeError('Default module version/contract/kind mismatch: '+name)
        if kind=='voice' and (m.get('protocol')!='SP_VOICE_V1' or m.get('runtime_download') is not False):raise RuntimeError('Unsafe voice manifest')
        result['modules'][kind]={'manifest':p.relative_to(ROOT).as_posix(),'api_version':1,'contract_sha256':CONTRACT}
    return result

def profile(llm=3,tts=2):
    if type(llm) is not int or llm not in (2,3) or type(tts) is not int or tts not in (1,2):raise ValueError('A08 profiles are LLM2/3 and TTS1/2')
    return {'llm_threads':llm,'kernel_threads':llm,'asr_threads':1,'tts_threads':tts,
            'native_thread_env':THREAD_ENV,'turn_queue':0,'active_turns':1,'voice_queue':4,
            'phase_policy':'SERIAL_LISTEN_ASR_GENERATE_VALIDATE_SYNTHESIZE_PLAY',
            'intra_sentence_streaming':False,'endpoint':'PUSH_TO_TALK_OR_FINISHED_WAV',
            'max_turns_per_session':200,'context':1024,'physical_ubatch':8,'prefix_cache':'DISABLED_R0'}

def clock_domain():
    """Missing Linux time namespaces are evidence gaps, not fabricated clocks."""
    try:
        namespace=Path('/proc/self/ns/time').readlink().as_posix();error=None
    except OSError as exc:
        namespace=None;error={'type':type(exc).__name__,'errno':exc.errno}
    return {'implementation':time.get_clock_info('monotonic').implementation,
            'time_namespace':namespace,'namespace_error':error,'pid':os.getpid(),
            'comparison_scope':'SAME_HOST_SAME_TIME_NAMESPACE_REQUIRED' if namespace else 'LOCAL_PROCESS_ONLY_UNVERIFIED_CROSS_PROCESS'}

def new_trace(sid,epoch,rid,mode,cold):
    domain=clock_domain()
    return {'schema':'A08_TRACE_V1','domain':'PC','board':'NOT_TESTED','session_id':sid,
            'epoch':epoch,'request_id':rid,'mode':mode,'status':'RUNNING','answer_source':None,
            'actual_backend':None,'configured_backend':'CPU_REFERENCE','timestamps':dict.fromkeys(STAMPS),
            'clock':'Linux CLOCK_MONOTONIC nanoseconds; native token timestamps are IPC receive boundaries',
            'clock_namespace':domain['time_namespace'],'clock_domain':domain,
            'events':[],'cache':{'policy':'R0_CLEAR_ALL_REPLAY','hit':False,'category':'cold_first_round' if cold else 'miss'},
            'unmeasured':{'first_effective_sound_ns':'NOT_TESTED_NO_ACOUSTIC_LOOPBACK',
                          'speech_end_ns':'file/text input; physical end of live speech not observed'},
            'acoustic_gap_ms':None,'playback_underruns':None}

def mark(trace,phase):trace['events'].append({'phase':phase,'monotonic_ns':time.monotonic_ns()})

def validate_trace(tr):
    """Evidence integrity, not answer accuracy or acoustic validation."""
    ts=tr['timestamps'];observed=[ts[k] for k in STAMPS if ts[k] is not None]
    if any(type(x) is not int or x<=0 for x in observed) or observed!=sorted(observed):raise ValueError('Non-monotonic or fabricated timestamp')
    if ts['first_effective_sound_ns'] is not None:raise ValueError('This build has no acoustic measurement')
    app=tr.get('application',{});model=app.get('model_result') or {}
    if ts['llm_start_ns'] is not None and tr['actual_backend']!='CPU_REFERENCE':raise ValueError('Incorrect actual backend')
    if tr['answer_source']=='MODEL':
        if not ts['llm_start_ns'] or not ts['llm_first_token_received_ns']:raise ValueError('Model answer without actual token evidence')
        if model.get('quantization')!='S1_W4A8_MLP' or model.get('bridge',{}).get('weight_load_count')!=72:raise ValueError('Wrong model or weight lifecycle')
        if model.get('state_position_after_clear')!=-1 or not model.get('state_cleared_before_response'):raise ValueError('Uncleared native state')
        if model.get('id')!=tr['session_id']+':'+tr['request_id']:raise ValueError('Native session/turn correlation mismatch')
    for key in ('asr','tts'):
        r=tr.get(key)
        if r and key=='tts' and not r.get('wav_path','').startswith(tr['session_id']+'/'):raise ValueError('Voice spool session identity mismatch')
    if tr['status']=='COMPLETED':
        if app.get('final_check',{}).get('status')!='pass' or not ts['sentence_checked_ns'] or not ts['tts_ready_ns']:raise ValueError('Unvalidated TTS')
        if not tr.get('playback',{}).get('playback_api_completed') or not ts['playback_complete_ns']:raise ValueError('Missing real playback completion')
    if tr.get('spool_after_bytes')!=0 or tr.get('cleanup_error'):raise ValueError('Spool/quiescence failure')
    return True
