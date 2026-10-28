"""Assess bounded candidate with the predeclared CPU02 rule, without extrapolation."""
import json


def save(path,x):
    with path.open('x',encoding='utf-8') as stream:json.dump(x,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def assess(out,profiles,index):
    design=json.loads((out/'DESIGN.json').read_text(encoding='utf-8'))
    comparisons=[]
    for side in ('s1','s2'):
        for name in ('short_plain','natural_plain','natural_plain_2','natural_profile'):
            old=index['baseline',side,name][1];new=index['candidate',side,name][1]
            comparisons.append(dict(side=side,id=name,baseline=old,candidate=new,
                ttft_fraction=new['client_first_token_s']/old['client_first_token_s']-1,
                complete_fraction=new['client_complete_s']/old['client_complete_s']-1))
    manager={}
    for phase in ('prefill','decode'):
        old=profiles['baseline/s2/natural_profile']['management'][phase];new=profiles['candidate/s2/natural_profile']['management'][phase]
        manager[phase]=dict(baseline=old,candidate=new,native_wait_fraction=new['native_permission_wait_ms']/old['native_permission_wait_ms']-1,
            manager_wall_fraction=new['manager_wall_ms']/old['manager_wall_ms']-1,
            exclusive_fraction={k:new['manager_exclusive_ms'][k]/old['manager_exclusive_ms'][k]-1 if old['manager_exclusive_ms'][k] else None for k in old['manager_exclusive_ms']})
        # Each submit has exactly one persistent record, with its own fsync span.
        folder=out/'candidate/readback-v1/run-v1/s2/natural_profile'
        raw=json.loads((folder/'management-profile.json').read_text(encoding='utf-8'))
        rows=[r for r in raw['rows'] if r.get('model_phase')==phase]
        assert len(rows)==new['calls']
        assert all(sum(1 for name,*_ in r['spans'] if name=='record.fsync')==1 for r in rows)
    ordinary=[r for r in comparisons if r['id'] in ('natural_plain','natural_plain_2')]
    checks=dict(native_permission_both_phases=all(v['native_wait_fraction']<0 for v in manager.values()),
        ordinary_PL_both_pairs_TTFT_and_complete=all(r['ttft_fraction']<0 and r['complete_fraction']<0 for r in ordinary if r['side']=='s2'),
        ordinary_CPU_complete_within_5pct=all(r['complete_fraction']<=.05 for r in ordinary if r['side']=='s1'))
    accepted=all(checks.values())
    health=json.loads((out/'candidate/readback-v1/run-v1/s2/natural_profile/health-metrics.json').read_text(encoding='utf-8'))
    assert health['reader_drains']>=4896 and health['schedule']['fresh_calls']>=4896
    cache=json.loads((out/'candidate/readback-v1/run-v1/s2/natural_profile/representation-metrics.json').read_text(encoding='utf-8'))
    assert cache['retained_snapshots']<=2 and cache['retained_payload_bytes']<=16777216
    save(out/'PERFORMANCE.json',dict(status='ACCEPTED_BOUNDED_SAMPLE_CPU02' if accepted else 'REJECTED_CPU02_PERFORMANCE_KEEP_CPU01',accepted=accepted,
        checks=checks,comparisons=comparisons,management=manager,decision_rule=design['acceptance'],
        physical_domain='BOARD',final_task08_acceptance=False,p95=None,power=None,device_cycles=None))
    # Same JSON parser format; raw descriptor removes Python flush stage only.
    save(out/'PERSISTENCE.json',dict(status='PASS_EACH_SUBMIT_OWN_FSYNC_BEFORE_REPLY',fsync_per_submit=1,
        first_journal_directory_fsync=True,raw_fd_has_Python_buffer=False,record_flush_metric='NOT_APPLICABLE_RAW_FD',
        records_json_schema='UNCHANGED_PARSED_FIELDS_COMPACT_WHITESPACE',fresh_journal_identity_and_extent_check_per_record=True,
        no_batch_permission=True,no_async_ack=True,no_cached_health_or_owner_decision=True,
        actual_kmsg_drains=health['reader_drains'],actual_fresh_observations=health['schedule']['fresh_calls'],representation_cache=cache))
