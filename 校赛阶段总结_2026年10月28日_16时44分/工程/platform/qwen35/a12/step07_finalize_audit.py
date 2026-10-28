"""Independent offline closeout audit; old abnormal manager exit remains explicit."""
import importlib.util
import json
from pathlib import Path
import tarfile
from common import ROOT,sha,save
from step07_finalize_policy import validate_retirement

OUT=ROOT/'evidence/model_pl_A/20261024-step07-finalize-v1'


def main():
    e=json.loads((OUT/'EXPECTED.json').read_text(encoding='utf-8'))
    r=json.loads((OUT/'readback_01/stdout.txt').read_text(encoding='utf-8'))
    package=OUT/'readback-v1.tar.gz';assert package.stat().st_size==r['package']['bytes'] and sha(package)==r['package']['sha256']
    dest=OUT/'readback-v1';reuse=dest.exists()
    if not reuse:dest.mkdir()
    files={}
    with tarfile.open(package) as tar:
        members=tar.getmembers();assert len(members)==len({m.name for m in members})
        for m in members:
            assert m.isfile() and Path(m.name).name==m.name
            data=tar.extractfile(m).read();p=dest/m.name
            if reuse:assert p.read_bytes()==data
            else:
                with p.open('xb') as f:f.write(data)
            files[m.name]=dict(bytes=len(data),sha256=sha(p))
    if (OUT/'READBACK_FILES.json').exists():assert json.loads((OUT/'READBACK_FILES.json').read_text(encoding='utf-8'))==files
    else:save(OUT/'READBACK_FILES.json',files)
    def j(name):return json.loads((dest/name).read_text(encoding='utf-8'))
    before=j('before-retirement.json');validate_retirement(before,e,now_ns=before['observed_monotonic_ns'])
    assert (dest/'controller.py').read_bytes()==(OUT/'execute_reviewed.py').read_bytes()
    assert not (dest/'STOP.json').exists() and j('controller-exit.json')['exit_code']==0
    assert j('old-manager-exit.json')==dict(pid=27132,exit_code=-9)
    events=[json.loads(l) for l in (dest/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    signals=[v for v in events if v['event']=='EXACT_PARKED_OWNER_SIGNAL_SENT']
    assert len(signals)==1 and signals[0]['pid']==27132 and signals[0]['signal']==9
    reserve=[v for v in events if v['event']=='EXACT_PARKED_OWNER_RETIRE_RESERVED'];assert len(reserve)==1
    assert reserve[0]['start_ticks']==2110722 and reserve[0]['normal_manager_exit'] is False
    assert 0<=reserve[0]['monotonic_ns']-before['observed_monotonic_ns']<=5_000_000_000
    assert all(v['allowed'] for v in events if v['event']=='KERNEL_OBSERVATION')
    final=j('independent-readback-v1.json');result=j('result.json')
    assert final['status']=='PASS_INDEPENDENT_FINALIZE_ONLY_NO_DEVICE_USERS_LOCKS_OR_ACTIVE_LEASE'
    assert final['boot_id']==e['boot_id'] and final['kernel']=='6.8.12-a10irq2'
    assert final['old_manager_absent'] and final['old_wrapper_absent'] and not final['active_lease']
    assert not any(final['locks'].values()) and final['ZOCL_absent'] and final['GDM_active']
    assert final['lease_sha256']==e['lease_sha256'] and final['kernel_gate']['allowed']
    delayed=json.loads((OUT/'final_check_01/stdout.txt').read_text(encoding='utf-8'))
    assert delayed['status']=='PASS_DELAYED_FINAL_CHECK_ALL_OLD_AND_RECOVERY_PROCESSES_ABSENT'
    assert all(delayed['known_processes_absent'].values()) and not any(delayed['locks'].values())
    assert not delayed['active_lease'] and delayed['kernel_gate']['allowed'] and delayed['boot_id']==e['boot_id']
    assert result['old_manager_absent'] and not result['canonical_locks_held'] and not result['active_lease']
    assert result['new_computation']==result['hardware_operations']==0
    # Reproduce the future component exactly from the preserved base + generator.
    spec=importlib.util.spec_from_file_location('window_v2_recipe',ROOT/'platform/qwen35/a12/step07_finalize_window.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    original=ROOT/'platform/qwen35/a12/window.py';source,_=module.generated_source()
    current=ROOT/'platform/qwen35/a12/window_closeout_v2.py'
    assert current.read_text(encoding='utf-8')==source
    tested=json.loads((OUT/'WINDOW_V2_PC_FINAL.json').read_text(encoding='utf-8'))
    assert tested['tested_source_sha256']==sha(current) and tested['methods']==7 and tested['status'].startswith('PASS_')
    save(OUT/'WINDOW_V2_FINAL_DERIVATION.json',dict(original_sha256=sha(original),v2_sha256=sha(current),
        reproducible=True,PC=tested,
        BOARD='NOT_TESTED',active_board_bundle_modified=False))
    audit=dict(status='PASS_FINALIZE_ONLY_OLD_ABNORMAL_EXIT_PRESERVED',old_manager_exit=-9,old_workers_exit=[0,0],
        finalizer_exit_code=0,signals_sent=1,signal_method='PIDFD_SIGKILL_ONLY_AFTER_FULL_QUIESCENCE',
        old_manager_pid=27132,old_manager_start_ticks=2110722,
        default_PL_operating=True,GDM_active=True,ZOCL_absent=True,no_device_FD_VMA=True,
        canonical_locks_held=False,active_lease=False,lease_archive=final['lease_archive'],lease_sha256=e['lease_sha256'],
        new_computation=0,PL_or_driver_mutations=0,reboots=0,hardware_global_counter=None,
        future_window_v2='PASS_PC_7_METHODS_BOARD_NOT_TESTED',step07_overall='PARTIAL_SINGLE_PROJECTION_ONLY_MLP_NOT_TESTED',
        independent_kernel_gate=final['kernel_gate'],boot_id=final['boot_id'],
        delayed_known_processes_absent=delayed['known_processes_absent'],delayed_kernel_gate=delayed['kernel_gate'],
        elapsed_recovery_ms=(events[-1]['monotonic_ns']-events[0]['monotonic_ns'])/1e6,
        failures_preserved=['Step07 initial finalization FAIL','Step06 cross-ISA graph FAIL','Step06 first full-range capacity FAIL'])
    save(OUT/'AUDIT.json',audit)
    print(json.dumps(audit))


if __name__=='__main__':main()
