"""Bounded normal/profile measurements; client clocks include ordinary IPC and completion."""
def run_case(worker,owner,path,*,real):
    process_start=time.monotonic_ns()
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
        assert len(request['tokens'])<=SPEC['prompt_token_limit'] and request['max_tokens']<=SPEC['output_token_limit']
        assert not request.get('diagnostic_dir') and not request.get('a12_consumer_trace') and not request.get('state_fingerprint')
        if 'prompt' in request:
            worker.send(dict(id=request['id'],op='tokenize',prompt=request['prompt']))
            tokenized=receive(worker,owner,case);save(case/'tokenization.json',tokenized)
            assert tokenized['type']=='tokens' and tokenized['tokens']==request['tokens']
        save(case/'request.json',request)
        before=dict(getattr(worker,'permission_metrics',{}));begin=time.monotonic_ns();worker.send(request);events=[]
        while True:
            r=receive(worker,owner,case)
            stamp=time.monotonic_ns()
            if r['type']=='token':events.append(dict(index=r['index'],token=r['token'],received_monotonic_ns=stamp))
            if r['type'] in ('result','error'):break
        ended=time.monotonic_ns();save(case/'result.json',r)
        assert r['type']=='result' and r['status']=='OK' and r['gpu_layers']==0,r
        assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
        if request['profile']:
            assert r['request_profile']['accounting_valid']
            assert r['request_profile']['node_profile']['enabled']
        first=events[0]['received_monotonic_ns'] if events else None
        after=dict(getattr(worker,'permission_metrics',{}))
        timing=dict(schema='A12_STEP10_CLIENT_TIMING_V1',begin_monotonic_ns=begin,end_monotonic_ns=ended,
            result_wall_ms=(ended-begin)/1e6,first_token_wall_ms=(first-begin)/1e6 if first else None,
            token_events=events,output_tokens=len(r['output_tokens']),complete_EOS=r['eos'],
            permission_metrics_delta={k:after.get(k,0)-before.get(k,0) for k in after},
            after_first_token_ms=(ended-first)/1e6 if first else None)
        save(case/'client-timing.json',timing)
        if real:
            route=r['bridge']['a12_route'];assert validate_bo(route)==spans
            assert route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
            expected=72*((len(request['tokens'])+7)//8+r['decode_calls'])
            assert route['host_verified_completions']==worker.runs==previous+expected
            previous=worker.runs
        results.append(dict(id=r['id'],status=r['status'],text=r['text'],tokens=r['output_tokens'],eos=r['eos']))
        last=r
        owner.platform.emit('CASE_FINISHED',case_id=r['id'],real=real,permission_runs=worker.runs,weight_loads=worker.loads)
    assert worker.close(timeout=15),'normal exit not proven; retain owner'
    save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
    save(path/'results.json',results)
    if real:owner.full_resident=False
    return last
