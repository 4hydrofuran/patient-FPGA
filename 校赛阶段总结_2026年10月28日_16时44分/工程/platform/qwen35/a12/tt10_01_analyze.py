"""Independent selective readback, numerical, permission, timing and restore audit."""
import base64
import hashlib
import io
import json
import tarfile
from pathlib import Path
from tt10_01_common import ROOT,OUT,FROZEN,j,save,sha
from tt10_01_numeric import same_result
from cpu01_numeric import compare_cases
from cpu01_profile import audit_profile
from cpu01b_analyze import accounting


def extract():
    receipt=j(OUT/'board_02/receipt.json')
    assert receipt['exit_code']==0 and receipt['payload_sent']
    assert receipt['script_sha256']==sha(OUT/'board_driver_reviewed02.py')
    events=[];found=False;target=OUT/'readback-v1';files={}
    for line in (OUT/'board_02/stdout.txt').open(encoding='utf-8'):
        e=json.loads(line)
        if e['event']!='READBACK':events.append(e);continue
        assert not found and e['mode']=='prefix';found=True
        raw=base64.b64decode(e['base64'],validate=True)
        assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
        archive_path=OUT/'readback-v1.tar.gz'
        if archive_path.exists():assert sha(archive_path)==e['sha256']
        else:archive_path.write_bytes(raw)
        target.mkdir(exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            members=archive.getmembers()
            assert len(members)<5000 and sum(m.size for m in members)<536870912
            assert len({m.name for m in members})==len(members)
            for m in members:
                p=(target/m.name).resolve()
                assert p.is_relative_to(target.resolve()) and not m.issym() and not m.islnk()
                if m.isdir():p.mkdir(parents=True,exist_ok=True);continue
                assert m.isfile();p.parent.mkdir(parents=True,exist_ok=True)
                b=archive.extractfile(m).read();assert len(b)==m.size
                if p.exists():assert sha(p)==hashlib.sha256(b).hexdigest()
                else:
                    with p.open('xb') as stream:stream.write(b)
                files[m.name]=dict(bytes=len(b),sha256=sha(p))
    assert found and events[-1]['event']=='ALL_WINDOWS_NORMAL_EXIT'
    assert not any(e['event'].startswith('STOP_') for e in events)
    if (OUT/'READBACK_FILES.json').exists():assert j(OUT/'READBACK_FILES.json')==files
    else:save(OUT/'READBACK_FILES.json',files)
    save(OUT/'BOARD_TRANSPORT_EVENTS.json',events)
    return target,files


def main():
    directory,files=extract();run=directory/'run-v1';bundle=OUT/'candidate/bundle-v2'
    assert j(directory/'manager-exit.json')['exit_code']==0
    assert j(directory/'stage-receipt.json')['manifest_sha256']==sha(directory/'manifest.json')
    expected={r['path']:r for r in j(bundle/'manifest.json')['files']}
    installed={r['path']:r for r in j(directory/'manifest.json')['files']}
    assert expected.keys()==installed.keys()
    assert all(expected[k]==installed[k] for k in expected if k!='control/preflight.json')
    for name in ('independent-postcheck.json','delayed-postcheck.json'):
        p=j(directory/name)
        assert not p['active_lease_exists'] and not p['module_present'] and not any(p['locks'].values())
        assert p['scans'][-1]['no_users_gate'] and not p['scans'][-1]['scan_issues']
        assert p['gdm_state']=='active' and p['fpga_state']=='operating'
        assert p['overlays']=={'k26-starter-kits_image_1':'applied'}
    initial=j(run/'s2/owner-initial-resource-scan.json')
    assert initial['scan_complete'] and not initial['scan_issues'] and initial['boot_id']==initial['boot_id_after']
    reqs=j(bundle/'control/requests.json');assert len(reqs)==6
    results={};clocks=[];resources={};profiles={};identities={};numbers={};inventories={};total=0
    for side in ('s1','s2'):
        root=run/side;ready=j(root/'ready.json');ex=j(root/'exit.json')
        assert ready['threads']==ready['kernel_threads']==2 and ready['physical_ubatch']==8 and ready['context']==1024
        assert ready['execution_kind']==('CPU_REFERENCE' if side=='s1' else 'FPGA_REAL')
        assert ready['prefix_cache']['enabled'] and ex['exit_code']==0
        assert j(root/'identity.json')['binary_sha256']==expected['bin/qwen35-a12']['sha256']
        corpus=j(root/'corpus-tokenization.json');frozen=j(FROZEN/'WORKLOADS.json')['real_inputs']
        assert len(corpus)==len(frozen)==25
        assert all(a['id']==b['id'] and a['tokens']==b['tokens'] for a,b in zip(corpus,frozen))
        loaded=j(root/'loaded-libraries.json')
        for path,row in loaded.items():
            key='bin/'+Path(path).name
            if key in expected:assert row['sha256']==expected[key]['sha256']
        identities[side]=dict(identity=j(root/'identity.json'),ready=ready,loaded_libraries=loaded)
        admission=j(root/'prefix-memory-admission.json');assert admission['allowed']
        assert admission['memory_kib']['MemAvailable']>=1114112+192*1024 and admission['memory_kib']['CmaFree']>=98304
        previous=0;hwm=[ready['peak_rss_kib']]
        for req in reqs:
            name=req['id'];case=root/name;r=j(case/'result.json');results[side,name]=r
            assert r['status']=='OK' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
            if 'peak_rss_kib' in r:hwm.append(r['peak_rss_kib'])
            if name=='warm_prefix':
                assert r['type']=='cache_created' and r['prefix_tokens']==70;new=70;decode=0
                entry=r['prefix_cache']['entries'];assert len(entry)==1 and entry[0]['position']==69
                assert entry[0]['owner']==dict(kind='public_neutral')
                assert entry[0]['charged_bytes']<=67108864 and entry[0]['logits_bytes']==248320*4
            else:
                assert r['decode_rc']==0 and r['gpu_layers']==0
                assert r['prompt_tokens']==len(req['tokens']) and r['threads']==r['kernel_threads']==2
                c=r['prefix_cache_request'];new=c['new_tokens'];decode=r['decode_calls']
                hit=req['cache_policy']!='R0'
                assert c['hit']==hit and c['reused_tokens']==(70 if hit else 0)
                assert new==len(req['tokens'])-(70 if hit else 0)
            if req['profile']:
                audited=audit_profile(r['request_profile']);manager=j(case/'management-profile.json')
                assert all(row['outcome']=='RETURNED' for row in manager['rows'])
                for row in manager['rows']:
                    assert all(row['start_ns']<=a<=b<=row['end_ns'] for _,a,b,_ in row['spans'])
                    if row.get('permit',{}).get('phase')=='submit':assert sum(label=='record.fsync' for label,a,b,cpu in row['spans'])==1
                profiles[side+'/'+name]=dict(native=r['request_profile'],node_summary=audited,
                    management=accounting(manager,r['request_profile']['pl_profile']))
            else:
                if 'request_profile' in r:assert not r['request_profile']['enabled']
                assert j(case/'management-profile.json')['rows']==[]
            if 'application' in req:
                a=j(case/'application-timing.json');s=a['stamps'];clock=j(case/'client-timing.json')
                ordered=['request_received_ns','backend_enter_ns','prompt_ready_ns','worker_send_ns','first_token_ns','worker_result_ns','checked_ns']
                assert all(s[x]<=s[y] for x,y in zip(ordered,ordered[1:]))
                assert a['TTFT_app_ms']>=a['TTFT_worker_ms']>=0 and a['eos'] and a['answer_source']=='MODEL'
                assert a['candidate_check']['status']==a['final_check']['status']=='pass'
                assert abs(a['TTFT_worker_ms']-clock['first_token_wall_ms'])<0.00001
                c=a['cache'];assert c['hit']==(name=='app_hit') and c['new_tokens']==new
                clocks.append(dict(side=side,id=name,TTFT_app_s=a['TTFT_app_ms']/1000,TTFT_worker_s=a['TTFT_worker_ms']/1000,
                    complete_app_s=a['complete_app_ms']/1000,generation_complete_app_s=(s['worker_result_ns']-s['request_received_ns'])/1e9,
                    validated_complete_app_s=(s['checked_ns']-s['request_received_ns'])/1e9,
                    native_prefill_s=r['prefill_ms']/1000,decode_s=r['decode_ms']/1000,
                    prepare_before_worker_ms=a['prepare_before_worker_ms'],cache=c,violation_10s=a['deadline_10s_violation']))
            if side=='s2':
                work=j(case/'actual-work.json');calls=72*((new+7)//8+decode);previous+=calls
                assert work['request_actual_calls']==calls and work['cumulative_actual_calls']==previous
                route=r['bridge']['a12_route'];assert route['host_verified_completions']==previous and route['weight_load_count']==72
                assert route['owned_bo_charged_bytes']==140591104 and route['a11_explicit_bo_allocations_host_counter']==148
                assert route['a11_live_weights']==ready['bridge']['a12_route']['a11_live_weights']
                raw=bytes.fromhex(route['a12_raw_meta_hex']);assert len(raw)==64
                le=lambda a,n:int.from_bytes(raw[a:a+n],'little')
                assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==previous
                assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
        assert ex['host_permission_runs']==previous<=5000
        old=FROZEN/'cpu02/readback-v1/run-v1'/side/'diag_exact'
        numbers[side+'_legacy_R0']=compare_cases(old,root/'diag_exact')
        numbers[side+'_prefix_result']=same_result(results[side,'diag_full_R0'],results[side,'diag_hit'])
        numbers[side+'_ordinary_result']=same_result(results[side,'app_R0'],results[side,'app_hit'])
        assert numbers[side+'_prefix_result']['equal'] and numbers[side+'_ordinary_result']['equal']
        gate=j(root/'diag_hit/prefix-numerical-gate.json');g=gate['all_bytes']
        assert gate['result']['equal'] and g['equal'] and g['prefill_state_equal']
        assert g['projection_streams']==144 and g['full_logit_vectors']==108
        assert g['reference_projection_sha256']==g['restored_projection_sha256']
        assert g['reference_logits_sha256']==g['restored_logits_sha256']
        assert g['reference_projection_records']==g['actual_projection_records']==1080
        numbers[side+'_full_prefix_gate']=gate
        inventories[side]={}
        for name in ('warm_prefix','diag_full_R0','diag_hit'):
            diag=root/name/'diag';inventory=j(diag/'FILE_HASHES.json')
            assert inventory['full_originals_retained_on_board']
            present={p.name for p in diag.iterdir() if p.is_file() and p.name!='FILE_HASHES.json'}
            assert present<=inventory['files'].keys()
            manifest=j(diag/'manifest.json')
            for row in manifest['projections']:
                for kind,dimension in (('input','K'),('output','N')):
                    assert inventory['files'][row[kind]]['bytes']==row['T']*row[dimension]*4
            for row in manifest['logits']:
                assert inventory['files'][row['file']]['bytes']==248320*4
                if name=='diag_full_R0':assert inventory['files'][row['file']]['sha256']==g['reference_logits_sha256'][str(row['position'])]
                else:assert inventory['files'][row['file']]['sha256']==g['restored_logits_sha256'][str(row['position'])]
            included=0;omitted=0
            for leaf,row in inventory['files'].items():
                p=diag/leaf
                if p.exists():assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'];included+=1
                else:assert leaf.endswith(('.x.bin','.y.bin','.f32'));omitted+=1
            inventories[side][name]=dict(total_original_files=len(inventory['files']),included=included,omitted=omitted,
                total_original_bytes=sum(v['bytes'] for v in inventory['files'].values()))
        assert sha(root/'diag_full_R0/diag/hybrid-state.bin')==sha(root/'diag_hit/diag/hybrid-state.bin')
        for leaf in ('logits-prefill-106.f32','logits-decode-0.f32'):
            assert sha(root/'diag_full_R0/diag'/leaf)==sha(root/'diag_hit/diag'/leaf)
        entry=results[side,'warm_prefix']['prefix_cache']['entries'][0]
        startup=j(root/'startup-timing.json');service=j(root/'service-ready.json')
        assert startup['ready_received_monotonic_ns']<service['ready_monotonic_ns']
        resources[side]=dict(peak_worker_RSS_kib=max(hwm),ready_memory=ready['memory'],memory_admission=admission,snapshot=entry,
            worker_ready_wall_s=(startup['ready_received_monotonic_ns']-startup['process_launch_monotonic_ns'])/1e9,
            service_ready_wall_s=(service['ready_monotonic_ns']-startup['process_launch_monotonic_ns'])/1e9,
            precompute_client_s=service['precompute_client_ms']/1000,capture_ms=service['capture_ms'],
            explicit_BO_bytes=140591104 if side=='s2' else 0,snapshot_scratch_planning_reserve_bytes=192*1024*1024,
            full_system_physical_peak=None,XRT_implicit_bytes=None,CPU_graph_workspace_separate_bytes=None)
        if side=='s2':
            assert ex['weight_load_permissions']==72;total=previous
            residency=j(root/'actual-residency.json');assert residency['weight_loads']==72 and len(residency['spans'])==148
            assert sum(n for a,n in residency['spans'])==140591104
            counts={};stamps=[]
            for line in (root/'worker/events.jsonl').open(encoding='utf-8'):
                e=json.loads(line);assert e['event']!='PERMISSION_FAULT_RETAIN_OWNER'
                if e['event']!='PERMISSION':continue
                assert e['allow'] is True;phase=e['request']['phase'];counts[phase]=counts.get(phase,0)+1
                obs=e['health_observation'];assert obs['checks_skipped'] is False and obs['kernel']['allowed'] is True
                assert obs['checked_monotonic_ns']<=e['monotonic_ns']
                if phase=='submit':stamps.append(obs['checked_monotonic_ns'])
                if not obs['closing']:
                    h=obs['live_health'];assert h['memory_kib']['MemAvailable']>=1114112 and h['memory_kib']['CmaFree']>=98304
                    assert all(0<t<55000 for t in h['temperatures_mC'])
            assert counts==dict(router_open=1,device_open=1,weight_load=72,submit=total,router_close=1)
            assert len(set(stamps))==total and all(a<b for a,b in zip(stamps,stamps[1:]))
    assert identities['s1']['ready']['prefix_cache']['binding_sha256']!=identities['s2']['ready']['prefix_cache']['binding_sha256']
    numbers['S1_S2_legacy']=compare_cases(run/'s1/diag_exact',run/'s2/diag_exact')
    for name in ('warm_prefix','diag_full_R0','diag_hit'):
        assert j(run/'s1'/name/'diag/FILE_HASHES.json')['files']==j(run/'s2'/name/'diag/FILE_HASHES.json')['files']
    assert numbers['s1_full_prefix_gate']==numbers['s2_full_prefix_gate']
    for name in ('diag_full_R0','diag_hit','app_R0','app_hit'):assert same_result(results['s1',name],results['s2',name])['equal']
    for e in map(json.loads,(run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()):
        if e['event']=='KERNEL_LOG_GATE':assert e['allowed']
        if e['event']=='COMMAND_END':assert e['exit_code']==0
    improvement={}
    for side in ('s1','s2'):
        a=next(r for r in clocks if r['side']==side and r['id']=='app_R0')
        b=next(r for r in clocks if r['side']==side and r['id']=='app_hit')
        assert b['TTFT_app_s']<a['TTFT_app_s']
        improvement[side]=dict(TTFT_reduction_fraction=1-b['TTFT_app_s']/a['TTFT_app_s'],
            complete_reduction_fraction=1-b['complete_app_s']/a['complete_app_s'])
    save(OUT/'NUMERICAL_BOARD.json',dict(status='PASS_SAME_ARM_FULL_STATE_LOGITS_PROJECTIONS',comparisons=numbers,
        same_ISA_only=True,remote_originals=j(OUT/'PACKAGE-02.json')['remote']+'/run-v1',selective_readback=True))
    save(OUT/'BOARD_IDENTITIES.json',dict(installed_manifest_sha256=sha(directory/'manifest.json'),workers=identities))
    save(OUT/'ACCOUNTING_BOARD.json',dict(status='PASS_NATIVE_AND_UNCHANGED_MANAGER_PROFILE',profiles=profiles))
    save(OUT/'BOARD_TIMINGS.json',dict(status='MEASURED_SAME_INPUT_R0_AND_EXACT_PREFIX',rows=clocks,improvement=improvement,
        samples_per_backend=dict(R0=1,hit=1),fixed_order='R0_THEN_HIT',statistical_acceptance=False,
        goal_10s='NOT_MET' if any(r['violation_10s'] for r in clocks) else 'NOT_FINAL_ACCEPTANCE',final_100_request_acceptance=False))
    save(OUT/'RESOURCE_ACCOUNTING_BOARD.json',dict(rows=resources,inventories=inventories,
        readback_uncompressed_bytes=sum(v['bytes'] for v in files.values()),readback_compressed_bytes=(OUT/'readback-v1.tar.gz').stat().st_size,
        remote_originals_deleted=False,extraction_cap_bytes=536870912))
    save(OUT/'BOARD_AUDIT.json',dict(status='PASS_TT10_01_PREFIX_EQUIVALENCE_REDUCED_WORK_AND_NORMAL_RESTORE',task01_complete=True,
        actual_PL_calls=total,manager_exit=0,worker_exits=[0,0],independent_and_delayed_postchecks='PASS',
        no_forced_cleanup=True,all_fresh_permission_checks_retained=True,default_backend_changed=False,
        rollback='/var/lib/kv260-a12/cpu02-candidate-20261024-v1',TTFT10_goal='NOT_MET' if any(r['violation_10s'] for r in clocks) else 'NOT_FINAL_ACCEPTANCE'))
    print(json.dumps(dict(status='PASS_TT10_01_BOARD_AUDIT',actual_PL_calls=total,ordinary_application_measurements=len(clocks),TTFT_app_s=[r['TTFT_app_s'] for r in clocks])))


if __name__=='__main__':main()
