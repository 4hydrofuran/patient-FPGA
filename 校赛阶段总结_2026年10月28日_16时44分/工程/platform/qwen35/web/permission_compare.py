"""Compare only matched fresh-model probes; never infer BOARD speed from PC."""
import argparse
import json
from pathlib import Path
import statistics


def compare(baseline,candidate):
    a,b=baseline['rows'],candidate['rows']
    if not a or len(a)!=len(b):raise ValueError('paired sample count differs')
    pairs=[]
    keys=('case_id','case_sha256','question','repeat','prompt_sha256','answer','output_tokens',
          'actual_backend','physical_T_calls','native_pl_calls','prefix_binding_sha256','model_identity')
    for x,y in zip(a,b):
        if any(x[k]!=y[k] for k in keys):raise ValueError('unmatched prompt/output/backend/call shape')
        if (x['answer_source']!='MODEL' or y['answer_source']!='MODEL'
                or x['answer_cache_used'] or y['answer_cache_used'] or not x['eos'] or not y['eos']):
            raise ValueError('cache/template/incomplete answer is not a fresh inference comparison')
        if x['launch']['worker_nice_adjustment']!=0 or y['launch']['worker_nice_adjustment']!=10:
            raise ValueError('comparison requires original versus nice10')
        if x['launch']['native_semantic_argv_sha256']!=y['launch']['native_semantic_argv_sha256']:
            raise ValueError('native arguments changed')
        for name in ('hit','reused_tokens','new_tokens','speculative_extra_tokens','policy'):
            if x['prefix'].get(name)!=y['prefix'].get(name):raise ValueError('prefix execution differs')
        pairs.append(dict(question=x['question'],repeat=x['repeat'],
            baseline_native_ms=x['native_request_wall_ms'],candidate_native_ms=y['native_request_wall_ms'],
            baseline_permission_ms=x['permission_wait_ms'],candidate_permission_ms=y['permission_wait_ms'],
            baseline_record_ms=x['permission']['durable_permission_record_ms'],
            candidate_record_ms=y['permission']['durable_permission_record_ms']))
    metrics={}
    for name,key in (('native','native_request_wall_ms'),('permission_wait','permission_wait_ms')):
        before=statistics.median(x[key] for x in a);after=statistics.median(x[key] for x in b)
        metrics[name]=dict(baseline_median_ms=before,candidate_median_ms=after,
            reduction_ms=before-after,reduction_percent=None if before<=0 else 100*(before-after)/before)
    actual=a[0]['actual_backend'];board=actual=='FPGA_REAL'
    return dict(status='PAIRED_FRESH_MODEL_COMPARISON',actual_backend=actual,samples_per_variant=len(a),
        BOARD='MEASURED' if board else 'NOT_TESTED',board_latency_ms=metrics['native'] if board else None,
        metrics=metrics,pairs=pairs,cache_used=False,
        scope='MATCHED_HOST_MEASUREMENTS; NO_DEVICE_CYCLES; NO_P95_CLAIM')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=compare(json.loads(args.baseline.read_text(encoding='utf-8-sig')),json.loads(args.candidate.read_text(encoding='utf-8-sig')))
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='pairs'},ensure_ascii=False,indent=2))
