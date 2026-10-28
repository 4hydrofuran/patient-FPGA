"""Independent readback audit: exact state/logits, real T, cancellation, ownership."""
import argparse,json,math
from array import array
from common import ROOT,sha,save
from step09_common import OUT
from step08_audit import extract,lifecycle
from step06_audit import compare

def j(p):return json.loads(p.read_text(encoding='utf-8'))
def lines(p):return [json.loads(s) for s in p.read_text(encoding='utf-8').splitlines()]

def run(variant):
    folder=OUT/variant;dest,receipt=extract(folder);root=dest/'run-v1';left=root/'s1';right=root/'s2'
    spec=j(folder/'bundle-v1/control/window-spec.json');requests=j(folder/'bundle-v1/control/requests.json')
    life=lifecycle(folder,dest,receipt);rows=[];previous=0;traces=[]
    for side in (left,right):
        assert j(side/'identity.json')['binary_sha256']=='18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4'
        assert j(side/'ready.json')['context']==1024 and j(side/'ready.json')['physical_ubatch']==8
    ready=j(right/'ready.json')['bridge']['a12_route'];assert ready['weight_load_count']==72
    assert j(left/'exit.json')['host_permission_runs']==j(left/'exit.json')['weight_load_permissions']==0
    for req in requests:
        s1=j(left/req['id']/'result.json');s2=j(right/req['id']/'result.json');row=dict(id=req['id'])
        assert s1['id']==s2['id']==req['id']
        if req['op']=='reset':assert s1['type']==s2['type']=='reset' and s1['epoch']==s2['epoch'];row['status']='PASS_RESET'
        elif req.get('cache_policy') in ('R1','R2'):
            assert s1['type']==s2['type']=='error' and s1['state_cleared'] and s2['state_cleared'] and all('R1/R2' in s['message'] for s in (s1,s2));row['status']='PASS_DISABLED_POLICY_REJECT'
        else:
            route=s2['bridge']['a12_route'];assert route['execution_kind']=='FPGA_REAL'
            assert route['weight_load_count']==72 and route['owned_bo_charged_bytes']==140591104 and route['a11_explicit_bo_allocations_host_counter']==148
            assert route['a11_live_weights']==ready['a11_live_weights'] and route['a11_io_bo_addresses']==ready['a11_io_bo_addresses']
            total=route['host_verified_completions'];calls=total-previous;previous=total
            assert s1['state_cleared_before_response'] and s2['state_cleared_before_response']
            assert s1['state_position_after_clear']==s2['state_position_after_clear']==-1
            if req.get('cancel_test'):
                assert s1['status']==s2['status']=='CANCELLED' and s1['partial_output_usable'] is False and s2['partial_output_usable'] is False
                assert calls==72 and j(right/req['id']/'reuse-refused.json')['status'].startswith('PASS_')
                row['status']='PASS_REAL_SAFE_BOUNDARY_CANCEL_DISCARD_NO_REUSE'
            else:
                assert s1['status']==s2['status']=='OK' and s1['output_tokens']==s2['output_tokens'] and s1['text']==s2['text'] and s1['eos']==s2['eos']
                assert s1['state_fingerprint']==s2['state_fingerprint'] and s1['last_prompt_logits_fnv64']==s2['last_prompt_logits_fnv64']
                assert s1['state_position_before_clear']==len(req['tokens'])+s1['decode_calls']-1
                assert s2['state_position_before_clear']==len(req['tokens'])+s2['decode_calls']-1
                expected=72*(math.ceil(len(req['tokens'])/min(req['prefill_chunk'],8))+s2['decode_calls'])
                assert calls==expected,(req['id'],calls,expected)
                row.update(status='PASS_SAME_ARM_STATE_LOGITS_TOKENS',state=s2['state_fingerprint'],prefill_logits=s2['last_prompt_logits_fnv64'])
                if req.get('diagnostic'):
                    d1=left/req['id']/'diag';d2=right/req['id']/'diag';numeric={}
                    for p in sorted(d1.glob('logits-*.f32')):
                        values=array('f');values.frombytes(p.read_bytes());assert all(math.isfinite(v) for v in values)
                        values=array('f');values.frombytes((d2/p.name).read_bytes());assert all(math.isfinite(v) for v in values)
                        result=compare((d2/p.name).read_bytes(),p.read_bytes(),.002,.0002);assert result['failures']==0;numeric[p.name]=result
                    assert len(numeric)==10 and (d1/'hybrid-state.bin').read_bytes()==(d2/'hybrid-state.bin').read_bytes()
                    m1=j(d1/'manifest.json');m2=j(d2/'manifest.json');index={(v['id'],v['execution']):v for v in m1['projections']}
                    sampled=[]
                    for v in m2['projections']:
                        q=index[v['id'],v['execution']];assert all(v[k]==q[k] for k in ('T','N','K'))
                        x=compare((d2/v['input']).read_bytes(),(d1/q['input']).read_bytes(),.002,.0002)
                        y=compare((d2/v['output']).read_bytes(),(d1/q['output']).read_bytes(),1e-4,1e-5)
                        assert x['failures']==y['failures']==0
                        sampled.append(dict(id=v['id'],execution=v['execution'],T=v['T'],input=x,output=y))
                    trace=route['a12_trace'];assert len(trace)==calls
                    assert [t['job_id'] for t in trace]==list(range(total-calls+1,total+1))
                    assert {(t['layer'],t['op']) for t in trace}=={(l,o) for l in range(24) for o in ('gate','up','down')}
                    for t in trace:
                        c=t['backend_completion'];assert t['consumer_verified'] and t['execution_kind']=='FPGA_REAL'
                        assert c['output_consumable'] and c['a12_observed_ert_state']==4 and c['kernel_build_id']==0xB3030002 and c['last_status_code']==0
                        raw=bytes.fromhex(c['a12_raw_meta_hex']);assert len(raw)==64 and c['job_id']==t['job_id']
                        le=lambda offset,size:int.from_bytes(raw[offset:offset+size],'little')
                        assert le(0,4)==0x57344138 and le(4,4)==0xB3030002 and le(8,8)==t['job_id']
                        assert le(16,4)==0 and le(20,4)==1 and le(24,8)==1 and le(32,8)==1835008
                        assert c['host_verified_completions']==t['job_id']
                        q=next((v for v in m2['projections'] if v['id']==f"l{t['layer']:02}_{t['op']}" and v['execution']==t['execution']),None)
                        if q:
                            assert t['row_start']==0 and t['T']==q['T'] and sha(d2/q['output'])==t['output_sha256']
                    traces.extend(trace);row.update(logits=numeric,sampled_projections=sampled,physical_T=sorted(set(t['T'] for t in trace)))
            row['real_calls']=calls
        rows.append(row)
    events=lines(right/'worker/events.jsonl');permits=[r for r in events if r['event']=='PERMISSION']
    allowed=[r for r in permits if r['request']['phase']=='submit' and r['allow']]
    denied=[r for r in permits if r['request']['phase']=='submit' and not r['allow']]
    assert len(allowed)==previous==j(right/'exit.json')['host_permission_runs']<=spec['max_runs']
    assert sum(r['allow'] and r['request']['phase']=='weight_load' for r in permits)==72
    if variant=='short':
        assert len(denied)>=1 and all(r['request']['job']>allowed[-1]['request']['job'] for r in denied)
        cancel=[r for r in events if r['event']=='SAFE_CANCEL_BOUNDARY'];assert len(cancel)==1 and cancel[0]['previous_synchronous_calls']==previous and cancel[0]['in_flight_at_boundary']==0
        assert any(r['event']=='LATE_RESULT_DISCARDED' and r.get('delivered') is False for r in events)
        # Across all physical partitions, compare the same 9-token prefix + one decode state.
        for side in (left,right):
            ref=j(side/'short_t8/result.json')
            for name in ('short_t1','short_t2','short_t4','A_after_B_rejects'):
                q=j(side/name/'result.json');assert q['state_fingerprint']==ref['state_fingerprint'] and q['last_prompt_logits_fnv64']==ref['last_prompt_logits_fnv64']
                if name.startswith('short_t'):
                    reference=side/'short_t8/diag';actual=side/name/'diag'
                    assert (reference/'hybrid-state.bin').read_bytes()==(actual/'hybrid-state.bin').read_bytes()
                    for f in reference.glob('logits-*.f32'):assert f.read_bytes()==(actual/f.name).read_bytes()
            a=j(side/'medical_A/result.json');b=j(side/'medical_A_again/result.json')
            assert a['state_fingerprint']==b['state_fingerprint'] and a['last_prompt_logits_fnv64']==b['last_prompt_logits_fnv64']
            other=j(side/'medical_B/result.json');assert other['state_fingerprint']!=a['state_fingerprint'] and other['last_prompt_logits_fnv64']!=a['last_prompt_logits_fnv64']
        assert set(t['T'] for t in traces)=={1,2,4,8}
    else:
        assert not denied
        for side in (left,right):
            a=j(side/'context1024_chunk8/result.json');b=j(side/'context1024_chunk256/result.json')
            assert a['state_fingerprint']==b['state_fingerprint'] and a['last_prompt_logits_fnv64']==b['last_prompt_logits_fnv64']
            assert b['logits_comparison']['failures']==0 and b['logits_comparison']['max_abs']==0
        negative=j(root/'startup-negative/SUMMARY.json');assert negative['status']=='PASS_ARM_MISSING_ARTIFACT_AND_WRONG_CONTRACT_NO_FALLBACK'
        assert len(negative['rows'])==2 and all(r['hardware_submissions']==0 and r['exit_code']==2 and not r['forced_exit'] for r in negative['rows'])
        for row in negative['rows']:
            case=root/'startup-negative'/row['case'];identity=j(case/'identity.json');cfg=j(case/'route.json')
            assert identity['binary_sha256']=='18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4' and identity['expected_exit_code']==2 and identity['no_device_open_permission']
            assert cfg['fpga_required'] is True and cfg['fallback']=='disabled' and cfg['execution_kind']=='FPGA_REAL'
            assert '"type":"ready"' not in (case/'stdout.txt').read_text(encoding='utf-8')
            expected='A12 missing pinned artifact' if row['case']=='missing_required_library' else 'A12 identity/fallback policy'
            raw_error=(case/'stderr.txt').read_text(encoding='utf-8');assert 'S1_FAILURE:' in raw_error and expected in raw_error
            assert len(row['permits'])==(1 if row['case']=='missing_required_library' else 0)
            assert all(q['request']['phase']=='router_open' and q['request']['pid']==identity['pid'] for q in row['permits'])
        old=j(OUT/'short/readback-v1/run-v1/s2/short_t8/result.json');new=j(right/'A_after_cancel_new_window/result.json')
        assert old['state_fingerprint']==new['state_fingerprint'] and old['last_prompt_logits_fnv64']==new['last_prompt_logits_fnv64']
    result=dict(status='PASS_BOARD_TASK09_'+variant.upper(),cases=rows,actual_calls=previous,diagnostic_real_consumed_outputs=len(traces),lifecycle=life,denied_after_cancel=len(denied),hardware_global_count=None,extension2048='NOT_TESTED',dangerous_timeout_poison_BOARD='NOT_TESTED')
    save(OUT/(variant.upper()+'_AUDIT.json'),result);print(json.dumps(dict(status=result['status'],actual_calls=previous,cases=len(rows))))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('variant',choices=['short','context']);run(p.parse_args().variant)
