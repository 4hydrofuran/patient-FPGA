"""Offline reconciliation of this stopped cleanup; never operates the board."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-cleanup-board-v3'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def audit():
    from cleanup_board_v3 import BOOT,KLOG,LEASE,validate_history
    sys.path.insert(0,str(ROOT/'platform/local/a11-mlp-20261023-v1'))
    from mlp_kernel_gate import MinimalGate
    from isolated_idle_policy import BOOT_FILES,LIBRARIES
    from idle_board_trial import RESTORE
    from accelerator_release_gate_v2 import require_no_users
    d=EV/'final_readback_01'
    state=json.loads((d/'state.json').read_bytes())
    rows=[json.loads(line) for line in (d/'v3/lifecycle.jsonl').read_bytes().splitlines()]
    status=json.loads((EV/'status_01/stdout.jsonl').read_bytes())
    for name in ('contracts_01.json','config_01.json','transport_tests_01.json','transport_tests_02.json','transport_tests_03.json'):
        assert json.loads((EV/name).read_bytes())['exit_code']==0,name
    for name in ('stage_01','prelaunch_readback_02','final_readback_01','status_01'):
        assert json.loads((EV/name/'receipt.json').read_bytes())['exit_code']==0,name
    assert json.loads((EV/'execute_01/receipt.json').read_bytes())['exit_code']==1
    assert json.loads((EV/'prelaunch_readback_01/receipt.json').read_bytes())['exit_code']==1
    assert not (EV/'execute_02/receipt.json').exists(), 'live supervisor must not be called exited'
    assert rows[0]['event']=='RECOVERY_RESERVED' and rows[0]['pid']==8851
    completed=[r['step'] for r in rows if r['event']=='STEP_COMMITTED']
    assert completed==['takeover','remove_test','unload_module','load_default','start_graphics']
    assert [r['step'] for r in rows if r['event']=='STEP_BEGIN']==completed
    assert rows[-1]['event']=='CONTROL_HARD_STOP' and rows[-1]['next_step']=='finalize'
    assert rows[-1]['inflight'] is None and rows[-1]['reason']=='RuntimeError: NON_TRANSIENT_SCAN_ERROR'
    for k in ('state','reason','next_step','completed_steps','inflight','generation'):
        assert status[k]==rows[-1][k]
    assert status['state']=='HARD_STOP_RECONCILE_ONLY'
    signals=[r for r in rows if r['event']=='SIGNAL_BEGIN']
    assert len(signals)==1 and signals[0]['pid']==6174 and signals[0]['signal']=='SIGUSR1'
    assert [r['pid'] for r in rows if r['event']=='PIDFD_EXIT_CONFIRMED']==[6174]
    commands=[r for r in rows if r['event']=='COMMAND_END']
    expected=[['dfx-mgr-client','-listPackage'],['dfx-mgr-client','-remove','0'],['rmmod','zocl'],
              ['dfx-mgr-client','-load','k26-starter-kits'],['systemctl','start','gdm.service']]
    assert [r['argv'] for r in commands]==expected and all(r['exit_code']==0 for r in commands)
    assert [r['argv'] for r in rows if r['event']=='COMMAND_BEGIN']==expected
    observations=[r for r in rows if r['event']=='RELEASE_OBSERVATION']
    assert observations[-1]['phase']=='before_finalize' and observations[-1]['scan']['scan_complete'] is False
    assert {'pid':8959,'reason':'ValueError: PROCESS_OR_FD_TABLE_CHANGED'} in observations[-1]['scan']['scan_issues']
    baseline=ROOT/'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/candidate/cleanup-v3-20261023/reviewed-kernel.raw.txt'
    assert sha(baseline)==KLOG
    gate=MinimalGate();assert gate.observe_action(BOOT,baseline.read_bytes().decode(),KLOG,'none')['allowed']
    advisories=[]
    for row in rows:
        if row['event']=='KERNEL_GATE':
            checked=gate.observe_action(BOOT,row['raw_log'],KLOG,row.get('action','none'))
            assert row['allowed'] and checked['allowed']
            advisories.extend(checked.get('reviewed_advisories',[]))
    final_kernel=gate.observe_action(BOOT,(d/'kernel.raw.txt').read_bytes().decode(),KLOG,'none')
    assert final_kernel['allowed']
    assert state['boot_id']==BOOT and state['kernel']=='6.8.12-a10irq2'
    require_no_users(state['scan'],True,boot_id=BOOT)
    assert state['overlays']=={'k26-starter-kits_image_1':'applied'}
    assert state['module_present'] is False and state['module_refcount'] is None
    assert state['render_nodes']==state['zocl_bound']==[] and state['fpga_state']=='operating'
    assert state['gdm_state']=='active' and state['gdm_exit_code']==0
    assert state['control_socket_present'] is True
    for pid in ('3202','3308','5322','6174'):assert state['processes'][pid] is None
    proc=state['processes']['8851'];assert proc['children']==''
    assert not any(v in proc['maps'] for v in ('/dev/','libxrt_','libsp_linear'))
    assert len(state['locks'])==2 and all(len(v)==1 and 'WRITE 8851 ' in v[0] for v in state['locks'].values())
    assert sha(d/'active-lease.json')==LEASE and not (d/'archived-lease.json').exists()
    assert not (d/'v3/result.json').exists()
    for path,pin in {**BOOT_FILES,**LIBRARIES}.items():assert state['pins'][path]==pin
    for name,pin in RESTORE.items():assert state['pins']['/lib/firmware/xilinx/k26-starter-kits/'+name]==pin
    assert state['default_firmware']=='k26-starter-kits' and state['vart_sha256'] is None
    assert state['outputs']==[] and sorted(state['permits'])==['allow-001.json','ready-001.json']
    assert len(set(state['permits'].values()))==1
    validate_history({name:(d/'original'/name).read_bytes() for name in ('lifecycle.jsonl','worker.stdout.jsonl','STOP.json')})
    temps=[t for row in rows if row['event']=='READBACK' for t in row['temperatures_mC']]
    assert temps and max(temps)<55000
    sealed={}
    for name in ('evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json',
                 'evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
                 'evidence/mlp_board_A/20261023-recovery-continuation-v1/SEAL.json',
                 'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/SEAL.json'):
        seal=json.loads((ROOT/name).read_bytes())
        for path,entry in seal['files'].items():
            p=ROOT/path;assert p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],path
        sealed[name]=len(seal['files'])
    return dict(status='DEFAULT_RESTORED_FINALIZATION_BLOCKED',A11='NOT_PASSED',A12='NOT_ELIGIBLE',
        default_PL_restored=True,gdm_restored=True,module_absent=True,independent_scan_complete=True,
        accelerator_fds=0,accelerator_vmas=0,compute_submissions=0,compute_BO_allocations=0,
        reboot_reset_flash=0,normal_worker_exit=False,supervisor_pid=8851,supervisor_normal_exit=False,
        retained_locks=2,active_lease_retained=True,archive_done=False,completed_steps=completed,
        current_control=status,commands=[dict(argv=r['argv'],exit_code=r['exit_code']) for r in commands],
        reviewed_advisories=advisories,unreviewed_kernel_diagnostics=0,peak_sample_temperature_mC=max(temps),
        execution_until_stop_seconds=(rows[-1]['monotonic_ns']-rows[0]['monotonic_ns'])/1e9,
        independent_readback_delay_seconds=(state['monotonic_ns']-rows[-1]['monotonic_ns'])/1e9,
        final_temperature_mC=state['temperatures_mC'],old_seals_verified=sealed,
        new_compute_or_load_test_authorized=False,
        next='PC review of final-only gate; no live patch/resume/signal/reload. New narrowly reviewed close-out decision required.')


if __name__=='__main__':
    result=audit()
    with (EV/'AUDIT.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps(result,indent=2))
