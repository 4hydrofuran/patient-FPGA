"""Independent exact readback, numerical, timing-nesting and lifecycle audit."""
import argparse,json,math
from common import ROOT,sha,save
from step10_common import OUT
from step08_audit import extract,lifecycle

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def audit_profile(result,real):
    p=result['request_profile'];assert p['enabled'] and p['accounting_valid']
    nodes=p['node_profile'];assert nodes['enabled']
    for phase in ('prefill','decode'):
        q=p['phases'][phase];buckets=nodes['phases'][phase]
        assert q['decode_failures']==q['graph_failures']==q['mlp_failures']==0
        assert buckets['mlp_custom']['calls']==q['mlp_calls']
        total=sum(v['wall_ms'] for v in buckets.values())
        assert 0<total<=q['cpu_graph_wall_ms']
        assert abs(q['cpu_graph_wall_ms']+q['host_graph_prepare_schedule_ms']-q['llama_decode_wall_ms'])<1e-6
        assert abs(q['mlp_inclusive_wall_ms']+q['non_mlp_cpu_graph_ms']-q['cpu_graph_wall_ms'])<1e-6
        pieces=sum(q[k] for k in ('linear_service_wall_ms','activation_gather_ms','activation_quant_ms','activation_cache_copy_ms','output_copy_ms','bridge_other_ms'))
        assert abs(pieces-q['mlp_inclusive_wall_ms'])<1e-6
        assert all(math.isfinite(v) and v>=0 for k,v in q.items() if k.endswith('_ms'))
        if real:
            pl=p['pl_profile']['phases'][phase];back=pl['backend'];assert pl['calls']==q['mlp_calls']
            assert pl['backend_call_wall_ms']+pl['completion_report_wall_ms']<=q['linear_service_wall_ms']+0.01
            children=sum(back[k] for k in ('a11_input_copy_and_meta_seed_ms','a11_input_bo_sync_ms','a11_set_args_ms','a11_submit_to_confirmed_completion_ms','a11_meta_sync_ms','a11_meta_validate_ms','a11_output_bo_sync_and_map_ms','a11_output_validate_ms'))
            assert abs(children-back['service_ms'])<1e-5
            assert back['service_ms']+back['a12_permission_wait_ms']<=pl['backend_call_wall_ms']+0.01
    return p

