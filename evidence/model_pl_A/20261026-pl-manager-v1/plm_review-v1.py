"""Current-source / ELF / regression / abrupt-owner proof audit, not Board acceptance."""
import re
import subprocess
from pathlib import Path
from plm_evidence import ROOT,OUT,PARENT,read,save,sha,pin
from plm_derive import generate
from plm_audit import audit_window

def main():
    text,_=generate();norm=read(OUT/'BUILD-v4.json');san=read(OUT/'BUILD-v5.json')
    w=Path(norm['workspace']);sw=Path(san['workspace']);assert text==(w/'source/backend.cpp').read_text()==(sw/'source/backend.cpp').read_text()
    runtime=['plm_manager.py','plm_page.py','plm_journal.py','plm_run.py']
    for tag in ('final-normal','final-san'):
        launch=read(OUT/tag/'LAUNCH.json');pins={r['path']:r['sha256'] for r in launch['source']}
        for name in runtime:assert pins['platform/qwen35/a12/'+name]==sha(ROOT/'platform/qwen35/a12'/name)
        assert audit_window(tag)['status']=='COMPLETE_CONTROL_WINDOW'
    for revision,build in ((4,norm),(5,san)):
        src=Path(build['workspace'])/'source';snapshot=read(OUT/f'SNAPSHOT-v{revision}.json')
        for row in snapshot['source']:assert sha(src/row['name'])==row['sha256']
        for row in build['artifacts']+build['ARM_artifacts']:assert sha(row['path'])==row['sha256']
        for p in src.iterdir():
            if p.is_file() and (p.name.startswith('plm_')):assert sha(p)==sha(ROOT/'platform/qwen35/a12'/p.name)
        for prefix in ('BACKEND','ROUTER','WRITER','PROBE','OBSERVER'):
            r=read(OUT/f'{prefix}_BUILD-v{revision}.json');assert r['exit_code']==0 and r['stderr']==''
        script=(Path(build['workspace'])/'build-arm.sh').read_text();assert '-mcpu=cortex-a53' in script and '-march=native' not in script and 'SP_LINEAR_CONTROL_TEST' not in script
        arm=read(OUT/f'ARM_BUILD-v{revision}.json');assert arm['exit_code']==0 and 'AArch64' in arm['stdout'] and 'libatomic' not in arm['stdout']
    def output(argv):
        r=subprocess.run(argv,capture_output=True,text=True);assert r.returncode==0,r.stderr
        return dict(command=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
    exports=output(['nm','-D','--defined-only',norm['observer_library']]);names={line.split()[-1] for line in exports['stdout'].splitlines()}
    assert names=={'a12_plm_observe_fd_v1'},names
    public=output(['nm','-D','--defined-only',str(w/'libplm_a53_unbound.so')]);names={line.split()[-1].split('@@')[0] for line in public['stdout'].splitlines()}
    assert names=={'SP_LINEAR_V1','sp_linear_open_v1','sp_linear_load_v1','sp_linear_run_v1','sp_linear_report_v1','sp_linear_unload_v1','sp_linear_close_v1','sp_a12_completion_report_v1'}
    for suite in ('suite02','san01'):
        result=read(OUT/(suite+'-AUDIT.json'));assert result['status']=='PASS_INDEPENDENT_CONTROL_JOURNALS_META_AND_RECEIPTS' and len(result['windows'])==17
        for name in read(OUT/(suite+'-SUITE.json'))['windows']:
            stderr=(OUT/name/'worker.stderr').read_text();assert 'ERROR: AddressSanitizer' not in stderr and 'runtime error:' not in stderr and 'UndefinedBehaviorSanitizer' not in stderr
    abrupt=read(OUT/'abrupt01/RESULT.json');assert abrupt['status']=='PASS_ACTUAL_PC_MANAGER_EXIT_CACHED_GRANT_QUARANTINE'
    assert abrupt['manager_pidfd_terminal'] and abrupt['native_pidfd_terminal'] and abrupt['lock_remained_blocked_while_native_live']
    assert abrupt['final']['claims']==5 and abrupt['final']['unknown_io'] and abrupt['final']['revoked'] and abrupt['native_failed_packet']['inventory']['stub_starts']==4
    unit=read(OUT/'UNIT_POLICY_RESULT-v2.json');assert unit['status']=='PASS' and unit['tests']==11
    counter=read(OUT/'CACHED_T_COUNTEREXAMPLE.json');assert counter['status']=='CONFIRMED_V2_COUNTEREXAMPLE_AND_V4_REJECTION' and counter['original_test_exit_code']==1
    assert read(OUT/'normal-01/RESULT.json')['page']['claims']==0 and 'thread bound' in read(OUT/'normal-01/RESULT.json')['reason']
    assert "name 'lane' is not defined" in read(OUT/'normal-02/RESULT.json')['reason']
    # Preserve all previous source identities and the unchanged original probe.
    for row in read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']:
        assert sha(ROOT/row['path'])==row['sha256']
    assert sha(ROOT/'evidence/model_pl_A/20261025-resource-probe-v1/bundle-v2.zip')=='acd578ddd66140a3d0507d71ea9a1d30245c632c7537f0a940227935cc17a7fa'
    comparison={}
    for tag in ('suite02-strict','suite02-batch','final-normal','final-san'):
        r=read(OUT/tag/'RESULT.json');comparison[tag]={k:r[k] for k in ('claims','private_messages','legacy_sequences','journal_records','journal_bytes','boundary_journal_read_bytes','boundary_artifact_read_bytes')}
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_PLM_PC_PROTOCOL_AND_A53_COMPILE_ONLY',
        current_source_matches_final_windows=True,ordinary_control_cases=17,sanitized_control_cases=17,additional_final_windows=2,
        policy_tests=11,abrupt_owned_manager_death=1,actual_model_windows=0,actual_FPGA_calls=None,
        cached_T_counterexample_retained=True,observer_exports=exports,ARM_public_exports=public,comparison=comparison,
        ARM_execution='NOT_EXECUTED',board_device_generation_approval='UNBOUND',actual_Qwen_router_request_hooks='NOT_IMPLEMENTED',
        actual_Board_health_and_lease_binding='NOT_IMPLEMENTED',PL_mode_coordinator='NOT_IMPLEMENTED',
        clinical_answers_delivered=0,BOARD='NOT_TESTED',production_enabled=False,release_allowed=False,replay_allowed=False,hardware_latency_saving_s=None))
    print('PASS_PLM_PC_PROTOCOL_AND_A53_COMPILE_ONLY')
if __name__=='__main__':main()
