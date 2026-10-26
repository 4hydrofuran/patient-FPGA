"""Independent BOARD combined diagnostic, numerical, permission and lifecycle audit."""
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile
from cpu01_profile import audit_profile
from cpu01_numeric import compare_cases
from cpu01b_analyze import accounting

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01-integrated-v1'


def j(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,x):
    with path.open('x',encoding='utf-8') as stream:json.dump(x,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def extract():
    assert j(OUT/'board_01/receipt.json')['exit_code']==0
    modes=[]
    for line in (OUT/'board_01/stdout.txt').open(encoding='utf-8'):
        event=json.loads(line)
        if event['event']!='READBACK':continue
        assert event['mode'] in ('old','integrated') and event['mode'] not in modes
        raw=base64.b64decode(event['base64'],validate=True)
        assert len(raw)==event['bytes'] and hashlib.sha256(raw).hexdigest()==event['sha256']
        directory=OUT/event['mode'];target=directory/'readback-v1'
        if target.exists():
            assert (directory/'readback-v1.tar.gz').read_bytes()==raw
            for name,row in j(directory/'READBACK_FILES.json').items():
                p=target/name;assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256']
            modes.append(event['mode']);continue
        target.mkdir();(directory/'readback-v1.tar.gz').write_bytes(raw)
        files={}
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as tar:
            members=tar.getmembers()
            assert len(members)<2000 and len({m.name for m in members})==len(members)
            assert sum(m.size for m in members)<536870912
            for member in members:
                p=(target/member.name).resolve()
                assert p.is_relative_to(target.resolve()) and not member.issym() and not member.islnk()
                if member.isdir():p.mkdir(parents=True,exist_ok=True);continue
                assert member.isfile();p.parent.mkdir(parents=True,exist_ok=True)
                data=tar.extractfile(member).read();assert len(data)==member.size
                with p.open('xb') as stream:stream.write(data)
                files[member.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
        save(directory/'READBACK_FILES.json',files);modes.append(event['mode'])
    assert set(modes)=={'old','integrated'}


def main():
    extract()
    numerics={};profiles={};rows=[];lifecycle={};case_index={};actual_calls=0
    for mode in ('old','integrated'):
        folder=OUT/mode/'readback-v1';run=folder/'run-v1';template=j(OUT/mode/'bundle-v1/manifest.json');manifest=j(folder/'manifest.json')
        assert j(folder/'manager-exit.json')['exit_code']==0
        assert j(folder/'stage-receipt.json')['manifest_sha256']==sha(folder/'manifest.json')
        expected={r['path']:r for r in template['files']};actual={r['path']:r for r in manifest['files']}
        assert actual.keys()==expected.keys()
        assert all(actual[k]==expected[k] for k in expected if k!='control/preflight.json')
        for name in ('independent-postcheck.json','delayed-postcheck.json'):
            post=j(folder/name)
            assert not post['active_lease_exists'] and not post['module_present'] and not any(post['locks'].values())
            assert post['scans'][-1]['no_users_gate'] and post['gdm_state']=='active'
            assert post['overlays']=={'k26-starter-kits_image_1':'applied'} and post['fpga_state']=='operating'
        numerics[mode+'_S1_S2']=compare_cases(run/'s1/diag_exact',run/'s2/diag_exact')
        if mode=='integrated':
            for side in ('s1','s2'):numerics['old_new_'+side]=compare_cases(OUT/'old/readback-v1/run-v1'/side/'diag_exact',run/side/'diag_exact')
        specs=j(OUT/mode/'bundle-v1/control/window-spec.json');reqs=j(OUT/mode/'bundle-v1/control/requests.json')
        totals={}
        for side in ('s1','s2'):
            root=run/side
            assert j(root/'identity.json')['binary_sha256']==expected['bin/qwen35-a12']['sha256']
            ready=j(root/'ready.json')
            assert ready['threads']==ready['kernel_threads']==2 and ready['physical_ubatch']==8 and ready['context']==1024
            assert ready['execution_kind']==('CPU_REFERENCE' if side=='s1' else 'FPGA_REAL')
            assert ready['non_mlp_projection_schedule']=='STABLE_PER_TOKEN_SIMD_GEMV'
            assert ready['attention_schedule']=='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING'
            exit=j(root/'exit.json');assert exit['exit_code']==0
            previous=0
            for request in reqs:
                name=request['id'];case=root/name;result=j(case/'result.json');clock=j(case/'client-timing.json');usage=j(case/'worker-usage.json')
                assert result['status']=='OK' and result['decode_rc']==0 and result['gpu_layers']==0
                assert result['state_cleared_before_response'] and result['state_position_after_clear']==-1
                if name!='diag_exact':
                    assert result['state_fingerprint'] is None and result['memory'] is None
                    assert result['logits_mode']=='final' and result['prefill_requested_logits']==1
                native=result['request_profile']
                if request['profile']:
                    audited=audit_profile(native)
                    if mode=='integrated':
                        assert audited['schema']=='A12_CPU_NODE_PROFILE_V2'
                        for phase in ('prefill','decode'):
                            aggs=native['node_profile']['phases'][phase]['aggregates']
                            assert any(a['role']=='output_head' and a['identity_basis']=='pinned_tied_embedding_output_weight_and_shape' for a in aggs)
                    decode_ms=sum(q['llama_decode_wall_ms'] for q in native['phases'].values())
                    outside=native['native_request_wall_ms']-decode_ms-result['reset_ms']-native['sample_ms']
                    assert outside>=0
                    boundaries=clock['result_wall_ms']-native['native_request_wall_ms'];assert boundaries>=0
                    metadata={}
                    if mode=='integrated':
                        for phase in ('prefill','decode'):
                            node=native['node_profile']['phases'][phase]
                            measured=(node['metadata_prepare_ns']+node['metadata_release_ns'])/1e6
                            remainder=native['phases'][phase]['host_graph_prepare_schedule_ms']-measured
                            assert remainder>=0
                            metadata[phase]=dict(prepare_ms=node['metadata_prepare_ns']/1e6,release_ms=node['metadata_release_ns']/1e6,
                                other_host_prepare_schedule_ms=remainder,parent='host_graph_prepare_schedule_ms')
                    raw_management=j(case/'management-profile.json')
                    current_idle=[r for r in raw_management['rows'] if r['kind']=='idle' and clock['begin_monotonic_ns']<=r['start_ns']<=r['end_ns']<=clock['end_monotonic_ns']]
                    excluded_idle=[r for r in raw_management['rows'] if r['kind']=='idle' and r not in current_idle]
                    for r in raw_management['rows']:
                        if r.get('model_phase') in ('prefill','decode'):
                            assert clock['begin_monotonic_ns']<=r['start_ns']<=r['end_ns']<=clock['end_monotonic_ns']
                    profiles[mode+'/'+side+'/'+name]=dict(native=native,management=accounting(raw_management,native['pl_profile']),node_summary=audited,
                        idle_observation=dict(current_rows=len(current_idle),current_wall_ms=sum(r['end_ns']-r['start_ns'] for r in current_idle)/1e6,
                            excluded_previous_backend_rows=len(excluded_idle),semantics='Unchanged raw01B collector keys rows by reused request ID, so PL raw reports also retain prior CPU idle rows; this view filters actual client clock. Native phase submit counts/timings are unaffected; idle is never added to permission phases.'),
                        request_tree=dict(client_wall_ms=clock['result_wall_ms'],native_wall_ms=native['native_request_wall_ms'],
                            client_native_boundary_remainder_ms=boundaries,native_children=dict(measured_llama_decode_ms=decode_ms,reset_ms=result['reset_ms'],
                            sample_ms=native['sample_ms'],other_native_ms=outside),metadata_nested_in_host=metadata,
                            semantics='other_native includes token/phase control, state handling, diagnostics and report construction; client/native remainder includes IPC and final response serialization/boundaries, not pure IPC.'))
                else:assert native['enabled'] is False and native['node_profile']['enabled'] is False
                if side=='s2':
                    route=result['bridge']['a12_route']
                    assert route['execution_kind']=='FPGA_REAL' and route['weight_load_count']==72 and route['owned_bo_charged_bytes']==140591104
                    assert route['a11_explicit_bo_allocations_host_counter']==148
                    expected_calls=72*((len(request['tokens'])+7)//8+result['decode_calls']);previous+=expected_calls
                    assert route['host_verified_completions']==previous
                    assert route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
                    meta=bytes.fromhex(route['a12_raw_meta_hex']);assert len(meta)==64
                    le=lambda a,n:int.from_bytes(meta[a:a+n],'little')
                    assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==previous
                    assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
                before,after=usage['before'],usage['after'];ticks=before['clock_ticks_per_second'];assert ticks==after['clock_ticks_per_second']
                row=dict(mode=mode,side=side,id=name,profile=request['profile'],client_first_token_s=clock['first_token_wall_ms']/1000,client_complete_s=clock['result_wall_ms']/1000,
                    native_prefill_s=result['prefill_ms']/1000,native_decode_s=result['decode_ms']/1000,native_request_s=native['native_request_wall_ms']/1000,
                    worker_process_cpu_s=sum(after[k]-before[k] for k in ('process_user_ticks','process_system_ticks'))/ticks,
                    worker_main_thread_context_switches={k:after[k]-before[k] for k in ('main_thread_voluntary_context_switches','main_thread_involuntary_context_switches')},
                    manager_process_usage=j(case/'management-profile.json')['process_usage_delta'])
                rows.append(row);case_index[mode,side,name]=(result,row)
            assert exit['host_permission_runs']==previous<=specs['max_runs']
            if side=='s1':assert previous==0
            else:
                assert previous==3816 and exit['weight_load_permissions']==72;actual_calls+=previous
                events=[json.loads(s) for s in (root/'worker/events.jsonl').read_text().splitlines()]
                assert not any(e['event']=='PERMISSION_FAULT_RETAIN_OWNER' for e in events)
                stamps=[]
                for event in events:
                    if event['event']!='PERMISSION':continue
                    assert event['allow'] is True
                    phase=event['request']['phase'];totals[phase]=totals.get(phase,0)+1
                    obs=event['health_observation'];assert obs['checks_skipped'] is False and obs['kernel']['allowed'] is True
                    assert obs['checked_monotonic_ns']<=event['monotonic_ns']
                    if phase=='submit':stamps.append(obs['checked_monotonic_ns'])
                    if not obs['closing']:
                        health=obs['live_health'];assert health['memory_kib']['MemAvailable']>=1114112 and health['memory_kib']['CmaFree']>=98304
                        assert all(0<t<55000 for t in health['temperatures_mC'])
                assert totals==dict(router_open=1,device_open=1,weight_load=72,submit=3816,router_close=1)
                assert len(set(stamps))==3816 and all(a<b for a,b in zip(stamps,stamps[1:]))
        life=[json.loads(s) for s in (run/'lifecycle.jsonl').read_text().splitlines()]
        assert all(e['allowed'] for e in life if e['event']=='KERNEL_LOG_GATE')
        assert all(e['exit_code']==0 for e in life if e['event']=='COMMAND_END')
        lifecycle[mode]=dict(manager_exit_code=0,worker_exit_codes=[0,0],permission_counts=totals,independent_postcheck='PASS',delayed_postcheck='PASS')
    for side in ('s1','s2'):
        for name in ('short_plain','short_profile','natural_plain','natural_profile'):
            old=case_index['old',side,name][0];new=case_index['integrated',side,name][0]
            for key in ('output_tokens','text','eos','last_prompt_logits_fnv64'):assert old[key]==new[key]
    overhead=[]
    for mode in ('old','integrated'):
        for side in ('s1','s2'):
            for prefix in ('short','natural'):
                plain,prof=(case_index[mode,side,prefix+'_'+p] for p in ('plain','profile'))
                assert all(plain[0][k]==prof[0][k] for k in ('output_tokens','text','eos','last_prompt_logits_fnv64'))
                overhead.append(dict(mode=mode,side=side,input=prefix,plain_complete_s=plain[1]['client_complete_s'],profile_complete_s=prof[1]['client_complete_s'],profile_over_plain_fraction=prof[1]['client_complete_s']/plain[1]['client_complete_s']-1,
                    plain_ttft_s=plain[1]['client_first_token_s'],profile_ttft_s=prof[1]['client_first_token_s']))
    selected=profiles['integrated/s2/natural_profile'];hotspots={}
    for phase in ('prefill','decode'):
        node=selected['native']['node_profile']['phases'][phase];q=selected['native']['phases'][phase]
        hotspots[phase]=dict(exclusive_categories=sorted([dict(category=k,**v) for k,v in node['categories'].items()],key=lambda a:a['wall_us'],reverse=True),
            alternate_role_shape_view=sorted(node['aggregates'],key=lambda a:a['wall_us'],reverse=True),metadata_prepare_s=node['metadata_prepare_ns']/1e9,
            metadata_release_s=node['metadata_release_ns']/1e9,parent_native=q,management=selected['management'][phase],
            graph_planning_barrier_timer_remainder_ms=selected['node_summary']['phases'][phase]['graph_planning_barrier_timer_remainder_ms'])
    save(OUT/'NUMERICAL.json',dict(status='PASS_BOARD_SAME_ISA_BIT_EXACT',comparisons=numerics))
    save(OUT/'ACCOUNTING.json',dict(status='PASS_BOARD_V1_V2_AND_01B_COMBINED_ACCOUNTING',profiles=profiles,semantics='Exclusive head-op categories; aggregate role/shape view is the same time, never additive. MLP callback and node scopes are alternative views. Manager spans nested below native permission wait. Fused children have no separate measured time.'))
    save(OUT/'HOTSPOTS.json',dict(status='MEASURED_BOARD_COMBINED',selected='integrated/s2/natural_profile',phases=hotspots,recommended_next='02 durable manager record/fsync and repeated health JSON; 05 linear-attention matrix work is the largest non-MLP CPU category. Integrate 03 only after its independent return and measured benefit; movement category is a measured upper context, not a claimed recoverable saving. No additional sampling needed for 01.'))
    save(OUT/'OBSERVER_OVERHEAD.json',dict(status='MEASURED_SINGLE_SAMPLES_NOT_STATISTICAL_ACCEPTANCE',rows=overhead,all_measurements=rows,
        limitations='Single samples, fixed old-then-new windows; warm cache not proven cold; manager observer enabled in both; profile-on is diagnostic only. No low-perturbation or speedup claim.',device_cycles=None,power=None))
    save(OUT/'BOARD_AUDIT.json',dict(status='PASS_BOARD_CPU01_COMPATIBLE_AND_UPDATED',physical_domain='BOARD',task01_complete=True,actual_PL_calls=actual_calls,lifecycle=lifecycle,numerical='BIT_EXACT',default_backend_changed=False,task03_changed=False,board_candidate='/var/lib/kv260-a12/cpu01-integrated-20261024-v1',rollback='/var/lib/kv260-a12/health-opt-20261024-v1'))
    print(json.dumps(dict(status='PASS_BOARD_CPU01_COMPATIBLE_AND_UPDATED',actual_PL_calls=actual_calls)))


if __name__=='__main__':main()