def main(variant):
    folder=OUT/variant;dest,receipt=extract(folder);life=lifecycle(folder,dest,receipt)
    run=dest/'run-v1';spec=j(folder/'bundle-v1/control/window-spec.json');requests=j(folder/'bundle-v1/control/requests.json')
    build=j(OUT/'BUILD-v2.json');pin=build['files']['qwen35-a12']['sha256'];rows=[];previous=0
    sides={s:run/s for s in ('s1','s2')}
    for s,path in sides.items():
        assert j(path/'identity.json')['binary_sha256']==pin
        ready=j(path/'ready.json');assert ready['context']==1024 and ready['physical_ubatch']==8
        assert ready['threads']==ready['kernel_threads']==2
        assert ready['execution_kind']==('CPU_REFERENCE' if s=='s1' else 'FPGA_REAL')
        assert ready['non_mlp_projection_schedule']=='STABLE_PER_TOKEN_SIMD_GEMV'
        assert ready['attention_schedule']=='SIMD_QUERY_ORDER_NO_SPLIT_KV_OR_QUERY_TILING'
    ready=j(sides['s2']/'ready.json')['bridge']['a12_route']
    assert ready['weight_load_count']==72 and ready['owned_bo_charged_bytes']==140591104
    for req in requests:
        name=req['id'];cpu=j(sides['s1']/name/'result.json');pl=j(sides['s2']/name/'result.json')
        row=dict(id=name,profile=req['profile'],teacher_forced=bool(req.get('teacher_tokens')),input_tokens=len(req['tokens']),cpu={},pl={})
        for s,result in (('s1',cpu),('s2',pl)):
            assert result['status']=='OK' and result['decode_rc']==0 and result['partial_output_usable']
            assert result['state_cleared_before_response'] and result['state_position_after_clear']==-1
            assert result['state_fingerprint'] is None and result['memory'] is None
            assert result['logits_mode']=='final' and result['prefill_requested_logits']==1
            assert result['state_position_before_clear']==len(req['tokens'])+result['decode_calls']-1
            client=j(sides[s]/name/'client-timing.json')
            assert len(client['token_events'])==len(result['output_tokens']) and client['result_wall_ms']>0
            assert client['begin_monotonic_ns']<client['token_events'][0]['received_monotonic_ns']<=client['end_monotonic_ns']
            if req['profile']:audit_profile(result,s=='s2')
            else:assert result['request_profile']['enabled'] is False
            events=client['token_events'];interval=(events[-1]['received_monotonic_ns']-events[0]['received_monotonic_ns'])/1e9
            metrics=dict(native_prefill_s=result['prefill_ms']/1000,native_ttft_s=result['ttft_ms']/1000,
                native_decode_s=result['decode_ms']/1000,native_decode_steps=result['decode_calls'],
                native_decode_steps_per_second=result['decode_calls']*1000/result['decode_ms'],
                client_first_token_s=client['first_token_wall_ms']/1000,client_complete_s=client['result_wall_ms']/1000,
                client_after_first_output_tokens_per_second=(len(events)-1)/interval if interval>0 else None,
                output_tokens=len(result['output_tokens']),eos=result['eos'],peak_process_rss_kib=result['peak_rss_kib'],
                native_request_s=result['request_profile']['native_request_wall_ms']/1000)
            row['cpu' if s=='s1' else 'pl']=metrics
        for key in ('output_tokens','text','eos','last_prompt_logits_fnv64','prefill_requested_logits','decode_calls'):assert cpu[key]==pl[key],(name,key)
        if name.startswith('natural'):
            assert cpu['text']==pl['text']=='疼痛在胸骨后。' and cpu['eos'] is True
        route=pl['bridge']['a12_route'];assert route['execution_kind']=='FPGA_REAL'
        assert route['weight_load_count']==72 and route['owned_bo_charged_bytes']==140591104 and route['a11_explicit_bo_allocations_host_counter']==148
        assert route['a11_live_weights']==ready['a11_live_weights'] and route['a11_io_bo_addresses']==ready['a11_io_bo_addresses']
        count=72*((len(req['tokens'])+7)//8+pl['decode_calls']);assert route['host_verified_completions']==previous+count
        previous+=count;row['calls']=count
        raw=bytes.fromhex(route['a12_raw_meta_hex']);le=lambda p,n:int.from_bytes(raw[p:p+n],'little')
        assert len(raw)==64 and le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==previous
        assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
        row['cpu_over_pl_speedup_request']=row['cpu']['client_complete_s']/row['pl']['client_complete_s']
        rows.append(row)
    for path in sides.values():
        for prefix in ('short','natural'):
            a=j(path/(prefix+'_plain')/'result.json');b=j(path/(prefix+'_profile')/'result.json')
            for key in ('output_tokens','text','eos','last_prompt_logits_fnv64'):assert a[key]==b[key]
    events=[json.loads(s) for s in (sides['s2']/'worker/events.jsonl').read_text().splitlines()]
    permits=[r for r in events if r['event']=='PERMISSION']
    assert all(r['allow'] for r in permits)
    assert len([r for r in permits if r['request']['phase']=='submit'])==previous
    assert j(sides['s2']/'exit.json')['host_permission_runs']==previous<=spec['max_runs']
    assert j(sides['s1']/'exit.json')['host_permission_runs']==0
    for r in permits:
        obs=r['health_observation'];assert obs['checks_skipped'] is False and obs['kernel']['allowed'] is True
        assert obs['checked_monotonic_ns']<=r['monotonic_ns']
        if not obs['closing']:
            h=obs['live_health'];assert h['memory_kib']['MemAvailable']>=1114112 and h['memory_kib']['CmaFree']>=98304
            assert all(0<t<55000 for t in h['temperatures_mC'])
    if variant=='optimized':
        for side,path in sides.items():
            for req in requests[:4]:
                old=j(OUT/'baseline/readback-v1/run-v1'/side/req['id']/'result.json');new=j(path/req['id']/'result.json')
                for key in ('output_tokens','text','eos','last_prompt_logits_fnv64'):assert old[key]==new[key]
    result=dict(status='PASS_BOARD_TASK10_'+variant.upper(),rows=rows,actual_calls=previous,lifecycle=life,
                normal_mode_ids=[r['id'] for r in requests if not r['profile']],same_arm_numerical_pairs='ALL_MATCH',
                device_cycles=None,AXI_bus_bytes=None,power=None,physical_total_peak=None,
                statistics='DESCRIPTIVE_ONLY_NO_P95',load_scope='FRESH_PROCESS_NOT_PROVEN_COLD_CACHE',
                compact_completion=spec['compact_completion'],compact_health_journal=spec['compact_health_journal'])
    save(OUT/(variant.upper()+'_AUDIT.json'),result)
    print(json.dumps(dict(status=result['status'],calls=previous,rows=len(rows))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=['baseline','optimized']);main(p.parse_args().variant)
