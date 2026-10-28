"""Re-budget elapsed time from the completed diagnostic, before any dev execution."""
import json
from common import sha,save
from step08_common import OUT

if __name__=='__main__':
    old=json.loads((OUT/'generation-budget.json').read_text())
    audit=json.loads((OUT/'DIAGNOSTIC_AUDIT.json').read_text())
    assert audit['status']=='PASS_BOARD_ALL_24_LAYERS_216_REAL_CONSUMED_OUTPUTS'
    root=OUT/'diagnostic/readback-v1/run-v1'
    timings={}
    for side in ('s1','s2'):
        r=json.loads((root/side/'teacher_T8/result.json').read_text())
        timings[side]={k:r[k] for k in ('prefill_ms','decode_ms','prompt_tokens','output_tokens')}
    new=json.loads(json.dumps(old));new['profiles'][0]['max_session_seconds']=18000
    new['per_request_receive_timeout_seconds']=1200
    new.update(parent_sha256=sha(OUT/'generation-budget.json'),diagnostic_sha256=sha(OUT/'DIAGNOSTIC_AUDIT.json'),
        measured_diagnostic=timings,
        time_only_revision='Before any dev execution: 17 paired prompts up to128 input/24 output, 47736 total permits. Durable per-permit health/ownership logging is significant. Explicit5h total/20min receive cap; expiry still cancels delivery without kill/unload. No workload, math or tolerance changes.')
    save(OUT/'generation-budget-v2.json',new)
    print('GENERATION_TIME_BOUND_REVISED_BEFORE_EXECUTION_WORKLOAD_UNCHANGED')
