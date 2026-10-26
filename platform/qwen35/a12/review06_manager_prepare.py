"""Derive one resource-only manager with a non-computing full-residency worker."""
import ast
from common import ROOT

if __name__=='__main__':
    p=ROOT/'platform/qwen35/a12';s=(p/'step07_mlp_manager.py').read_text(encoding='utf-8')
    s=s.replace('from window_closeout_v2 import Window','from window_capacity_only import Window\nfrom capacity_policy import admission,review_archive_cache')
    s=s.replace('a12-mlp-l00-20261024-v1','a12-capacity-20261024-v1')
    start=s.index('def run_case(');end=s.index('\n\ndef main():',start)
    s=s[:start]+'''def run_case(worker,owner,path,*,real):
    ready=receive(worker,owner,path);save(path/'ready.json',ready)
    assert ready['type']=='ready'
    if real:
        r=ready['bridge']['a12_route']
        assert ready['execution_kind']=='FPGA_REAL' and r['weight_load_count']==worker.loads==72
        assert worker.runs==r['host_verified_completions']==0
        assert r['owned_bo_charged_bytes']==140591104 and r['a11_explicit_bo_allocations_host_counter']==148
        assert r['status']=='READY' and not r['a12_trace'] and r['a12_route_scope']=='all'
        spans=list(zip(r['a11_io_bo_addresses'],r['a11_io_bo_charged_sizes']))
        assert r['a11_argument_groups']==[3]*6 and len(r['a11_live_weights'])==72
        for w in r['a11_live_weights']:spans.extend(zip(w['addresses'],w['charged_sizes']))
        assert len(spans)==148 and sum(n for a,n in spans)==140591104
        for i,(addr,size) in enumerate(spans):
            assert 0<=addr and addr+size<=2147483648 and size%8192==0
            assert all(addr+size<=a or a+n<=addr for a,n in spans[:i])
        observed=owner.platform.snapshot('all_72_weights_resident_no_compute')
        reserve=admission(observed['memory_kib'],140591104,already_charged_bo_bytes=140591104)
        save(path/'actual-residency.json',dict(spans=spans,reserve=reserve,zero_submissions=True,weights=72))
        assert reserve['allowed'],'actual all-weight residency reserve failed'
        # No generate request is ever sent to the real worker. Permissions also reject submit.
        r=ready
    else:
        assert ready['execution_kind']=='CPU_REFERENCE' and ready['bridge']['weight_load_count']==72
        request=json.loads((BUNDLE/'control/request.json').read_text())
        request.update(diagnostic_report=False,diagnostic_nodes=False,state_fingerprint=False,dump_state=False,a12_consumer_trace=False)
        save(path/'request.json',request);worker.send(request)
        while True:
            r=receive(worker,owner,path)
            if r['type'] in ('result','error'):break
        save(path/'result.json',r)
        assert r['type']=='result' and r['status']=='OK' and r['state_cleared_before_response'] and r['state_position_after_clear']==-1
    assert worker.close(timeout=10),'normal exit not proven; retain owner'
    assert worker.runs==0
    save(path/'exit.json',dict(pid=worker.process.pid,exit_code=worker.process.returncode,
        host_permission_runs=worker.runs,weight_load_permissions=worker.loads))
    return r
''' +s[end:]
    s=s.replace("scope='l0',max_runs=51,max_loads=3,explicit_bo_budget_bytes=6062080","scope='all',max_runs=1224,max_loads=72,explicit_bo_budget_bytes=140591104")
    s=s.replace("assert initial['memory_kib']['CmaFree']-5920>=32768+65536","assert initial['memory_kib']['CmaFree']>=32768")
    s=s.replace("assert initial['memory_kib']['MemAvailable']-5920>=1048576+65536","assert initial['memory_kib']['MemAvailable']>=1048576")
    s=s.replace("max_session_seconds=120,bundle_sha256", "operation='ALLOCATE_UPLOAD_ONLY_NO_COMPUTE',allowed_kernel_submissions=0,max_session_seconds=120,bundle_sha256")
    anchor="        owner=Owner(p,review,s2)"
    cache='''
        before=p.snapshot('archive_cache_before')
        rows=json.loads((BUNDLE/'control/archive-pins.json').read_text())
        verified=review_archive_cache(rows)
        after=p.snapshot('archive_cache_after')
        save(run/'archive-cache-review.json',dict(before=before['memory_kib'],after=after['memory_kib'],files=verified,
             model_pages_touched=False,drop_caches=False,files_deleted=False))'''
    s=s.replace(anchor,anchor+cache)
    anchor="        run_case(cpu,owner,s1,real=False);p.no_users(module_loaded=False)"
    s=s.replace(anchor,anchor+'''
        pending=p.snapshot('before_full_BO_allocation')
        capacity=admission(pending['memory_kib'],140591104)
        save(run/'pre-allocation-admission.json',capacity)
        assert capacity['allowed'],'fresh conservative full-range admission failed; no allocation'
''')
    s=s.replace("backend_host_verified_completions=result['bridge']['a12_route']['host_verified_completions']", "backend_host_verified_completions=result['bridge']['a12_route']['host_verified_completions']")
    s=s.replace("scope='l0',lease_archived=True,step07_MLP='EXECUTED_PENDING_INDEPENDENT_AUDIT'", "scope='all',lease_archived=True,capacity_probe='72_WEIGHTS_148_BO_ZERO_COMPUTE'")
    s=s.replace('L00_MLP_MODEL_EXECUTION_AND_NORMAL_RESTORE_PENDING_INDEPENDENT_AUDIT','FULL_CAPACITY_LOAD_ONLY_NORMAL_RESTORE_PENDING_AUDIT')
    s=s.replace("status='L00_MLP_NORMAL_EXIT',scope='l0'", "status='CAPACITY_ONLY_NORMAL_EXIT',scope='all',kernel_submissions=0")
    s=s.replace('One reviewed l00 gate/up/down model window','One reviewed full-capacity allocation/upload only window; compute prohibited')
    s=s.replace('Admission is for ONLY l00 gate/up/down: preserve the full-range capacity limitation.','Only load-only permissions will be provided; full capacity admission occurs below before allocation.')
    s=s.replace("        assert reserve['allowed'],'actual all-weight residency reserve failed'",
      "        ready['capacity_reserve_pass']=reserve['allowed']\n        save(path/'resident-process.json',dict(status=Path(f'/proc/{worker.process.pid}/status').read_text(),\n             smaps_rollup=Path(f'/proc/{worker.process.pid}/smaps_rollup').read_text()))")
    s=s.replace("        assert capacity['allowed'],'fresh conservative full-range admission failed; no allocation'",
      "        if not capacity['allowed']:\n            owner.finish(cpu)\n            save(run/'result.json',dict(status='FAIL_FRESH_FULL_CAPACITY_ADMISSION_NO_PL_MUTATION',scope='all',\n                 permission_submissions=0,backend_host_verified_completions=0,lease_archived=True,step08='NOT_STARTED'))\n            return")
    s=s.replace("dict(status='FULL_CAPACITY_LOAD_ONLY_NORMAL_RESTORE_PENDING_AUDIT',",
      "dict(status='FULL_CAPACITY_LOAD_ONLY_NORMAL_RESTORE_PENDING_AUDIT' if result['capacity_reserve_pass'] else 'FAIL_ACTUAL_RESIDENCY_EXTRA_RESERVE_RESTORED_NORMALLY',")
    ast.parse(s);dest=p/'review06_manager.py'
    if dest.exists():assert dest.read_bytes()==s.encode('utf-8'),'existing controller differs from derivation'
    else:dest.write_text(s,encoding='utf-8',newline='\n')
    print('CAPACITY_ONLY_MANAGER_READY_ZERO_COMPUTE')
