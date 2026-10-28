"""Independent audit of health-only candidate, exact lifecycle and same-arm results."""
import hashlib,json,sys
from pathlib import Path
from common import ROOT,sha,save
from step08_audit import extract,lifecycle
from step10_audit import audit_profile

OUT=ROOT/'evidence/model_pl_A/20261024-health-opt-v1'
def j(p):return json.loads(p.read_text(encoding='utf-8'))

if __name__=='__main__':
    folder=OUT/'candidate';dest,receipt=extract(folder);life=lifecycle(folder,dest,receipt)
    run=dest/'run-v1';spec=j(folder/'bundle-v1/control/window-spec.json')
    package=j(OUT/'PACKAGE.json');rows=[];previous=0
    for side in ('s1','s2'):
        assert j(run/side/'identity.json')['binary_sha256']==package['binary_sha256']
        ready=j(run/side/'ready.json');assert ready['context']==1024 and ready['physical_ubatch']==8
        assert ready['threads']==ready['kernel_threads']==2
        assert ready['execution_kind']==('CPU_REFERENCE' if side=='s1' else 'FPGA_REAL')
    ready=j(run/'s2/ready.json')['bridge']['a12_route']
    assert ready['weight_load_count']==72 and ready['owned_bo_charged_bytes']==140591104
    for req in j(folder/'bundle-v1/control/requests.json'):
        name=req['id'];cpu=j(run/'s1'/name/'result.json');pl=j(run/'s2'/name/'result.json')
        for key in ('output_tokens','text','eos','last_prompt_logits_fnv64','prefill_requested_logits','decode_calls'):
            assert cpu[key]==pl[key],(name,key)
            for side,current in (('s1',cpu),('s2',pl)):
                old=j(ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/readback-v1/run-v1'/side/name/'result.json')
                assert old[key]==current[key],('historical',name,side,key)
        for side,current in (('s1',cpu),('s2',pl)):
            assert current['status']=='OK' and current['decode_rc']==0 and current['partial_output_usable']
            assert current['state_cleared_before_response'] and current['state_position_after_clear']==-1
            assert current['state_fingerprint'] is None and current['memory'] is None
            if req['profile']:audit_profile(current,side=='s2')
        route=pl['bridge']['a12_route'];count=72*((len(req['tokens'])+7)//8+pl['decode_calls']);previous+=count
        assert route['host_verified_completions']==previous
        assert route['weight_load_count']==72 and route['owned_bo_charged_bytes']==140591104
        assert route['a11_explicit_bo_allocations_host_counter']==148
        assert route['a11_live_weights']==ready['a11_live_weights'] and route['a11_io_bo_addresses']==ready['a11_io_bo_addresses']
        raw=bytes.fromhex(route['a12_raw_meta_hex']);le=lambda p,n:int.from_bytes(raw[p:p+n],'little')
        assert len(raw)==64 and le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==previous
        assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and route['a12_observed_ert_state']==4
        clients={s:j(run/s/name/'client-timing.json') for s in ('s1','s2')}
        old=j(ROOT/'evidence/model_pl_A/20261024-step10-v1/optimized/readback-v1/run-v1/s2'/name/'client-timing.json')
        metrics=clients['s2']['permission_metrics_delta']
        assert metrics['calls']==count
        rows.append(dict(id=name,calls=count,cpu_complete_s=clients['s1']['result_wall_ms']/1000,
            pl_complete_s=clients['s2']['result_wall_ms']/1000,cpu_first_s=clients['s1']['first_token_wall_ms']/1000,
            pl_first_s=clients['s2']['first_token_wall_ms']/1000,previous_pl_complete_s=old['result_wall_ms']/1000,
            health_s=metrics['health_check_ms']/1000,previous_health_s=old['permission_metrics_delta']['health_check_ms']/1000,
            owner_s=metrics['owner_check_ms']/1000,durable_record_s=metrics['durable_permission_record_ms']/1000,
            pl_permission_s=sum(v['backend']['a12_permission_wait_ms'] for v in pl['request_profile'].get('pl_profile',{}).get('phases',{}).values())/1000 if req['profile'] else None,
            numerical='MATCH_SAME_ARM_CPU_AND_OLD_PL_TOKENS_TEXT_EOS_PREFILL_LOGITS',
            health_metrics=j(run/'s2'/name/'health-metrics.json')))
    permits=[]
    with (run/'s2/worker/events.jsonl').open(encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if r['event']!='PERMISSION':continue
            assert r['allow'] is True
            obs=r['health_observation'];assert obs['checks_skipped'] is False and obs['kernel']['allowed'] is True
            assert obs['checked_monotonic_ns']<=r['monotonic_ns']
            h=obs['live_health'];assert h['memory_kib']['MemAvailable']>=1114112 and h['memory_kib']['CmaFree']>=98304
            assert all(0<t<55000 for t in h['temperatures_mC'])
            if r['request']['phase']=='submit':permits.append(r)
    assert len(permits)==previous<=5000
    assert j(run/'s2/exit.json')['host_permission_runs']==previous
    # Rebuild lease bytes independently; an existing history path alone is insufficient.
    review=j(run/'review.json');profile=j(run/'s2/runtime-profile.json')
    lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope=review['scope'],window=review['window_id'],
        identity=review['machine_sha256']+':'+review['boot_id'],pid=profile['manager_pid'],
        owner_start_ticks=profile['manager_start_ticks'],expires_monotonic_ns=profile['expires_monotonic_ns'],
        compute_authorized=True,max_runs=review['max_runs'],max_loads=review['max_loads'],explicit_bo_budget_bytes=review['explicit_bo_budget_bytes'])
    pin=hashlib.sha256((json.dumps(lease,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
    for n in ('status_final','delayed_01'):assert j(folder/n/'stdout.txt')['lease_sha256']==pin
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from accelerator_release_gate_v2 import require_no_users
    from step07_finalize_policy import transient_scan
    events=[json.loads(s) for s in (run/'s2/finalization-events.jsonl').read_text().splitlines()]
    scans=[r for r in events if r['event']=='FULL_PROCESS_OBSERVATION'];assert scans
    for row in scans[:-1]:assert transient_scan(row['scan'],review['boot_id'])
    require_no_users(scans[-1]['scan'],True,boot_id=review['boot_id'])
    save(OUT/'BOARD_AUDIT.json',dict(status='PASS_HEALTH_ONLY_BOARD_BOUNDED',rows=rows,calls=previous,lifecycle=life,
        archived_lease_sha256=pin,complete_final_scan=True,final_scan_attempts=len(scans),
        physical_peak_bytes=None,hardware_cycles=None,default_FPGA_enabled=False,
        statistics='SINGLE_PASS_SMALL_SAMPLE_ORDER_CPU_THEN_PL_NOT_GENERAL_SPEEDUP',
        dangerous_BOARD_faults='NOT_TESTED',context1024='NOT_RETESTED_HEALTH_CANDIDATE'))
    print(json.dumps(dict(status='PASS_HEALTH_ONLY_BOARD_BOUNDED',calls=previous,rows=len(rows))))
