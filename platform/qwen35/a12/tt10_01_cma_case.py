"""Bounded BOARD numerical gate and one ordinary R0/hit pair per backend."""
import json,time
from pathlib import Path
from tt10_01_app import measure
from tt10_01_numeric import same_result
from tt10_01_cma_legacy import compare_legacy_case
from tt10_01_diag_reader import DiagnosticReader,NumericalStreams
from tt10_01_cma_observer import PhaseObserver,ApplicationSendGate


def execute_case(worker,owner,path,*,real,api):
    save=api['save'];sha=api['sha'];receive=api['receive'];validate_bo=api['validate_bo'];BUNDLE=api['BUNDLE'];SPEC=api['SPEC'];ob=api['ob']
    def get():return receive(worker,owner,path)
    ready=get();save(path/'ready.json',ready)
    assert ready['type']=='ready' and ready['prefix_cache']['enabled']
    save(path/'startup-timing.json',dict(process_launch_monotonic_ns=worker.task10_launch_ns,ready_received_monotonic_ns=time.monotonic_ns(),service_ready=False,reason='Prefix precomputation not complete'))
    if real:
        route=ready['bridge']['a12_route'];spans=validate_bo(route)
        assert ready['execution_kind']=='FPGA_REAL' and worker.loads==72 and worker.runs==route['host_verified_completions']==0
        owner.full_resident=True;owner.health();save(path/'actual-residency.json',dict(spans=spans,weight_loads=72))
    else:assert ready['execution_kind']=='CPU_REFERENCE'
    mem={s.split(':')[0]:int(s.split()[1]) for s in Path('/proc/meminfo').read_text().splitlines()}
    assert mem['MemAvailable']>=1114112+192*1024 and mem['CmaFree']>=98304
    save(path/'prefix-memory-admission.json',dict(memory_kib=mem,snapshot_and_scratch_planning_reserve_bytes=192*1024*1024,
        required_remaining_MemAvailable_kib=1114112,actual_peak_not_inferred=True,allowed=True))
    binding=ready['prefix_cache']['binding_sha256'];requests=json.loads((BUNDLE/'control/requests.json').read_text())
    assert len(requests)==SPEC['request_limit']
    corpus=json.loads((BUNDLE/'control/workloads.json').read_text())['real_inputs'];audit=[]
    for item in corpus:
        worker.send(dict(id='audit-'+item['id'],op='tokenize',prompt=item['prompt']));r=get()
        assert r['type']=='tokens' and r['tokens']==item['tokens'];audit.append(dict(id=item['id'],tokens=r['tokens']))
    save(path/'corpus-tokenization.json',audit)
    loaded=sorted({line.split()[-1] for line in (Path('/proc')/str(worker.process.pid)/'maps').read_text().splitlines() if line.split()[-1].startswith('/') and '.so' in line.split()[-1]})
    save(path/'loaded-libraries.json',{p:dict(bytes=Path(p).stat().st_size,sha256=sha(p)) for p in loaded})
    phase=PhaseObserver(owner,worker,path,real=real)
    reader=None
    try:
        reader=DiagnosticReader(path,phase.event)
        full=NumericalStreams();joined=NumericalStreams();ledgers={}
        previous=0;results={};last=None
        for frozen in requests:
            request=dict(frozen);case=path/request['id'];case.mkdir()
            assert len(request['tokens'])<=SPEC['prompt_token_limit'] and request['max_tokens']<=SPEC['output_token_limit']
            assert not request.get('diagnostic_dir') and not request.get('a12_consumer_trace')
            if request.pop('tt10_diagnostic',False):request.update(diagnostic_dir=str(case/'diag'),diagnostic_all_layers=True,dump_state=True,state_fingerprint=True)
            if request['op']=='cache_create' or request['cache_policy']!='R0':request['cache_binding_sha256']=binding
            save(case/'request.json',request);ob.ENABLED=bool(request['profile']);ob.start_request(request)
            if 'application' not in request:phase.before_request(request)
            begin=time.monotonic_ns();events=[];clock=None
            if 'application' in request:
                r,events,begin,ended,clock=measure(ApplicationSendGate(worker,phase),get,(BUNDLE/'control/chat_template.jinja').read_text(),request)
            else:
                worker.send(request)
                while True:
                    r=get();stamp=time.monotonic_ns();assert r['id']==request['id']
                    if r['type']=='token':events.append(dict(index=r['index'],token=r['token'],received_monotonic_ns=stamp))
                    if r['type'] in ('result','error','cache_created'):break
                ended=time.monotonic_ns()
            save(case/'result.json',r)
            assert r['type']==('cache_created' if request['op']=='cache_create' else 'result') and r['status']=='OK',r
            assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
            if clock:
                save(case/'application-timing.json',clock);assert clock['answer_source']=='MODEL' and clock['eos']
                assert clock['candidate_check']['status']==clock['final_check']['status']=='pass'
            first=events[0]['received_monotonic_ns'] if events else None
            save(case/'client-timing.json',dict(begin_monotonic_ns=begin,end_monotonic_ns=ended,result_wall_ms=(ended-begin)/1e6,
                first_token_wall_ms=None if first is None else (first-begin)/1e6,token_events=events))
            ob.finish_request(r if 'request_profile' in r else dict(id=r['id'],request_profile={}),case/'management-profile.json')
            if request['profile']:save(case/'profile-audit.json',api['audit_profile'](r['request_profile']))
            if request['op']=='cache_create':
                new=len(request['tokens']);decode=0
                assert len(r['prefix_cache']['entries'])==1 and r['prefix_cache']['entries'][0]['tokens']==SPEC['prefix_tokens']
                save(path/'service-ready.json',dict(ready_monotonic_ns=ended,precompute_client_ms=(ended-begin)/1e6,capture_ms=r['capture_ms'],
                    prefix_cache=r['prefix_cache'],cold_service_TTFT_promised=False))
            else:
                new=r['prefix_cache_request']['new_tokens'];decode=r['decode_calls']
                assert new==(len(request['tokens'])-SPEC['prefix_tokens'] if request['cache_policy']!='R0' else len(request['tokens']))
            if real:
                route=r['bridge']['a12_route'];assert validate_bo(route)==spans and route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
                expected=72*((new+7)//8+decode);assert route['host_verified_completions']==worker.runs==previous+expected;previous=worker.runs
                save(case/'actual-work.json',dict(new_prefill_tokens=new,prefill_PL_calls=72*((new+7)//8),decode_PL_calls=72*decode,request_actual_calls=expected,cumulative_actual_calls=previous))
            phase.completed(r)
            if 'diagnostic_dir' in request:
                streams=joined if request['id'] in ('warm_prefix','diag_hit') else full if request['id']=='diag_full_R0' else NumericalStreams()
                ledgers[request['id']]=streams.scan(reader,request['id'],completed=True,quiescent=phase.quiescent())
                save(case/'diagnostic-read-audit.json',ledgers[request['id']])
            results[request['id']]=r;last=r
            if request['id']=='diag_exact':
                old=Path(SPEC['legacy_reference'])/'run-v1'/('s2' if real else 's1')/'diag_exact'
                legacy=compare_legacy_case(old,case,ledgers[request['id']]['files'])
                save(case/'legacy-format-bridge.json',legacy)
                assert legacy['historical_comparison_pass'],legacy
                save(case/'legacy-bit-exact.json',dict(status='PASS_HISTORICAL_FIELDS_AND_ALL_ORIGINAL_RAW_BYTES',files=legacy['raw_file_count'],
                    historical_final_state_sha256=legacy['historical_final_state_sha256'],terminal_sha_equality_claimed=legacy['terminal_sha_equality_claimed']))
            if request['id']=='diag_hit':
                reader.verify();phase.event('NUMERICAL_COMPARE_BEGIN',force=True)
                gate=dict(result=same_result(results['diag_full_R0'],r),all_bytes=full.compare(joined))
                save(case/'prefix-numerical-gate.json',gate);assert gate['result']['equal'] and gate['all_bytes']['equal']
                phase.event('NUMERICAL_COMPARE_COMPLETE',force=True)
            if request['id']=='app_hit':assert same_result(results['app_R0'],r)['equal']
            owner.platform.emit('CASE_FINISHED',case_id=request['id'],real=real,permission_runs=worker.runs,weight_loads=worker.loads)
        reader.verify();phase.event('ALL_REQUESTS_COMPLETE',force=True)
        assert worker.close(timeout=15),'normal exit not proven; retain owner'
        save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
        for name in ('warm_prefix','diag_full_R0','diag_hit'):
            directory=path/name/'diag'
            files=ledgers[name]['files']  # Full original bytes were hashed in the same comparison read.
            save(directory/'FILE_HASHES.json',dict(files=files,full_originals_retained_on_board=True,
                note='Readback omits large projection/intermediate-logit files; full originals retained at this reviewed window path'))
        assert last is not None;return last
    except BaseException as exc:
        try:phase.event('CASE_ADAPTER_FAILED',fatal=True,reason=type(exc).__name__+': '+str(exc))
        except BaseException:pass
        raise
    finally:
        if reader is not None:reader.close()
        phase.close()
