"""Inserted into reviewed manager: bounded state/cancel cases, never force-close."""
def run_case(worker,owner,path,*,real):
    ready=receive(worker,owner,path);save(path/'ready.json',ready)
    assert ready['type']=='ready'
    if real:
        route=ready['bridge']['a12_route'];assert ready['execution_kind']=='FPGA_REAL'
        spans=validate_bo(route);assert worker.loads==72 and worker.runs==route['host_verified_completions']==0
        owner.full_resident=True;owner.health();save(path/'actual-residency.json',dict(spans=spans,weight_loads=72))
    else:assert ready['execution_kind']=='CPU_REFERENCE'
    requests=json.loads((BUNDLE/'control/requests.json').read_text());results=[];previous=0;last=None
    assert len(requests)==SPEC['request_limit']
    for frozen in requests:
        case=path/frozen['id'];case.mkdir();request=dict(frozen)
        diagnostic=request.pop('diagnostic',False);cancel=request.pop('cancel_test',False)
        assert len(request.get('tokens',[]))<=SPEC['prompt_token_limit']
        assert request.get('max_tokens',0)<=SPEC['output_token_limit']
        if diagnostic:request.update(diagnostic_dir=str(case/'diag'),dump_state=True)
        if 'prompt' in request:
            worker.send(dict(id=request['id'],op='tokenize',prompt=request['prompt']))
            tokenized=receive(worker,owner,case);save(case/'tokenization.json',tokenized)
            assert tokenized['type']=='tokens' and tokenized['tokens']==request['tokens']
        if cancel and real:
            boundary=worker.runs+72
            def hook(permit):
                if permit['phase']=='submit' and worker.runs==boundary and not worker.delivery_cancelled:
                    worker.record(event='SAFE_CANCEL_BOUNDARY',previous_synchronous_calls=worker.runs,next_job=permit['job'],in_flight_at_boundary=0)
                    worker.cancel('task09 confirmed synchronous boundary before next submit')
            worker.before_permission=hook
        save(case/'request.json',request);worker.send(request)
        while True:
            r=receive(worker,owner,case)
            if cancel and not real and r['type']=='token' and not worker.delivery_cancelled:worker.cancel('task09 PC/ARM CPU after first native token')
            if r['type'] in ('result','error','reset'):break
        save(case/'result.json',r)
        if request['op']=='reset':
            assert r['type']=='reset'
        elif request.get('cache_policy','R0')!='R0':
            assert r['type']=='error' and 'R1/R2' in r['message'] and r['state_cleared']
        elif cancel:
            assert worker.delivery_cancelled and r['type']=='result' and r['status']=='CANCELLED',r
            assert r['partial_output_usable'] is False and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
            worker.record(event='LATE_RESULT_DISCARDED',request_id=r['id'],status=r['status'],delivered=False)
            try:worker.send(dict(id='forbidden_old_worker',op='generate',tokens=[1],max_tokens=1))
            except RuntimeError:save(case/'reuse-refused.json',dict(status='PASS_OLD_CANCELLED_WORKER_REFUSES_NEW_REQUEST'))
            else:raise AssertionError('cancelled worker reused')
            if real:
                assert worker.runs==boundary and r['bridge']['a12_route']['host_verified_completions']==boundary
        else:
            assert r['type']=='result' and r['status']=='OK' and r['gpu_layers']==0,r
            assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
        if r['type']=='result':
            if real:
                route=r['bridge']['a12_route'];assert validate_bo(route)==spans
                assert route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
                assert route['host_verified_completions']==worker.runs and worker.runs>previous
                previous=worker.runs
            last=r
        results.append(dict(id=r['id'],type=r['type'],status=r.get('status')))
        owner.platform.emit('CASE_FINISHED',case_id=r['id'],real=real,permission_runs=worker.runs,weight_loads=worker.loads)
    assert worker.close(timeout=15),'normal exit not proven; retain owner'
    save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
    save(path/'results.json',results)
    if real:owner.full_resident=False
    return last
