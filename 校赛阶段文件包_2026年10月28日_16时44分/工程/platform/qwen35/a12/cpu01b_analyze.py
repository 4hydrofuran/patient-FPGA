"""Verify board readback, pair unchanged outputs, and account management spans."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261024-cpu-opt-01b-v1'
BASE=ROOT/'evidence/model_pl_A/20261024-cpu-opt-00-v1/frozen/health-readback/run-v1'


def j(path):return json.loads(path.read_text(encoding='utf-8'))
def sha(raw):return hashlib.sha256(raw).hexdigest()
def save(path,data):
    with path.open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n')


def extract():
    modes=[]
    for line in (OUT/'board_01/stdout.txt').read_text(encoding='utf-8').splitlines():
        event=json.loads(line)
        if event['event']!='READBACK':continue
        raw=base64.b64decode(event['base64'],validate=True)
        assert len(raw)==event['bytes'] and sha(raw)==event['sha256']
        directory=OUT/event['mode'];target=directory/'readback-v1'
        if target.exists():modes.append(event['mode']);continue
        target.mkdir()
        (directory/'readback-v1.tar.gz').write_bytes(raw)
        files={}
        with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as archive:
            members=archive.getmembers();assert len(members)<2000 and sum(m.size for m in members)<134217728
            for member in members:
                path=(target/member.name).resolve()
                assert path.is_relative_to(target.resolve()) and not member.issym() and not member.islnk()
                if member.isdir():path.mkdir(parents=True,exist_ok=True);continue
                assert member.isfile();path.parent.mkdir(parents=True,exist_ok=True)
                data=archive.extractfile(member).read();assert len(data)==member.size
                with path.open('xb') as stream:stream.write(data)
                files[member.name]=dict(bytes=len(data),sha256=sha(data))
        save(directory/'READBACK_FILES.json',files);modes.append(event['mode'])
    return modes


def accounting(profile,native):
    siblings=['request.parse','request.order','owner.total','health.total','decision','record.total','reply.encode','reply.send']
    result={}
    for phase in ('prefill','decode','UNATTRIBUTED_NO_NATIVE_PHASE_COUNTERS'):
        data=profile['totals'].get(phase)
        if data is None:continue
        spans=data['spans'];wall=data['wall_ns']/1e6
        exclusive={name:0.0 for name in siblings}
        for row in profile['rows']:
            if row.get('model_phase')!=phase:continue
            for name in siblings:
                # Decision statements can nest. Union their actual intervals instead
                # of adding inclusive parent/child spans under the same label.
                intervals=sorted((a,b) for label,a,b,cpu in row['spans'] if label==name)
                end=-1
                for a,b in intervals:
                    exclusive[name]+=max(0,b-max(a,end))/1e6
                    end=max(end,b)
        remainder=wall-sum(exclusive.values())
        assert remainder>=-1e-6
        native_wait=native.get('phases',{}).get(phase,{}).get('backend',{}).get('a12_permission_wait_ms')
        result[phase]=dict(calls=data['rows'],manager_wall_ms=wall,manager_thread_cpu_ms=data['thread_cpu_ns']/1e6,
            manager_exclusive_ms=dict(**exclusive,unclassified_manager=remainder),
            nested_spans_ms={k:v['wall_ns']/1e6 for k,v in spans.items()},
            native_permission_wait_ms=native_wait,
            channel_client_scheduling_remainder_ms=None if native_wait is None else native_wait-wall)
    return result


def analyze(modes):
    assert set(modes)=={'off','on'}
    rows=[];profiles={};lifecycle={};calls=0
    for mode in ('off','on'):
        root=OUT/mode/'readback-v1';run=root/'run-v1';manifest=j(root/'manifest.json')
        assert j(root/'manager-exit.json')['exit_code']==0
        assert j(root/'stage-receipt.json')['manifest_sha256']==sha((root/'manifest.json').read_bytes())
        template=j(OUT/mode/'bundle-v1/manifest.json');expected={r['path']:r for r in template['files']}
        actual={r['path']:r for r in manifest['files']}
        assert actual.keys()==expected.keys()
        assert all(actual[k]==expected[k] for k in expected if k!='control/preflight.json')
        for name in ('independent-postcheck.json','delayed-postcheck.json'):
            status=j(root/name)
            assert not status['active_lease_exists'] and not status['module_present'] and not any(status['locks'].values())
            assert status['gdm_state']=='active' and status['fpga_state']=='operating' and status['scans'][-1]['no_users_gate']
        for backend in ('s1','s2'):
            exit=j(run/backend/'exit.json');assert exit['exit_code']==0
            if backend=='s2':
                assert exit['host_permission_runs']==3240 and exit['weight_load_permissions']==72
                calls+=exit['host_permission_runs']
                residency=j(run/backend/'actual-residency.json')
                spans=residency['spans']
                assert residency['weight_loads']==72 and len(spans)==148 and sum(n for a,n in spans)==140591104
                events=[json.loads(line) for line in (run/backend/'worker/events.jsonl').read_text().splitlines()]
                assert not any(e['event']=='PERMISSION_FAULT_RETAIN_OWNER' for e in events)
                groups={}
                fresh_stamps=[]
                for event in events:
                    if event['event']!='PERMISSION':continue
                    assert event['allow'] is True
                    phase=event['request']['phase']
                    observation=event['health_observation']
                    assert observation['checks_skipped'] is False
                    assert observation['checked_monotonic_ns']<=event['monotonic_ns']
                    if phase=='submit':fresh_stamps.append(observation['checked_monotonic_ns'])
                    bucket=groups.setdefault(phase,dict(calls=0,owner_ms=0,health_ms=0,durable_record_ms=None))
                    bucket['calls']+=1;bucket['owner_ms']+=event['owner_check_ms'];bucket['health_ms']+=event['health_check_ms']
                assert {k:v['calls'] for k,v in groups.items()}==dict(router_open=1,device_open=1,weight_load=72,submit=3240,router_close=1)
                assert len(set(fresh_stamps))==3240 and all(a<b for a,b in zip(fresh_stamps,fresh_stamps[1:]))
                lifecycle[mode]=dict(phases=groups,scope='Original durable permission events; startup/load/close retained separately. Detailed observer spans exported for active generate requests only.')
            for name in ('short_profile','natural_plain','natural_profile'):
                folder=run/backend/name;result=j(folder/'result.json');clock=j(folder/'client-timing.json')
                baseline=j(BASE/backend/name/'result.json')
                assert result['status']=='OK' and result['state_cleared_before_response'] and result['state_position_after_clear']==-1
                for key in ('output_tokens','text','eos','last_prompt_logits_fnv64'):
                    assert result[key]==baseline[key],(mode,backend,name,key)
                rows.append(dict(mode=mode,backend=backend,id=name,ttft_s=clock['first_token_wall_ms']/1000,
                    complete_s=clock['result_wall_ms']/1000,prefill_s=result['prefill_ms']/1000,
                    decode_s=result['decode_ms']/1000,decode_calls=result['decode_calls']))
                if mode=='on':
                    profile=j(folder/'management-profile.json')
                    assert all(r['outcome']=='RETURNED' for r in profile['rows'])
                    for row in profile['rows']:
                        assert all(row['start_ns']<=a<=b<=row['end_ns'] for _,a,b,_ in row['spans'])
                        if row.get('permit',{}).get('phase')=='submit':
                            assert sum(name=='record.fsync' for name,a,b,cpu in row['spans'])==1
                    profiles[backend+'/'+name]=dict(accounting=accounting(profile,result['request_profile']['pl_profile']),
                        process_usage_delta=profile['process_usage_delta'],
                        idle=profile['totals'].get('idle'),phase_attribution=profile['phase_attribution'])
    overhead=[]
    for backend in ('s1','s2'):
        for name in ('short_profile','natural_plain','natural_profile'):
            off=next(r for r in rows if r['mode']=='off' and r['backend']==backend and r['id']==name)
            on=next(r for r in rows if r['mode']=='on' and r['backend']==backend and r['id']==name)
            overhead.append(dict(backend=backend,id=name,
                ttft_off_s=off['ttft_s'],ttft_on_s=on['ttft_s'],ttft_delta_s=on['ttft_s']-off['ttft_s'],
                complete_off_s=off['complete_s'],complete_on_s=on['complete_s'],
                complete_delta_s=on['complete_s']-off['complete_s'],
                complete_fraction=on['complete_s']/off['complete_s']-1))
    save(OUT/'ACCOUNTING.json',dict(schema='A12_CPU01B_ACCOUNTING_V1',domain='BOARD',profiles=profiles,lifecycle_permissions=lifecycle,
        explanation='manager_exclusive_ms unions same-label nested intervals before summing siblings. Nested_spans_ms are inclusive and non-additive. Native remainder includes channel, client and scheduling; not pure IPC.'))
    save(OUT/'OBSERVER_OVERHEAD.json',dict(status='MEASURED_TWO_SEQUENTIAL_BOUNDED_WINDOWS',rows=overhead,
        limitations=['One sample per mode/workload; off before on, not randomized; drift and instrumentation are not separated.',
                     'No p95/statistical significance; observed elapsed changes are not optimization gains.']))
    prefill=profiles['s2/natural_profile']['accounting']['prefill']
    ordered=sorted(prefill['manager_exclusive_ms'].items(),key=lambda item:item[1],reverse=True)
    save(OUT/'HOTSPOTS.json',dict(source='on/readback-v1/run-v1/s2/natural_profile/management-profile.json',
        prefill_manager_ranking_ms=ordered,prefill_nested_spans_ms=prefill['nested_spans_ms'],
        native_permission_wait_ms=prefill['native_permission_wait_ms'],
        channel_client_scheduling_remainder_ms=prefill['channel_client_scheduling_remainder_ms'],
        next='Choose 02 equivalent management optimization from measured nested costs; preserve freshness and durable confirmation.'))
    save(OUT/'BOARD_AUDIT.json',dict(status='PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS',real_PL_calls=calls,
        output_checks='TOKEN_TEXT_EOS_PREFILL_LOGITS_DIGEST_MATCH_HEALTH_BASELINE_ALL12_ROWS',
        manager_worker_exits=0,independent_delayed_postchecks=True,ARM_xclbin_math_unchanged=True,
        timing_rows=rows,hardware_cycles=None,power_watts=None,default_FPGA_enabled=False,A12_step11='PENDING',
        full_raw_state_comparison='NOT_REPEATED_PYTHON_ONLY_OBSERVER',context1024='NOT_TESTED'))
    print(json.dumps(dict(status='PASS_BOARD_CPU01B_BOUNDED_DIAGNOSTICS',real_PL_calls=calls,prefill_ranking_ms=ordered)))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--extract-only',action='store_true');args=parser.parse_args()
    modes=extract()
    if args.extract_only:print(json.dumps(dict(extracted=modes)))
    else:analyze(modes)
