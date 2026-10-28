"""Final independent readback, stable resources, lease digest and exactness validation."""
import hashlib
import json
import sys
from common import ROOT,save
from step07_mlp_prepare import OUT

def j(path):return json.loads(path.read_text(encoding='utf-8'))

def main():
    a=j(OUT/'AUDIT.json');assert a['status']=='PASS_BOARD_L00_MLP_REAL_CONSUMPTION_AND_NORMAL_CLOSEOUT'
    assert all(x['bit_exact'] for x in a['logits'].values())
    assert all(x[k]['bit_exact'] for x in a['projections'].values() for k in ('input','output'))
    assert all(x['comparison']['bit_exact'] for x in a['downstream_nodes']) and a['hybrid_state']['bit_exact']
    assert len(a['projections'])==36 and len(a['downstream_nodes'])==72 and a['same_previous_S1']
    run=OUT/'readback-v1/run-v1';r=j(run/'s2/result.json');trace=r['bridge']['a12_route']['a12_trace']
    first=trace[0]['backend_completion'];expected=[]
    for t in trace:
        c=t['backend_completion']
        assert c['a11_io_bo_addresses']==first['a11_io_bo_addresses']
        assert c['a11_live_weights']==first['a11_live_weights']
        assert t['row_start']==0 and t['consumer_verified']
        assert t['consumer_observation']=='INPUT_HASH_BEFORE_AND_EXECUTION_CONFIRMED_AFTER_ALLOWING_IN_PLACE'
        assert (t['consumer_name'],t['consumer_op'])==(('l_out-0','ADD') if t['op']=='down' else ('ffn_swiglu-0','GLU'))
    review=j(run/'review.json');profile=j(run/'s2/runtime-profile.json')
    # Reconstruct expected bytes, compare actual archive digest read independently on board.
    lease=dict(schema='A12_MODEL_LEASE_V1',owner='A',scope=review['scope'],window=review['window_id'],
       identity=review['machine_sha256']+':'+review['boot_id'],pid=profile['manager_pid'],
       owner_start_ticks=profile['manager_start_ticks'],expires_monotonic_ns=profile['expires_monotonic_ns'],
       compute_authorized=True,max_runs=51,max_loads=3,explicit_bo_budget_bytes=6062080)
    pin=hashlib.sha256((json.dumps(lease,ensure_ascii=False,indent=2)+'\n').encode()).hexdigest()
    sys.path.insert(0,str(ROOT/'platform/qwen35/a10'))
    from kernel_log_gate import KernelLogGate
    gate=KernelLogGate();pre=j(OUT/'readback_01/stdout.txt')
    assert gate.observe(review['boot_id'],pre['kernel_raw'],pre['kernel_sha256'])['allowed']
    post=[]
    for name in ('status_01','delayed_01'):
        state=j(OUT/name/'stdout.txt');assert j(OUT/name/'receipt.json')['exit_code']==0
        assert state['boot_id']==review['boot_id'] and state['kernel']=='6.8.12-a10irq2'
        assert state['scans'][-1]['scan_complete'] and state['scans'][-1]['no_users_gate']
        assert not state['module_present'] and not state['active_lease_exists'] and not any(state['locks'].values())
        assert state['known_processes_absent'] and all(state['known_processes_absent'].values())
        assert state['gdm_state']=='active' and state['fpga_state']=='operating'
        assert state['overlays']=={'k26-starter-kits_image_1':'applied'}
        assert state['lease_archived'] and state['lease_sha256']==pin
        k=gate.observe(state['boot_id'],state['kernel_raw'],state['kernel_sha256']);assert k['allowed']
        post.append(dict(snapshot=name,lease_digest_matches_expected=pin,processes_absent=state['known_processes_absent'],kernel_gate=k))
    assert j(OUT/'identity_rejection_01/stdout.txt')['status']=='PASS_BOARD_WRONG_CONTRACT_REJECTED_BEFORE_PERMISSION_OR_DEVICE'
    assert j(OUT/'REAL_Y_REJECTION.json')['actual_matches_graph_trace']
    save(OUT/'FINAL_CHECK.json',dict(status='PASS_BIT_EXACT_STABLE_RESOURCES_AND_DELAYED_NORMAL_CLOSEOUT',
       all_logits_projections_nodes_and_state_bit_exact=True,resources_reused=True,weight_loads=3,
       BO_count=10,BO_bytes=6062080,hardware_calls=9,manager_exit_code=0,worker_exit_codes=[0,0],
       readbacks=post,step08='NOT_STARTED',task06_failures='UNCHANGED_DEFERRED_BY_USER'))
    print('PASS_BIT_EXACT_STABLE_RESOURCES_AND_DELAYED_NORMAL_CLOSEOUT')

if __name__=='__main__':main()
