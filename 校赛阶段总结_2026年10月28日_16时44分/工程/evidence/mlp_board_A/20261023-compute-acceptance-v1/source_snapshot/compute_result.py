"""Closed failure is recoverable; unknown completion never enters this protocol."""
import math,re
from mlp_policy import schedule

def need(ok,reason):
    if not ok:raise ValueError(reason)

def validate_result(result,identity,pid):
    for k,v in dict(identity,worker_pid=pid,normal_handles_closed=True).items():
        need(type(result.get(k)) is type(v) and result[k]==v,'result identity differs: '+k)
    status=result.get('status');failed=status=='FAILED_CLOSED_A11_MINIMAL'
    need(failed or status=='NORMAL_CLOSED_A11_MINIMAL','unknown closed status')
    rows=result.get('calls');count=result.get('real_submissions')
    need(type(rows) is list and type(count) is int and count==len(rows) and 0<=count<=23,'call ledger differs')
    weights=len(set(r['weight'] for r in schedule()[:count]))
    need(type(result.get('weight_loads')) is int and result['weight_loads']==weights,'weight ledger differs')
    if failed:
        if count==0:
            need(result.get('failure_kind')=='OPEN_RETURNED_ERROR' and result.get('failed_job')==0 and
                 type(result.get('failure_code')) is int and 1<=result['failure_code']<=9 and
                 result.get('context_disposition')=='NOT_CREATED','open failure differs')
        else:
            need(result.get('failure_kind')=='COMPLETED_NUMERIC_OR_QUANT_MISMATCH' and
                 result.get('failed_job')==count and result.get('failure_code') is None and
                 result.get('context_disposition')=='CLOSED_AFTER_VALIDATED_COMPLETION','failed completion differs')
    else:need(count==23 and weights==5,'incomplete success')
    for i,(plan,row) in enumerate(zip(schedule(),rows)):
        for k,v in plan.items():need(type(row.get(k)) is type(v) and row[k]==v,'schedule differs: '+k)
        for k,v in dict(guards_intact=True,status_code=0,kernel_build_id=0xB3030002,
                        output_consumable=True,completion_validated=True,host_verified_completions=i+1).items():
            need(type(row.get(k)) is type(v) and row[k]==v,'unproven completion: '+k)
        numeric=row.get('numeric_pass');quant=row.get('quant_bytes_match')
        need(type(numeric) is bool and type(quant) is bool,'missing validation flags')
        if failed and i==count-1:need(not numeric or not quant,'failure without rejected data')
        else:need(numeric and quant,'unreported validation failure')
        need(re.fullmatch('[0-9a-f]{64}',row.get('actual_output_sha256','')) is not None,'actual hash missing')
        for k in ('input_quant_ms','service_ms','api_run_ms','report_ms','output_copy_ms'):
            value=row.get(k);need(type(value) in (int,float) and math.isfinite(value) and value>=0,'invalid timing')
        need(row['service_ms']>=row['api_run_ms']+row['input_quant_ms'],'service scope differs')
        for k in ('hardware_cycles','measured_AXI_bytes','pure_kernel_ms'):
            need(k in row and row[k] is None,'unmeasured hardware metric')
    return result
