"""Private PS launch scheduling and exact request-boundary permission counters.

No device access, health caching, background journal writes or permit batching.
The launcher changes only the owned native child's scheduling priority.
"""
import copy
import hashlib
import json
from pathlib import Path

SCHEMA='A12_PERMISSION_SCHEDULING_V1'
METRICS=('calls','owner_check_ms','health_check_ms','durable_permission_record_ms')


def policy(path):
    p=Path(path)
    if not p.exists():return dict(schema=SCHEMA,worker_nice_adjustment=0)
    value=json.loads(p.read_text(encoding='utf-8'))
    if set(value)!={'schema','worker_nice_adjustment'} or value['schema']!=SCHEMA:
        raise ValueError('permission scheduling policy differs')
    adjustment=value['worker_nice_adjustment']
    if type(adjustment) is not int or adjustment not in (0,5,10):
        raise ValueError('worker nice adjustment must be 0, 5 or 10')
    return value


def launch(argv,selection):
    command=list(argv)
    if not command or any(not isinstance(s,str) or not s for s in command):
        raise ValueError('explicit native argv required')
    adjustment=selection.get('worker_nice_adjustment')
    if selection.get('schema')!=SCHEMA or type(adjustment) is not int or adjustment not in (0,5,10):
        raise ValueError('unreviewed worker scheduling selection')
    # Baseline/candidate are copied into different runtime directories. Compare
    # executable content via the native prefix identity; only its path may differ.
    semantic=[Path(command[0]).name,*command[1:]]
    native_hash=hashlib.sha256(json.dumps(semantic,separators=(',',':')).encode()).hexdigest()
    if adjustment:
        command=['/usr/bin/nice','--adjustment='+str(adjustment),'--',*command]
    return command,dict(schema=SCHEMA,worker_nice_adjustment=adjustment,
        native_semantic_argv_sha256=native_hash,scope='OWNED_CHILD_ONLY_INHERITED_BY_ITS_THREADS',
        persistence='ORIGINAL_SYNCHRONOUS_FSYNC_BEFORE_EVERY_PERMISSION_REPLY')


def launch_from_bundle(argv):
    path=Path(argv[0]).parent.parent/'control/permission-runtime.json'
    return launch(argv,policy(path))


def checkpoint(worker):
    values=getattr(worker,'permission_metrics',{})
    return {name:copy.deepcopy(values.get(name,0)) for name in METRICS}


def difference(before,after):
    result={name:after[name]-before[name] for name in METRICS}
    if any(value<0 for value in result.values()):raise ValueError('permission counters moved backwards')
    return dict(result,scope='EXACT_REQUEST_BOUNDARIES_INCLUDES_LAST_PERMISSION_RECORD')


def summarize(response,before,after,*,launch_profile):
    result=response.get('model_result') or {}
    spec=result.get('speculative_decoding') or {}
    if (response.get('answer_source')!='MODEL' or response.get('llm_calls')!=1
            or response.get('cache_provenance') is not None
            or response.get('final_check',{}).get('status')!='pass'
            or result.get('eos') is not True or result.get('teacher_forced') is not False
            or spec.get('answer_cache_used') is not False or spec.get('forced_output') is not False):
        raise ValueError('comparison requires an EOS-complete checked fresh model answer')
    profile=result['request_profile'];pl=profile['pl_profile'];phases=pl['phases']
    backend=result.get('actual_backend')
    delta=difference(before,after)
    calls=sum(int(p.get('calls',0)) for p in phases.values())
    if backend=='FPGA_REAL' and (not profile['enabled'] or not pl['enabled'] or delta['calls']!=calls):
        raise ValueError('permission boundary/native call counts differ')
    if backend not in ('FPGA_REAL','CPU_REFERENCE'):raise ValueError('unexpected actual backend')
    if backend=='CPU_REFERENCE' and delta['calls']!=0:raise ValueError('CPU test must not claim physical permits')
    return dict(request_id=response['request_id'],case_id=response['case_id'],
        case_sha256=response['case_sha256'],prompt_sha256=result['application_timing']['prompt_sha256'],
        answer=response['text'],output_tokens=result['output_tokens'],actual_backend=backend,
        answer_source='MODEL',answer_cache_used=False,model_calls=1,eos=True,
        launch=copy.deepcopy(launch_profile),permission=delta,
        native_request_wall_ms=profile['native_request_wall_ms'],
        session_received_to_validated_ms=response['stage_timing']['received_to_validated_ms'],
        permission_wait_ms=sum(p.get('backend',{}).get('a12_permission_wait_ms',0) for p in phases.values()),
        backend_service_ms=sum(p.get('backend',{}).get('service_ms',0) for p in phases.values()),
        native_pl_calls=calls,prefix=copy.deepcopy(result['prefix_cache_request']),
        physical_T_calls=profile['phases']['prefill']['physical_T_calls'],
        prefix_binding_sha256=result['prefix_cache']['binding_sha256'],
        model_identity=copy.deepcopy(result['prefix_cache']['identity']),
        measurement='SESSION_SUBMIT_TO_VALIDATION_AND_NATIVE_PROFILE_NOT_BROWSER_PAINT',
        hardware_cycles=None)
