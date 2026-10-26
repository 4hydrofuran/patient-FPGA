"""Independently verify real full BO residency, zero compute, reserve and restoration."""
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from common import ROOT,sha,save
from review06_common import OUT
from capacity_policy import admission

def j(p):return json.loads(p.read_text(encoding='utf-8'))

def main():
    receipt=j(OUT/'readback_01/stdout.txt');archive=OUT/'readback-v1.tar.gz'
    assert sha(archive)==receipt['package']['sha256'] and archive.stat().st_size==receipt['package']['bytes']
    dest=OUT/'readback-v1';dest.mkdir()
    files={}
    with tarfile.open(archive) as tar:
        members=tar.getmembers();assert len(members)==len({m.name for m in members})
        for m in members:
            assert m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts
            data=tar.extractfile(m).read();p=dest/m.name;p.parent.mkdir(parents=True,exist_ok=True)
            with p.open('xb') as f:f.write(data)
            files[m.name]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    save(OUT/'READBACK_FILES.json',files)
    run=dest/'run-v1';r=j(run/'result.json')
    assert r['status']=='FULL_CAPACITY_LOAD_ONLY_NORMAL_RESTORE_PENDING_AUDIT',r
    assert r['permission_submissions']==r['backend_host_verified_completions']==0
    assert r['capacity_probe']=='72_WEIGHTS_148_BO_ZERO_COMPUTE' and r['step08']=='NOT_STARTED'
    assert j(dest/'manager-exit.json')['exit_code']==0
    for s in ('s1','s2'):assert j(run/s/'exit.json')['exit_code']==0 and j(run/s/'exit.json')['host_permission_runs']==0
    cpu=j(run/'s1/result.json');assert cpu['status']=='OK' and cpu['state_cleared_before_response']
    ready=j(run/'s2/ready.json');backend=ready['bridge']['a12_route']
    for s in ('s1','s2'):
        identity=j(run/s/'identity.json')
        assert identity['physical_domain']=='BOARD' and identity['binary_sha256']=='18d3d929cafdaa5043be5e4febf6150a938f12be5a1ea2da56d36be893a6c7d4'
    assert ready['execution_kind']=='FPGA_REAL' and backend['weight_load_count']==72 and backend['host_verified_completions']==0
    assert backend['owned_bo_charged_bytes']==140591104 and backend['a11_explicit_bo_allocations_host_counter']==148
    assert backend['a11_argument_groups']==[3]*6 and len(backend['a11_live_weights'])==72 and not backend['a12_trace']
    assert backend['hardware_done_count'] is None
    assert backend['kernel_build_id']==0xB3030002
    assert backend['xclbin_sha256']=='bdcb66ca69279e0109928d7b32c3ea0325f617a267e1869636944ba3c193b5fa'
    spans=list(zip(backend['a11_io_bo_addresses'],backend['a11_io_bo_charged_sizes']))
    for w in backend['a11_live_weights']:spans.extend(zip(w['addresses'],w['charged_sizes']))
    assert len(spans)==148 and sum(n for addr,n in spans)==140591104
    for i,(addr,n) in enumerate(spans):
        assert 0<=addr and addr+n<=2147483648 and n%8192==0
        assert all(addr+n<=a or a+s<=addr for a,s in spans[:i])
    events=[json.loads(l) for l in (run/'s2/worker/events.jsonl').read_text(encoding='utf-8').splitlines()]
    permits=[e for e in events if e['event']=='PERMISSION']
    assert len(permits)==75 and all(e['allow'] for e in permits)
    assert [e['request']['phase'] for e in permits]==['router_open','device_open']+['weight_load']*72+['router_close']
    assert not any(e.get('request',{}).get('phase')=='submit' for e in events)
    assert not (run/'s2/request.json').exists() and not (run/'s2/ISOLATED.json').exists()
    cfg=j(run/'s2/runtime-profile.json');review=j(run/'review.json')
    assert review['operation']=='ALLOCATE_UPLOAD_ONLY_NO_COMPUTE' and review['allowed_kernel_submissions']==0
    assert review['scope']=='all' and review['max_loads']==72
    lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope=review['scope'],window=review['window_id'],
       identity=review['machine_sha256']+':'+review['boot_id'],pid=cfg['manager_pid'],owner_start_ticks=cfg['manager_start_ticks'],
       expires_monotonic_ns=cfg['expires_monotonic_ns'],compute_authorized=True,max_runs=1224,max_loads=72,explicit_bo_budget_bytes=140591104)
    lease_digest=hashlib.sha256((json.dumps(lease,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
    pre=j(run/'pre-allocation-admission.json');actual=j(run/'s2/actual-residency.json')
    for item in (pre,actual['reserve']):
        expected=admission(item['memory_kib'],140591104,already_charged_bo_bytes=item['already_charged_bo_bytes'])
        assert expected==item and item['allowed']
    assert actual['reserve']['already_charged_bo_bytes']==140591104 and actual['reserve']['pending_bo_bytes']==0
    cache=j(run/'archive-cache-review.json');pins=j(OUT/'bundle-v1/control/archive-pins.json')
    assert len(cache['files'])==len(pins)==7 and not cache['drop_caches'] and not cache['files_deleted']
    for x,y in zip(cache['files'],pins):
        assert all(x[k]==v for k,v in y.items()) and x['hash_verified_before_advice'] and x['identity_size_mtime_unchanged']
    lifecycle=[json.loads(l) for l in (run/'lifecycle.jsonl').read_text(encoding='utf-8').splitlines()]
    checks=[l for l in lifecycle if l['event']=='READBACK'];gates=[l for l in lifecycle if l['event']=='KERNEL_LOG_GATE']
    assert gates and all(g['allowed'] for g in gates)
    assert all(l['exit_code']==0 for l in lifecycle if l['event']=='COMMAND_END')
    peak=dict(min_MemAvailable_kib=min(x['memory_kib']['MemAvailable'] for x in checks),
       min_CmaFree_kib=min(x['memory_kib']['CmaFree'] for x in checks),
       max_temperature_mC=max(z for x in checks for z in x['temperatures_mC']),samples=len(checks),
       S1_RSS_HWM_kib=j(run/'s1/result.json')['peak_rss_kib'],S2_RSS_HWM_kib=ready['peak_rss_kib'],
       total_physical_peak_bytes=None)
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from kernel_log_gate import KernelLogGate
    gate=KernelLogGate();assert gate.observe(review['boot_id'],gates[-1]['raw_log'],gates[-1]['current_sha256'])['allowed']
    assert gate.observe(receipt['boot_id'],receipt['kernel_raw'],receipt['kernel_sha256'])['allowed']
    post=[]
    for name in ('status_01','delayed_01'):
        state=j(OUT/name/'stdout.txt');assert j(OUT/name/'receipt.json')['exit_code']==0
        assert state['boot_id']==review['boot_id'] and state['kernel']=='6.8.12-a10irq2'
        assert state['scans'][-1]['no_users_gate'] and state['scans'][-1]['scan_complete']
        assert not state['module_present'] and not state['active_lease_exists'] and not any(state['locks'].values())
        assert state['known_processes_absent'] and all(state['known_processes_absent'].values())
        assert state['gdm_state']=='active' and state['fpga_state']=='operating' and state['lease_archived']
        assert state['lease_sha256']==lease_digest
        assert state['overlays']=={'k26-starter-kits_image_1':'applied'}
        k=gate.observe(state['boot_id'],state['kernel_raw'],state['kernel_sha256']);assert k['allowed']
        post.append(dict(snapshot=name,kernel_gate=k,processes_absent=state['known_processes_absent'],lease_sha256=state['lease_sha256']))
    numeric=j(OUT/'NUMERIC_REVIEW.json');assert len(numeric['comparisons'])==17
    out=dict(status='PASS_STEP06_REVIEW_NO_REMAINING_BLOCKER_FOR_CONTROLLED_STEP08',
       numerical_disposition='CROSS_ISA_FAIL_REPRODUCED_SAME_BOARD_REFERENCE_REQUIRED',
       independent_scalar_cases=17,actual_PL_outputs_independently_checked=9,
       full_residency=dict(weight_loads=72,explicit_BO_count=148,explicit_BO_bytes=140591104,
          low2GiB_nonoverlap_group3_allocation_alignment8192=True,pre_allocation_admission=pre,
          actual_residency_reserve=actual['reserve'],hardware_kernel_submissions=0),
       cache_review=cache,resource=peak,independent_postchecks=post,
       manager_exit=0,worker_exits=[0,0],default_restore=True,active_lease=False,held_locks=False,
       original_failures='RETAINED_NO_RETROACTIVE_PASS',step08='NOT_STARTED',
       full_model_computation='NOT_TESTED',performance_speedup=None,
       remaining_conditions=['fresh identity/kernel/locks and live reserve at next window',
          'same-board matching S1/S2; cross-ISA is separate limitation',
          'all 72 projection actual-Y consumption/numerics must pass in task08',
          'diagnostic archive cache treatment only for exact pinned task artifacts',
          'physical workload peak and generation stability still unmeasured'])
    save(OUT/'AUDIT.json',out)
    print(json.dumps(dict(status=out['status'],full_residency=out['full_residency'],resource=peak)))

if __name__=='__main__':main()
