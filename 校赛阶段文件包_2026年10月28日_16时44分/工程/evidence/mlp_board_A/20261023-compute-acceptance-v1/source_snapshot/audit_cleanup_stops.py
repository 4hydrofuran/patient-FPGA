"""Offline audit of the two explicitly authorized cleanup attempts; no board I/O."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
A=ROOT/'evidence/mlp_board_A/20261023-recovery-only-v1'
B=ROOT/'evidence/mlp_board_A/20261023-recovery-continuation-v1'


def read(p):return json.loads(p.read_bytes())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]


def main():
    first=rows(A/'stopped_readback_01/recovery-only-20261023-v1/lifecycle.jsonl')
    second=rows(B/'readback_01/recovery-continuation-20261023-v1/lifecycle.jsonl')
    state=read(B/'readback_01/state.json')
    assert [r['pid'] for r in first if r['event']=='SIGNAL_BEGIN']==[3308,3202]
    assert [r['pid'] for r in second if r['event']=='SIGNAL_BEGIN']==[5322]
    for rs in (first,second):
        signals=[r for r in rs if r['event']=='SIGNAL_BEGIN']
        assert all(r['signal']=='SIGUSR1' and r['normal_exit'] is False for r in signals)
        assert [r['pid'] for r in rs if r['event']=='PIDFD_EXIT_CONFIRMED']==[r['pid'] for r in signals]
        assert not any(r['event'] in ('COMMAND_BEGIN','GDM_START','RECOVERY_COMPLETE') for r in rs)
        assert rs[-1]['event']=='RECOVERY_STOPPED_NO_RETRY'
        assert all(r['allowed'] for r in rs if r['event']=='KERNEL_GATE')
    assert not state['worker_exists'] and state['manager_proc'] is None and not state['prior_cleanup_exists']
    scan=state['scan']
    assert scan['scan_complete'] and not scan['scan_issues'] and not scan['device_holders'] and not scan['device_mappings']
    assert state['module_refcount']=='0' and state['cleanup_locks_owned']==[True,True]
    assert state['recovery_process']['pid']==6174 and state['recovery_process']['children']==''
    assert not any(x in state['recovery_process']['maps'] for x in ('libxrt_','libsp_linear','/dev/'))
    assert state['gdm_state']=='inactive' and state['overlays']=={'a11-mlp-20261023-v1_image_1':'applied'}
    assert digest(B/'readback_01/kernel.raw.txt')==digest(A/'stop_details_02/kernel.raw.txt')
    assert read(B/'readback_01/fetch_receipt.json')['exit_code']==0
    for root,names in [(A,['tests_01.json']), (B,['tests_01.json','contracts_01.json','config_01.json'])]:
        for name in names:assert read(root/name)['exit_code']==0
    old={}
    for seal in ['evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
                 'evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json']:
        files=read(ROOT/seal)['files']
        for rel,v in files.items():
            p=ROOT/rel;assert p.stat().st_size==v['bytes'] and digest(p)==v['sha256'],rel
        old[seal]=len(files)
    samples=[];previous=None
    for line,r in enumerate(second,1):
        if r['event']!='RELEASE_OBSERVATION':continue
        s=r['scan'];current={(p['pid'],p['start_ticks']) for p in s['inspected_processes']}
        samples.append(dict(source_line=line,phase=r['phase'],attempt=r['attempt'],complete=s['scan_complete'],
            issues=s['scan_issues'],process_count=len(current),
            added=sorted(current-previous) if previous is not None else None,
            removed=sorted(previous-current) if previous is not None else None))
        previous=current
    report=dict(status='PARTIAL_RECOVERY_STOPPED_DEFAULT_NOT_RESTORED',audit_domain='PC_OFFLINE',audit_exit_code=0,
        authorized_signal_targets=[3308,3202,5322],all_target_exits_confirmed=True,normal_worker_exit=False,
        hardware_commands_in_cleanup=0,compute_submissions=0,default_restored=False,A11='NOT_PASSED',A12='NOT_ELIGIBLE',
        current_waiter_pid=6174,current_waiter_start_ticks=second[0]['start_ticks'],
        final_readback_monotonic_ns=state['monotonic_ns'],module_refcount=0,
        fd_vma_scan_complete=True,device_fds=0,device_vmas=0,locks_retained=True,active_lease_retained=True,
        gdm_state='inactive',overlays=state['overlays'],temperatures_mC=state['temperatures_mC'],
        original_transport_exit_code=read(A/'execute_01/host_receipt.json')['exit_code'],
        continuation_transport_exit_code=None,continuation_remote_process_still_running=True,
        no_new_kernel_text_since_first_release=True,prior_seals_verified=old,
        pc_tests=dict(original_methods=6,continuation_methods=13),readiness_samples=samples,
        cause='Three complete post-handover scans had changing global PID sets; fourth scan incomplete. No two globally identical complete sets. Not evidence of a new accelerator fault.',
        remaining=['Do not treat stopped guard as recovery success','Review global process identity condition and controlled continuation design on PC',
                   'New scoped authorization before any further termination or configuration action',
                   'Ordinary unload/default PL/GDM restoration and independent final readback still NOT_DONE'])
    with (B/'AUDIT.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    files={}
    for root in (A,B):
        for p in root.rglob('*'):
            if not p.is_file():continue
            # Live host receipt/stdout is not a final, immutable record.
            if root==B and 'execute_01' in p.relative_to(root).parts:continue
            if p.name=='SEAL.json':continue
            files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=digest(p))
    for name in ['recover_open_only.py','recovery_host.py','test_recover_open_only.py','prepare_recovery_evidence.py',
                 'recover_cleanup_waiter.py','recovery_continuation_host.py','test_recover_cleanup_waiter.py',
                 'prepare_recovery_continuation.py','audit_cleanup_stops.py']:
        p=Path(__file__).parent/name;files[p.relative_to(ROOT).as_posix()]=dict(bytes=p.stat().st_size,sha256=digest(p))
    with (B/'SEAL.json').open('x',encoding='utf-8') as f:json.dump(dict(status='SEALED_PARTIAL_NOT_RECOVERED',
        excluded_live_paths=['evidence/mlp_board_A/20261023-recovery-continuation-v1/execute_01/'],files=files),f,indent=2)
    print(json.dumps(dict(status=report['status'],offline_audit='PASS',sealed_files=len(files),prior_seals_verified=old)))


if __name__=='__main__':main()
