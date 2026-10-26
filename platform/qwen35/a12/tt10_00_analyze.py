"""Independent readback, numerical, safety, timing and restoration audit."""
import base64
import io
import json
from pathlib import Path
import tarfile
from tt10_00_prepare import ROOT,OUT,j,save,sha
from cpu01_numeric import compare_cases
from cpu01_profile import audit_profile
from cpu01b_analyze import accounting


def extract():
    assert j(OUT/'board_01/receipt.json')['exit_code']==1
    assert j(OUT/'board_02/receipt.json')['exit_code']==2
    assert j(OUT/'board_03/receipt.json')['exit_code']==0
    modes=[]
    lines=[]
    for attempt, mode in [('board_02','health'),('board_03','cpu02')]:
        for line in (OUT/attempt/'stdout.txt').open(encoding='utf-8'):
            event=json.loads(line)
            if event['event']=='READBACK' and event['mode']==mode:lines.append(line)
    for line in lines:
        e=json.loads(line)
        if e['event']!='READBACK':continue
        assert e['mode'] in ('health','cpu02') and e['mode'] not in modes
        raw=base64.b64decode(e['base64'],validate=True)
        import hashlib
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        directory=OUT/e['mode'];target=directory/'readback-v1'
        target.mkdir(exist_ok=True)
        archive_path=directory/'readback-v1.tar.gz'
        if archive_path.exists():assert archive_path.read_bytes()==raw
        else:archive_path.write_bytes(raw)
        files={}
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            members=archive.getmembers()
            assert len(members)<2000 and sum(m.size for m in members)<536870912
            assert len({m.name for m in members})==len(members)
            for m in members:
                p=(target/m.name).resolve()
                assert p.is_relative_to(target.resolve()) and not m.issym() and not m.islnk()
                if m.isdir():p.mkdir(parents=True,exist_ok=True);continue
                assert m.isfile();p.parent.mkdir(parents=True,exist_ok=True)
                b=archive.extractfile(m).read();assert len(b)==m.size
                if p.exists():assert p.read_bytes()==b
                else:
                    with p.open('xb') as f:f.write(b)
                files[m.name]=dict(bytes=len(b),sha256=sha(p))
        pin=directory/'READBACK_FILES.json'
        if pin.exists():assert j(pin)==files
        else:save(pin,files)
        modes.append(e['mode'])
    assert modes==['health','cpu02']


