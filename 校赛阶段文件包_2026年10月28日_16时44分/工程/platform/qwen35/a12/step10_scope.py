"""Freeze inputs, order, modes and hard budgets before task10 board compute."""
import json
from common import ROOT, sha, save
from step10_common import OUT

def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    short=dict(op='generate',tokens=list(range(1,10)),teacher_tokens=[10,11,12,13],max_tokens=4,
               prefill_chunk=256,logits_mode='final',cache_policy='R0',state_fingerprint=False,a12_consumer_trace=False)
    natural=dict(j(ROOT/'evidence/model_pl_A/20261024-step09-v1/REQUESTS.json')['short'][5])
    # Select by ID, never depend on the order of a previous matrix.
    natural=next(dict(r) for r in j(ROOT/'evidence/model_pl_A/20261024-step09-v1/REQUESTS.json')['short'] if r['id']=='medical_A')
    natural.update(max_tokens=24,teacher_tokens=[],prefill_chunk=256,logits_mode='final',
                   state_fingerprint=False,a12_consumer_trace=False)
    natural.pop('diagnostic',None)
    common=[dict(short,id='short_plain',profile=False),dict(short,id='short_profile',profile=True),
            dict(natural,id='natural_plain',profile=False),dict(natural,id='natural_profile',profile=True)]
    medium=dict(short,id='context128_profile',tokens=([1,2,3,4,5,6,7,8,9]*15)[:128],profile=True)
    long=dict(short,id='context1024_profile',tokens=([1,2,3,4,5,6,7,8,9]*114)[:1022],
              teacher_tokens=[10,11],max_tokens=2,profile=True)
    requests=dict(baseline=common,optimized=common+[medium,long])
    save(OUT/'REQUESTS.json',requests)
    budgets={}
    for variant,runs,seconds in [('baseline',6500,7200),('optimized',17000,14400)]:
        req=requests[variant]
        worst=sum(72*((len(r['tokens'])+7)//8+r['max_tokens']-1) for r in req)
        assert worst<=runs
        budget=dict(schema='A12_STEP10_BOUNDED_V1',physical_domain='BOARD',context=1024,physical_ubatch=8,
            per_request_receive_timeout_seconds=5400,profiles=[dict(scope='all',max_successful_runs=runs,
            weight_load_limit=72,explicit_bo_limit_bytes=140591104,request_limit=len(req),prompt_token_limit=max(len(r['tokens']) for r in req),
            output_token_limit=24,max_session_seconds=seconds)],worst_case_calls=worst)
        budgets[variant]=budget;save(OUT/(variant+'-budget.json'),budget)
    save(OUT/'SCOPE.json',dict(status='FROZEN_BEFORE_BOARD_COMPUTE',task='A12_STEP10',requests_sha256=sha(OUT/'REQUESTS.json'),
        budgets=budgets,order='BASELINE_THEN_OPTIONAL_OPTIMIZED; EACH_WINDOW_CPU_ALL_THEN_PL_ALL',threads=2,kernel_threads=2,
        model='Qwen/Qwen3.5-0.8B',context=1024,physical_ubatch=8,scope='all',algorithm='TILED',R0=True,
        same_source_same_binary=True,GDM='STOPPED_FOR_BOTH_CPU_AND_PL',
        modes=dict(normal='profile=false, final logits, no dumps/consumer trace/state serialization',
                   profile='same graph/fusion/barriers, clocks and bounded aggregates only'),
        conditional_fix='Only if baseline identifies redundant completion report or durable duplicate health journal as material cost; same validated completion, all per-permit gates and durable permission record retained; otherwise preserve initial version',
        load_scope='FRESH_PROCESS_NOT_PROVEN_COLD_FILE_CACHE; NO_GLOBAL_DROP_CACHES',
        statistics='DESCRIPTIVE_SMALL_SAMPLE; NO_P95_OR_SIGNIFICANCE',
        final_speedup='NULL_UNTIL_SAME_BOARD_PAIRED_AUDIT',power=None,device_cycles=None,AXI_bytes=None,
        physical_total_peak=None,voice_pipeline='NOT_INCLUDED',extension2048='NOT_TESTED',
        dangerous_fault_injection='NOT_TESTED',reboot_power_flash=False,major_unresolved_limit_seconds=600))
    print(json.dumps(dict(status='TASK10_SCOPE_FROZEN',budgets={k:v['worst_case_calls'] for k,v in budgets.items()})))
