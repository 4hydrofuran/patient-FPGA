"""Derived full compute manager: current budgets, bounded requests and fast fresh health."""
import ast
from common import ROOT

if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12';s=(p/'review06_manager.py').read_text(encoding='utf-8')
    s=s.replace('from window_capacity_only import Window','from window_closeout_v2 import Window\nfrom step08_health import live_snapshot,compact_kernel_record')
    s=s.replace("WINDOW='a12-capacity-20261024-v1'","SPEC=json.loads((BUNDLE/'control/window-spec.json').read_text())\nWINDOW=SPEC['window_id']")
    s=s.replace("self.log=(run/'lifecycle.jsonl').open('x');self.kernel_gate=MinimalGate()","self.run=run;self.log=(run/'lifecycle.jsonl').open('x');self.kernel_gate=MinimalGate()")
    pos=s.index('    def guard(self,identity=None):')
    s=s[:pos]+'''    def emit(self,event,**data):
        if event=='KERNEL_LOG_GATE':data=compact_kernel_record(self.run,data)
        return super().emit(event,**data)

''' +s[pos:]
    s=s.replace("            if not closing:self.platform.snapshot('a12_health')", "            if not closing:self.platform.emit('LIVE_HEALTH',**live_snapshot(self.boot,full_resident=getattr(self,'full_resident',False)))")
    s=s.replace('def receive(worker,owner,run,timeout=65):','def receive(worker,owner,run,timeout=None):\n    timeout=SPEC[\'receive_seconds\'] if timeout is None else timeout')
    start=s.index('def run_case(');end=s.index('\n\ndef main():',start)
    s=s[:start]+'''def validate_bo(route):
    assert route['owned_bo_charged_bytes']==140591104 and route['weight_load_count']==72
    assert route['a11_explicit_bo_allocations_host_counter']==148 and route['a11_argument_groups']==[3]*6
    spans=list(zip(route['a11_io_bo_addresses'],route['a11_io_bo_charged_sizes']))
    assert len(route['a11_live_weights'])==72
    for w in route['a11_live_weights']:spans.extend(zip(w['addresses'],w['charged_sizes']))
    assert len(spans)==148 and sum(n for a,n in spans)==140591104
    for i,(a,n) in enumerate(spans):
        assert 0<=a and a+n<=2147483648 and n%8192==0
        assert all(a+n<=b or b+m<=a for b,m in spans[:i])
    return spans

def run_case(worker,owner,path,*,real):
    ready=receive(worker,owner,path);save(path/'ready.json',ready)
    assert ready['type']=='ready'
    if real:
        route=ready['bridge']['a12_route'];assert ready['execution_kind']=='FPGA_REAL'
        spans=validate_bo(route);assert worker.loads==72 and worker.runs==route['host_verified_completions']==0
        owner.full_resident=True;owner.health()
        save(path/'actual-residency.json',dict(spans=spans,weight_loads=72))
    else:assert ready['execution_kind']=='CPU_REFERENCE' and ready['bridge']['weight_load_count']==72
    requests=json.loads((BUNDLE/'control/requests.json').read_text());results=[];previous=0
    assert len(requests)==SPEC['request_limit']
    for frozen in requests:
        case=path/frozen['id'];case.mkdir();request=dict(frozen)
        if len(request.get('tokens',[]))>SPEC['prompt_token_limit'] or request['max_tokens']>SPEC['output_token_limit']:
            raise RuntimeError('request outside frozen profile')
        if 'prompt' in request:
            worker.send(dict(id=request['id'],op='tokenize',prompt=request['prompt']))
            tokenized=receive(worker,owner,case);save(case/'tokenization.json',tokenized)
            assert tokenized['type']=='tokens' and tokenized['tokens']==request['tokens']
        if SPEC['variant']=='diagnostic':request['diagnostic_dir']=str(case/'diag')
        save(case/'request.json',request);worker.send(request)
        while True:
            r=receive(worker,owner,case)
            if r['type'] in ('result','error'):break
        save(case/'result.json',r)
        assert r['type']=='result' and r['status']=='OK' and r['gpu_layers']==0,r
        assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
        assert r['prompt_tokens']<=SPEC['prompt_token_limit'] and len(r['output_tokens'])<=SPEC['output_token_limit']
        if real:
            route=r['bridge']['a12_route'];assert route['a12_route_scope']=='all'
            assert validate_bo(route)==spans and route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
            assert route['host_verified_completions']==worker.runs and worker.runs>previous
            if SPEC['variant']=='diagnostic':
                trace=route['a12_trace'];assert len(trace)==216 and len(trace)==worker.runs
                assert {x['layer'] for x in trace}==set(range(24))
                for t in trace:
                    c=t['backend_completion'];assert t['consumer_verified'] and t['execution_kind']=='FPGA_REAL'
                    assert c['output_consumable'] and c['last_status_code']==0 and c['job_id']==t['job_id']
                    assert c['a12_observed_ert_state']==4 and c['kernel_build_id']==0xB3030002 and len(c['a12_raw_meta_hex'])==128
            else:assert route['a12_trace']==[]
            previous=worker.runs
        results.append(dict(id=r['id'],text=r['text'],tokens=r['output_tokens'],eos=r['eos'],prompt_tokens=r['prompt_tokens']))
        owner.platform.emit('CASE_FINISHED',case_id=r['id'],real=real,permission_runs=worker.runs,weight_loads=worker.loads)
    assert worker.close(timeout=10),'normal exit not proven; retain owner'
    save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,
         host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
    save(path/'results.json',results)
    if real:owner.full_resident=False
    return r
''' +s[end:]
    s=s.replace("scope='all',max_runs=1224,max_loads=72,explicit_bo_budget_bytes=140591104", "scope='all',max_runs=SPEC['max_runs'],max_loads=72,explicit_bo_budget_bytes=140591104")
    s=s.replace("operation='ALLOCATE_UPLOAD_ONLY_NO_COMPUTE',allowed_kernel_submissions=0,max_session_seconds=120", "operation='BOUNDED_FULL_MODEL_'+SPEC['variant'],max_session_seconds=SPEC['max_session_seconds']")
    s=s.replace("scope='all',lease_archived=True,capacity_probe='72_WEIGHTS_148_BO_ZERO_COMPUTE'", "scope='all',lease_archived=True,variant=SPEC['variant'],request_count=SPEC['request_limit']")
    s=s.replace("'FULL_CAPACITY_LOAD_ONLY_NORMAL_RESTORE_PENDING_AUDIT' if result['capacity_reserve_pass'] else 'FAIL_ACTUAL_RESIDENCY_EXTRA_RESERVE_RESTORED_NORMALLY'", "'FULL_MODEL_'+SPEC['variant']+'_NORMAL_RESTORE_PENDING_AUDIT'")
    s=s.replace("status='CAPACITY_ONLY_NORMAL_EXIT',scope='all',kernel_submissions=0", "status='FULL_MODEL_WINDOW_NORMAL_EXIT',scope='all',variant=SPEC['variant']")
    s=s.replace('One reviewed full-capacity allocation/upload only window; compute prohibited','One new reviewed full-model compute window')
    s=s.replace("step08='NOT_STARTED'", "step08='IN_PROGRESS_'+SPEC['variant']+'_PENDING_AUDIT'")
    ast.parse(s);(p/'step08_manager.py').write_text(s,encoding='utf-8',newline='\n')
    print('STEP08_MANAGER_SOURCE_READY_EXPLICIT_VARIANT_LIMITS')
