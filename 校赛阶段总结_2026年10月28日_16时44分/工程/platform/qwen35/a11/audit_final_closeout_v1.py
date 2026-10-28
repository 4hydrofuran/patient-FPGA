"""Offline independent closeout audit. No board connection or mutations."""
import hashlib
import json
from pathlib import Path
import sys
from final_closeout_v2 import BOOT,LEASE,JOURNAL

ROOT=Path(__file__).resolve().parents[3]
EV=ROOT/'evidence/mlp_board_A/20261023-final-closeout-v1'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    sys.path.insert(0,str(ROOT/'platform/local/a11-mlp-20261023-v1'))
    from accelerator_release_gate_v2 import require_no_users
    from kernel_log_gate import KernelLogGate
    r=EV/'readback_01';s=json.loads((r/'state.json').read_bytes())
    packet=json.loads((r/'stdout.jsonl').read_bytes())
    rows=[json.loads(x) for x in (r/'closeout_v2/lifecycle.jsonl').read_bytes().splitlines()]
    result=json.loads((r/'closeout_v2/result.json').read_bytes())
    for name in ('contracts_01.json','config_01.json','tests_02.json','tests_v2_01.json'):
        assert json.loads((EV/name).read_bytes())['exit_code']==0
    for name in ('preflight_01','execute_02','readback_01'):
        assert json.loads((EV/name/'receipt.json').read_bytes())['exit_code']==0
    assert json.loads((EV/'execute_01/receipt.json').read_bytes())['exit_code']==2
    failure=json.loads((r/'closeout_v1/STOP.json').read_bytes())
    assert failure['signal_attempted'] is False and failure['phase']=='RESERVED'
    assert sha(ROOT/'platform/qwen35/a11/final_closeout_v2.py')==json.loads((EV/'execute_02/receipt.json').read_bytes())['helper_sha256']
    assert rows[0]['event']=='CLOSEOUT_RESERVED' and rows[0]['pid']==10888
    signals=[x for x in rows if x['event']=='SIGNAL_BEGIN']
    assert len(signals)==1 and signals[0]['pid']==8851 and signals[0]['signal']=='SIGUSR1'
    expected=['OLD_SUPERVISOR_EXIT_CONFIRMED','CLOSEOUT_LOCKS_ACQUIRED','ARCHIVE_PREPARED',
              'ARCHIVE_BEGIN','ARCHIVE_COMMITTED','STALE_PRIVATE_SOCKET_REMOVED','OWN_LOCK_FDS_CLOSED','CLOSEOUT_TOOL_COMPLETE']
    assert [x['event'] for x in rows if x['event'] in expected]==expected
    assert rows[-1]['event']=='CLOSEOUT_TOOL_COMPLETE'
    assert result['hardware_commands']==result['compute_runs']==0 and result['old_supervisor_normal_exit'] is False
    assert result['locks_deleted'] is False
    for row in rows:
        if row['event']=='KERNEL_CHECK':assert row['result']['allowed']
        if row['event']=='RESOURCE_SCAN':require_no_users(row['scan'],True,boot_id=BOOT)
    require_no_users(s['scan'],True,boot_id=BOOT)
    assert s['boot_id']==BOOT and s['kernel']=='6.8.12-a10irq2'
    assert s['module_present'] is False and s['module_refcount'] is None
    assert s['overlays']=={'k26-starter-kits_image_1':'applied'} and s['fpga_state']=='operating'
    assert s['gdm_state']=='active' and s['gdm_exit_code']==0
    assert not s['render_nodes'] and not s['zocl_bound'] and s['control_socket_present'] is False
    assert len(s['locks'])==2 and all(v==[] for v in s['locks'].values())
    assert set(s['processes'])=={'3202','3308','5322','6174','8851','10685','10888'}
    assert all(v is None for v in s['processes'].values())
    assert packet['files']['active-lease.json'] is None and sha(r/'archived-lease.json')==LEASE
    assert packet['files']['closeout_v2/STOP.json'] is None
    assert sha(r/'v3/lifecycle.jsonl')==JOURNAL and packet['files']['v3/result.json'] is None
    pre=json.loads((EV/'preflight_01/state.json').read_bytes())
    assert s['pins']==pre['pins'] and s['default_firmware']==pre['default_firmware']=='k26-starter-kits'
    assert s['vart_sha256']==pre['vart_sha256'] and s['outputs']==pre['outputs']==[]
    assert s['permits']==pre['permits']
    baseline=(EV/'preflight_01/kernel.raw.txt').read_bytes().decode()
    gate=KernelLogGate();assert gate.observe(BOOT,baseline,sha(EV/'preflight_01/kernel.raw.txt'))['allowed']
    assert gate.observe(BOOT,(r/'kernel.raw.txt').read_bytes().decode())['allowed']
    sealed={}
    for name in ('evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json',
        'evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
        'evidence/mlp_board_A/20261023-cleanup-pc-fix-v3/SEAL.json',
        'evidence/mlp_board_A/20261023-cleanup-board-v3/SEAL.json'):
        entries=json.loads((ROOT/name).read_bytes())['files']
        for path,entry in entries.items():
            p=ROOT/path;assert p.stat().st_size==entry['bytes'] and sha(p)==entry['sha256'],path
        sealed[name]=len(entries)
    peak=max(t for row in rows if row['event']=='HEALTH' for t in row['temperatures_mC'])
    audit=dict(status='PASS_CLOSEOUT_ONLY_NOT_A11',A11='NOT_PASSED',A12='NOT_ELIGIBLE',
        default_PL=True,gdm_active=True,ZOCL_absent=True,accelerator_FDs=0,accelerator_VMAs=0,
        locks_held=0,active_lease_absent=True,lease_archived=True,old_supervisor_exit='AUTHORIZED_SIGUSR1_NOT_NORMAL',
        new_closeout_tool_exit_code=0,all_known_workers_supervisors_absent=True,private_socket_retired=True,
        compute_submissions=0,hardware_load_unload_service_commands=0,reboot_reset_flash=0,
        old_failure_preserved=True,new_kernel_diagnostics=0,peak_sample_temperature_mC=peak,
        readback_temperature_mC=s['temperatures_mC'],elapsed_seconds=(rows[-1]['monotonic_ns']-rows[0]['monotonic_ns'])/1e9,
        readback_delay_seconds=(s['monotonic_ns']-rows[-1]['monotonic_ns'])/1e9,old_seals_verified=sealed,
        next='A11 diagnostic open failure PC preparation; new separately authorized board window required')
    with (EV/'AUDIT.json').open('x') as f:json.dump(audit,f,indent=2)
    print(json.dumps(audit,indent=2))


if __name__=='__main__':main()