def main():
    extract();numbers={};clocks=[];profiles={};life={};cases={};resource={};identities={};evidence_storage={};actual=0
    for mode in ('health','cpu02'):
        bundle=OUT/mode/('bundle-v2' if mode=='cpu02' else 'bundle-v1')
        directory=OUT/mode/'readback-v1';run=directory/'run-v1';template=j(bundle/'manifest.json')
        manifest=j(directory/'manifest.json');assert j(directory/'manager-exit.json')['exit_code']==0
        captured=j(OUT/mode/'READBACK_FILES.json')
        evidence_storage[mode]=dict(readback_compressed_bytes=(OUT/mode/'readback-v1.tar.gz').stat().st_size,
            readback_uncompressed_bytes=sum(row['bytes'] for row in captured.values()),
            diagnostic_bytes=sum(row['bytes'] for name,row in captured.items() if '/diag/' in name),
            jsonl_log_bytes=sum(row['bytes'] for name,row in captured.items() if name.endswith('.jsonl')),
            local_archive_extraction_cap_bytes=536870912,remote_disk_quota_enforced=False,
            bound='Inherited 1800-second/5000-call/request-count limits; extraction cap is not a remote disk quota')
        assert j(directory/'stage-receipt.json')['manifest_sha256']==sha(directory/'manifest.json')
        expected={r['path']:r for r in template['files']};installed={r['path']:r for r in manifest['files']}
        assert expected.keys()==installed.keys()
        assert all(expected[k]==installed[k] for k in expected if k!='control/preflight.json')
        identities[mode]=dict(local_bundle=bundle.relative_to(ROOT).as_posix(),local_manifest_sha256=sha(bundle/'manifest.json'),
            installed_manifest_sha256=sha(directory/'manifest.json'),workers={})
        for name in ('independent-postcheck.json','delayed-postcheck.json'):
            p=j(directory/name)
            assert not p['active_lease_exists'] and not p['module_present'] and not any(p['locks'].values())
            assert p['scans'][-1]['no_users_gate'] and p['gdm_state']=='active' and p['fpga_state']=='operating'
            assert p['overlays']=={'k26-starter-kits_image_1':'applied'}
        numbers[mode+'_S1_S2']=compare_cases(run/'s1/diag_exact',run/'s2/diag_exact')
        if mode=='cpu02':
            for side in ('s1','s2'):numbers['health_cpu02_'+side]=compare_cases(OUT/'health/readback-v1/run-v1'/side/'diag_exact',run/side/'diag_exact')
        if mode=='cpu02':
            initial_scan=j(run/'s2/owner-initial-resource-scan.json')
            assert initial_scan['scan_complete'] and not initial_scan['scan_issues']
            assert initial_scan['boot_id']==initial_scan['boot_id_after']
        reqs=j(bundle/'control/requests.json');total=0
        for side in ('s1','s2'):
            root=run/side;ready=j(root/'ready.json');ex=j(root/'exit.json')
            assert ready['threads']==ready['kernel_threads']==2 and ready['physical_ubatch']==8 and ready['context']==1024
            assert ready['execution_kind']==('CPU_REFERENCE' if side=='s1' else 'FPGA_REAL')
            assert ready['cache_policy']=='R0_CLEAR_ALL_REPLAY' and ex['exit_code']==0
            assert j(root/'identity.json')['binary_sha256']==expected['bin/qwen35-a12']['sha256']
            corpus=j(root/'corpus-tokenization.json');frozen=j(OUT/'WORKLOADS.json')['real_inputs']
            assert len(corpus)==len(frozen)==25 and all(a['id']==b['id'] and a['tokens']==b['tokens'] for a,b in zip(corpus,frozen))
            loaded=j(root/'loaded-libraries.json')
            for path,row in loaded.items():
                key='bin/'+Path(path).name
                if key in expected:assert row['sha256']==expected[key]['sha256']
            identities[mode]['workers'][side]=dict(identity=j(root/'identity.json'),ready=ready,loaded_libraries=loaded)
            previous=0;hwm=[ready['peak_rss_kib']]
            for req in reqs:
                name=req['id'];case=root/name;r=j(case/'result.json');clock=j(case/'client-timing.json')
                assert r['status']=='OK' and r['decode_rc']==0 and r['gpu_layers']==0
                assert r['state_cleared_before_response'] and r['state_position_after_clear']==-1
                assert r['prompt_tokens']==len(req['tokens']) and r['threads']==r['kernel_threads']==2
                hwm.append(r['peak_rss_kib']);cases[mode,side,name]=r
                if req['profile']:
                    audited=audit_profile(r['request_profile'])
                    if mode=='cpu02':
                        manager=j(case/'management-profile.json')
                        assert all(row['outcome']=='RETURNED' for row in manager['rows'])
                        for row in manager['rows']:
                            assert all(row['start_ns']<=a<=b<=row['end_ns'] for _,a,b,_ in row['spans'])
                            if row.get('permit',{}).get('phase')=='submit':
                                assert sum(label=='record.fsync' for label,a,b,cpu in row['spans'])==1
                    profiles[mode+'/'+side+'/'+name]=dict(native=r['request_profile'],node_summary=audited,
                        management=accounting(j(case/'management-profile.json'),r['request_profile']['pl_profile']) if mode=='cpu02' else None,
                        management_availability='DETAILED' if mode=='cpu02' else 'ORIGINAL_AGGREGATE_ONLY')
                else:
                    assert not r['request_profile']['enabled'] and not r['request_profile']['node_profile']['enabled']
                    assert j(case/'management-profile.json')['rows']==[]
                if 'application' in req:
                    a=j(case/'application-timing.json');s=a['stamps']
                    assert s['request_received_ns']<=s['backend_enter_ns']<=s['prompt_ready_ns']<=s['worker_send_ns']<=s['first_token_ns']<=s['worker_result_ns']<=s['checked_ns']
                    assert a['TTFT_app_ms']>=a['TTFT_worker_ms']>=0 and a['cache']['hit'] is False
                    assert a['cache']['new_tokens']==len(req['tokens']) and a['eos'] and a['answer_source']=='MODEL'
                    assert a['candidate_check']['status']==a['final_check']['status']=='pass'
                    assert abs(a['TTFT_worker_ms']-clock['first_token_wall_ms'])<0.00001
                    clocks.append(dict(mode=mode,side=side,id=name,profile=req['profile'],TTFT_app_s=a['TTFT_app_ms']/1000,
                        TTFT_worker_s=a['TTFT_worker_ms']/1000,complete_app_s=a['complete_app_ms']/1000,
                        generation_complete_app_s=(s['worker_result_ns']-s['request_received_ns'])/1e9,
                        validated_complete_app_s=(s['checked_ns']-s['request_received_ns'])/1e9,
                        before_worker_ms=a['prepare_before_worker_ms'],after_worker_ms=a['validated_after_worker_ms'],
                        native_prefill_s=r['prefill_ms']/1000,decode_s=r['decode_ms']/1000,
                        violation_10s=a['deadline_10s_violation'],answer_source=a['answer_source'],cache_hit=False))
                if side=='s2':
                    route=r['bridge']['a12_route'];previous+=72*((len(req['tokens'])+7)//8+r['decode_calls'])
                    assert route['host_verified_completions']==previous and route['weight_load_count']==72
                    assert route['owned_bo_charged_bytes']==140591104 and route['a11_explicit_bo_allocations_host_counter']==148
                    assert route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
                    raw=bytes.fromhex(route['a12_raw_meta_hex']);assert len(raw)==64
                    le=lambda a,n:int.from_bytes(raw[a:a+n],'little')
                    assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==previous
                    assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
            assert ex['host_permission_runs']==previous<=5000
            resource[mode+'/'+side]=dict(peak_worker_RSS_kib=max(hwm),ready_memory=ready['memory'],
                short_complete_state_bytes=(root/'diag_exact/diag/hybrid-state.bin').stat().st_size,
                explicit_BO_bytes=140591104 if side=='s2' else 0,full_system_physical_peak=None,XRT_implicit_bytes=None,
                CPU_graph_workspace_separate_bytes=None,CPU_graph_scope='Included in worker RSS; no allocator-level split in unchanged native binary',
                runtime_libraries_verified=True)
            if side=='s2':
                assert previous==4680 and ex['weight_load_permissions']==72;total=previous;actual+=previous
                residency=j(root/'actual-residency.json')
                assert residency['weight_loads']==72 and len(residency['spans'])==148
                assert sum(n for a,n in residency['spans'])==140591104
                events=[json.loads(l) for l in (root/'worker/events.jsonl').read_text().splitlines()]
                assert not any(e['event']=='PERMISSION_FAULT_RETAIN_OWNER' for e in events)
                counts={};stamps=[]
                for e in events:
                    if e['event']!='PERMISSION':continue
                    assert e['allow'] is True;phase=e['request']['phase'];counts[phase]=counts.get(phase,0)+1
                    obs=e['health_observation'];assert obs['checks_skipped'] is False and obs['kernel']['allowed'] is True
                    assert obs['checked_monotonic_ns']<=e['monotonic_ns']
                    if phase=='submit':stamps.append(obs['checked_monotonic_ns'])
                    if not obs['closing']:
                        h=obs['live_health'];assert h['memory_kib']['MemAvailable']>=1114112 and h['memory_kib']['CmaFree']>=98304
                        assert all(0<t<55000 for t in h['temperatures_mC'])
                assert counts==dict(router_open=1,device_open=1,weight_load=72,submit=4680,router_close=1)
                assert len(set(stamps))==4680 and all(a<b for a,b in zip(stamps,stamps[1:]))
        events=[json.loads(l) for l in (run/'lifecycle.jsonl').read_text().splitlines()]
        assert all(e['allowed'] for e in events if e['event']=='KERNEL_LOG_GATE')
        assert all(e['exit_code']==0 for e in events if e['event']=='COMMAND_END')
        life[mode]=dict(real_PL_calls=total,manager_exit=0,worker_exits=[0,0],independent_postcheck='PASS',delayed_postcheck='PASS')
        if mode=='health':life[mode]['initial_independent_postcheck']='FAILED_UNSPECIFIED_SUBCONDITION_RETAINED_IN_BOARD_01; fresh complete and delayed rechecks passed without recompute or forced cleanup'
        if mode=='cpu02':life[mode]['initial_v1_attempt']='REFUSED_AT_OWNER_CREATION_NO_WORKER_OR_PL_MUTATION; failed readback retained; v2 adds initial scan record with identical gate predicates'
    for side in ('s1','s2'):
        for name in ('short_proxy','app_plain_1','app_plain_2','app_profile'):
            a=cases['health',side,name];b=cases['cpu02',side,name]
            assert all(a[k]==b[k] for k in ('output_tokens','text','eos','last_prompt_logits_fnv64'))
    save(OUT/'NUMERICAL.json',dict(status='PASS_BOARD_BIT_EXACT_AND_APPLICATION_QUALITY',comparisons=numbers))
    save(OUT/'BASELINES_BOARD_IDENTITY.json',dict(status='ACTUAL_CURRENT_LOADED_IDENTITIES_FROZEN',references=identities,
         configuration='2 GGML threads, 2 kernel threads, T8, ctx1024, R0, all MLP projections; parent native unchanged',
         runtime_math_changed=False,system_library_hashes_scope='Captured actual loaded files, not a claim of new SDK build'))
    save(OUT/'ACCOUNTING.json',dict(status='PASS_NATIVE_PROFILE_AND_AVAILABLE_MANAGER_ACCOUNTING',profiles=profiles))
    overhead=[]
    for mode in ('health','cpu02'):
        for side in ('s1','s2'):
            rows=[r for r in clocks if r['mode']==mode and r['side']==side];plain=[r['TTFT_app_s'] for r in rows if not r['profile']]
            profile=next(r['TTFT_app_s'] for r in rows if r['profile'])
            overhead.append(dict(mode=mode,side=side,ordinary_samples=plain,ordinary_mean=sum(plain)/len(plain),
                                 profile_s=profile,profile_minus_ordinary_mean_s=profile-sum(plain)/len(plain)))
    save(OUT/'BOARD_BASELINES.json',dict(status='FROZEN_CURRENT_R0_APPLICATION_MEASUREMENTS',rows=clocks,observer_comparisons=overhead,
         samples_per_mode_backend=dict(ordinary=2,profile=1),statistical_acceptance=False,goal_10s='NOT_MET_R0_BASELINE',cache='NOT_IMPLEMENTED',
         caveats=['Fixed health-then-cpu02 order','Different native observer schemas retained','Not a cache candidate or final 100-request acceptance']))
    save(OUT/'RESOURCE_ACCOUNTING.json',dict(status='BO_AND_WORKER_RSS_MEASURED_FULL_SYSTEM_PEAK_NOT_MEASURED',rows=resource,
         evidence_storage=evidence_storage,
         future_snapshot_reserve=j(OUT/'RESOURCE_ESTIMATE.json')['provisional_TT10_01_reserve']))
    save(OUT/'BOARD_AUDIT.json',dict(status='PASS_TT10_00_BOUNDED_BASELINE_AND_NORMAL_RESTORE',actual_PL_calls=actual,
         lifecycle=life,task00_complete=True,cache_implemented=False,TTFT10_goal='NOT_MET_BASELINE',default_backend_changed=False,
         cross_build='NOT_REQUIRED_UNCHANGED_A53',rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1'))
    print(json.dumps(dict(status='PASS_TT10_00_BOARD_BASELINE',actual_PL_calls=actual,app_measurements=len(clocks))))

if __name__=='__main__':main()
