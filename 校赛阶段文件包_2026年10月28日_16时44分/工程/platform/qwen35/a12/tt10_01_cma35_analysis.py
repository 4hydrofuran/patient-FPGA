"""Offline reconstruction of the v3 comparison interval. Never contacts the board."""
import collections
import datetime
import hashlib
import json
from pathlib import Path
from tt10_01_common import ROOT, OUT, sha, save


def j(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    w=OUT/'window-20261025-v3';e=w/'execution-01';r=e/'parked-extracted-01';run=r/'run-v1'
    dest=w/'analysis-cma35-20261025-v1';dest.mkdir(exist_ok=False)
    inv=j(r/'PARKED_SNAPSHOT.json')['inventory'];local=j(e/'PARKED_READBACK_FILES.json')['files']
    manifest=j(w/'bundle-v4/manifest.json');expected={x['path']:x for x in manifest['files']}
    source_names=['control/tt10_01_manager.py','platform/qwen35/a12/tt10_01_case.py',
        'platform/qwen35/a12/tt10_01_numeric.py','platform/qwen35/a12/tt10_01_common.py',
        'platform/qwen35/a12/capacity_policy.py','platform/qwen35/a12/cpu01b_health.py',
        'platform/qwen35/a12/cpu01b_observer.py']
    inputs={};source_pins={}
    for name in source_names:
        p=w/'bundle-v4'/name
        assert p.stat().st_size==expected[name]['bytes'] and sha(p)==expected[name]['sha256']
        source_pins[name]=expected[name]
    def read_evidence(name):
        p=r/name
        assert p.stat().st_size==inv[name]['bytes'] and sha(p)==inv[name]['sha256']
        assert local[name]['sha256']==inv[name]['sha256']
        inputs[name]=dict(bytes=p.stat().st_size,sha256=sha(p))
        return j(p)
    for name in ('run-v1/lifecycle.jsonl','run-v1/s2/worker/events.jsonl'):
        p=r/name;assert sha(p)==inv[name]['sha256'];inputs[name]=dict(bytes=p.stat().st_size,sha256=sha(p))
    rows=[json.loads(x) for x in (run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
    permits=[json.loads(x) for x in (run/'s2/worker/events.jsonl').read_text(encoding='utf-8').splitlines()]
    sides={};read_plans={}
    for side,real in [('s1',False),('s2',True)]:
        stem=f'run-v1/{side}/diag_hit/'
        timing=read_evidence(stem+'client-timing.json');end=timing['end_monotonic_ns']
        finished=next(x for x in rows if x['event']=='CASE_FINISHED' and x.get('case_id')=='diag_hit' and x['real']==real)
        before=[x for x in rows if x['event']=='LIVE_HEALTH' and x['monotonic_ns']<=end][-1]
        after=next(x for x in rows if x['monotonic_ns']>finished['monotonic_ns'] and x['event'] in ('LIVE_HEALTH','EXACT_RESERVE_REFUSAL_SAVED'))
        sample=after if after['event']=='LIVE_HEALTH' else after['sample']
        sample_ns=sample.get('observed_monotonic_ns',sample.get('monotonic_ns'))
        bm=before['memory_kib'];am=sample['memory_kib']
        assert not any(x['event'] in ('LIVE_HEALTH','EXACT_RESERVE_REFUSAL_SAVED') and end<x['monotonic_ns']<finished['monotonic_ns'] for x in rows)
        gate=read_evidence(stem+'prefix-numerical-gate.json')
        assert gate['result']['equal'] and gate['all_bytes']['equal']
        for name in ('management-profile.json','profile-audit.json'):read_evidence(stem+name)
        plan=[];sizes=collections.Counter();counts=collections.Counter()
        for case in ('diag_full_R0','warm_prefix','diag_hit'):
            prefix=f'run-v1/{side}/{case}/diag/'
            m=read_evidence(prefix+'manifest.json');plan.append((prefix+'manifest.json','manifest'))
            for row in m['projections']:
                for k in ('input','output'):plan.append((prefix+row[k],'projection'))
            for row in m['logits']:plan.append((prefix+row['file'],'logits'))
        for case in ('diag_full_R0','diag_hit'):plan.append((f'run-v1/{side}/{case}/diag/hybrid-state.bin','state'))
        for name,kind in plan:
            sizes[kind]+=inv[name]['bytes'];counts[kind]+=1
        assert len(plan)==len({p for p,k in plan})==4541
        assert sum(sizes.values())==544944148
        read_plans[side]=[dict(path=p,kind=k,bytes=inv[p]['bytes'],sha256=inv[p]['sha256']) for p,k in plan]
        no_grants=[x for x in permits if x['event']=='PERMISSION' and end<x['monotonic_ns']<finished['monotonic_ns']]
        if real:assert no_grants==[] and finished['permission_runs']==2376
        approx=(inv[stem+'prefix-numerical-gate.json']['mtime_ns']-inv[stem+'profile-audit.json']['mtime_ns'])/1e9
        sides[side]=dict(result_end_monotonic_ns=end,case_finished_monotonic_ns=finished['monotonic_ns'],
            post_result_interval_s=(finished['monotonic_ns']-end)/1e9,
            last_memory_observation_ns=before['monotonic_ns'],next_memory_observation_ns=sample_ns,
            actual_memory_endpoint_interval_s=(sample_ns-before['monotonic_ns'])/1e9,
            before=bm,after={k:am[k] for k in ('MemAvailable','CmaFree','CmaTotal')},
            CmaFree_drop_MiB=(bm['CmaFree']-am['CmaFree'])/1024,
            MemAvailable_drop_MiB=(bm['MemAvailable']-am['MemAvailable'])/1024,
            health_samples_inside_post_result_interval=0,
            profile_audit_to_gate_file_mtime_delta_s=approx,
            mtime_delta_is_approximation_not_instrumented_duration=True,
            numeric_read_bytes_by_kind=dict(sizes),numeric_read_count_by_kind=dict(counts),
            numeric_read_total_bytes=sum(sizes.values()),numeric_read_unique_files=len(plan),
            largest_read_file_bytes=max(inv[p]['bytes'] for p,k in plan),
            PL_grants_inside_interval=len(no_grants) if real else 0,
            all_bytes_numeric_gate='PASS_PRESERVED')
    assert read_evidence('run-v1/s1/diag_hit/prefix-numerical-gate.json')==read_evidence('run-v1/s2/diag_hit/prefix-numerical-gate.json')
    assert read_evidence('run-v1/s2/ready.json')['bridge']['a12_route']['a11_live_weights']==read_evidence('run-v1/s2/diag_hit/result.json')['bridge']['a12_route']['a11_live_weights']
    residency=read_evidence('run-v1/s2/actual-residency.json');assert len(residency['spans'])==148
    assert sum(n for a,n in residency['spans'])==140591104
    archive=read_evidence('run-v1/archive-cache-review.json')
    assert len(archive['files'])==19 and not any('tt10-01-20261025-v3' in x['path'] for x in archive['files'])
    save(dest/'READ_PLAN.json',read_plans)
    result=dict(status='OFFLINE_CAUSAL_RECONSTRUCTION_COMPLETE_ATTRIBUTION_NOT_PROVEN',
        updated_beijing=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        scope=dict(board_contact=False,board_mutation=False,model_runs=0,source03_rerun=False,repair_deployed=False,BOARD='NOT_TESTED_THIS_ANALYSIS'),
        sides=sides,explicit_BO=dict(buffers=148,bytes=140591104,weights=72,ready_to_hit_addresses_unchanged=True),
        startup_cache_advice=dict(verified_historical_files=19,current_window_diagnostics_included=False),
        facts=['Both backends reread 544944148 bytes in 4541 distinct files using the same strict comparison',
            'PL post-result interval has zero new permission grants; resident weights/BOs are unchanged',
            'No memory samples exist inside the approximately 35-second comparison interval',
            'The existing 1MiB read loop bounds the Python read buffer, not Linux page cache',
            'Current numerical reads have no file-local fadvise or post-read cache management'],
        leading_hypothesis='Diagnostic rereads/readahead retain movable page-cache pages in CMA; global MemAvailable largely counts them as reclaimable',
        not_proven=['Per-page CMA ownership','Exact instant of decline','Exclusive causation by diagnostic reads',
            'Effectiveness of DONTNEED on this board','Absence of implicit XRT allocations/leaks'],
        thresholds=dict(MemAvailable_kib=1114112,CmaFree_kib=98304,changed=False),
        preserved_v3_status='FAILED_CMA_AFTER_PREFIX_GATES_OWNER_RETAINED',task01_complete=False,PL_TTFT_app_s=None,
        DeepSeek_used=False,actual_model_settings='unknown',inputs=inputs,source_pins=source_pins)
    save(dest/'TIMELINE_AND_IO.json',result)
    print(json.dumps(dict(status=result['status'],sides={s:{k:r[k] for k in ('post_result_interval_s','actual_memory_endpoint_interval_s','CmaFree_drop_MiB','MemAvailable_drop_MiB','numeric_read_total_bytes','numeric_read_unique_files','largest_read_file_bytes')} for s,r in sides.items()},board_contact=False,repair_deployed=False)))


if __name__=='__main__':main()
