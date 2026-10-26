"""Verify actual frontend source, reused mathematics, private ABI and scoped evidence."""
import subprocess
from pathlib import Path
from modelpl_evidence import ROOT,OUT,PARENT,read,save,sha
from modelpl_derive import runtime,cpu
from modelpl_audit import audit

def main():
    build=read(OUT/'BUILD-v5.json');work=Path(build['workspace']);src=work/'source';actual,changes=runtime();adapter,_=cpu()
    for name,text in actual.items():assert (src/name).read_text()==text
    assert (src/'modelpl_cpu.cpp').read_text()==adapter
    for row in build['source']:assert sha(src/row['name'])==row['sha256']
    for row in build['runtime_artifacts']:assert sha(row['path'])==row['sha256']
    for row in build['math_libraries_before_and_after']:assert sha(row['path'])==row['sha256']
    quant=build['imported_quant_object'];assert sha(quant['path'])==quant['sha256']
    link=(work/'pc/CMakeFiles/qwen35-a12.dir/link.txt').read_text();assert quant['path'] in link
    assert not list((work/'pc/CMakeFiles').rglob('w4a8.cpp.o')) and not build['math_DSO_recompiled'] and not build['quant_math_recompiled']
    arm=read(OUT/'ARM_BUILD-v5.json');assert arm['status']=='PASS_A53_NATIVE_FRONT_ROUTE_AND_PRIVATE_BACKEND_COMPILE_ONLY'
    for row in arm['artifacts']+arm['original_math_before_and_after']:assert sha(row['path'])==row['sha256']
    armflags=(work/'arm/CMakeFiles/qwen35-a12.dir/flags.make').read_text();assert 'SP_A12_PC_TEST' not in armflags and '-mcpu=cortex-a53' in armflags and '-march=native' not in armflags
    armlink=(work/'arm/CMakeFiles/qwen35-a12.dir/link.txt').read_text();assert arm['original_math_before_and_after'][0]['path'] in armlink
    backend=work/'arm-private-backend/backend.cpp';text=backend.read_text();assert 'return SP_UNSUPPORTED;\n#endif\n    a12::permit("device_open",0);' in text
    assert '(void)digest;return SP_UNSUPPORTED;' in text and 'sp_a12_plm_request_abort_v1' in text
    def capture(argv):
        r=subprocess.run(argv,capture_output=True,text=True);assert r.returncode==0,r.stderr
        return dict(command=argv,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
    symbols=capture(['nm','-D','--defined-only',str(work/'liba12_modelpl_xrt_unbound.so')]);exports={line.split()[-1] for line in symbols['stdout'].splitlines()}
    public={'SP_LINEAR_V1','sp_linear_open_v1@@SP_LINEAR_V1','sp_linear_load_v1@@SP_LINEAR_V1','sp_linear_run_v1@@SP_LINEAR_V1',
        'sp_linear_report_v1@@SP_LINEAR_V1','sp_linear_unload_v1@@SP_LINEAR_V1','sp_linear_close_v1@@SP_LINEAR_V1','sp_a12_completion_report_v1@@SP_LINEAR_V1'}
    private={'A12_PLM_PRIVATE_V1','sp_a12_plm_request_v1@@A12_PLM_PRIVATE_V1','sp_a12_plm_request_end_v1@@A12_PLM_PRIVATE_V1','sp_a12_plm_request_abort_v1@@A12_PLM_PRIVATE_V1'}
    assert exports==public|private,exports
    elf=capture(['readelf','-h','-d',str(work/'arm/qwen35-a12')]);assert 'AArch64' in elf['stdout']
    cpu_symbols=capture(['nm','-D','--defined-only',build['adapter']]);names={s.split()[-1] for s in cpu_symbols['stdout'].splitlines() if s.split()[-1].startswith('sp_')}
    assert names=={'sp_linear_open_v1','sp_linear_load_v1','sp_linear_run_v1','sp_linear_report_v1','sp_linear_unload_v1','sp_linear_close_v1','sp_a12_completion_report_v1','sp_a12_plm_request_v1','sp_a12_plm_request_end_v1','sp_a12_plm_request_abort_v1'}
    audit_result=read(OUT/'model02-AUDIT.json');assert audit_result['status']=='PASS_ACTUAL_CPU_FRONT_ROUTE_ORDINARY_AND_SPECIFIC_FAILURE_GATES' and len(audit_result['windows'])==11
    perf=read(OUT/'PERF_PC_EXPLORATION.json');assert len(perf['samples'])==4
    for sample in perf['samples']:assert audit(sample['tag'])['status']=='ACCEPTED_PC_MODEL_ORDINARY_WINDOW'
    runtime_names=('modelpl_manager.py','modelpl_run.py')
    for tag in ['model02-strict','model02-batch']+[s['tag'] for s in perf['samples']]:
        launch={r['path']:r['sha256'] for r in read(OUT/tag/'LAUNCH.json')['source']}
        for name in runtime_names:assert launch['platform/qwen35/a12/'+name]==sha(ROOT/'platform/qwen35/a12'/name)
    owner=read(OUT/'OWNER_CONCURRENCY_RESULT.json');assert owner['new_poll_errors']==0 and owner['previous_shared_poll_errors']>0 and owner['same_held_pidfd'] and not owner['PID_reopened'] and owner['terminal_refused']
    assert read(OUT/'DEVELOPMENT_SUITE_REJECTION.json')['status']=='NOT_ACCEPTED_CACHED_REVOKE_TARGET_NOT_REACHED'
    assert read(OUT/'model01-cached-revoke/RESULT.json')['page']['claims']==0
    fixed=read(OUT/'model02-cached-revoke/RESULT.json');assert fixed['page']['claims']==5 and fixed['fault_expectation']['intended_fault_verified'] and fixed['page']['unknown_io']
    assert read(OUT/'PC_ADAPTER_BUILD-v1.json')['exit_code']!=0 and 'openssl/evp.h' in read(OUT/'PC_ADAPTER_BUILD-v1.json')['stderr']
    for row in read(PARENT/'PRESERVATION.json')['old_source_pins']+read(PARENT/'FINAL_REVIEW.json')['source']:assert sha(ROOT/row['path'])==row['sha256']
    save(OUT/'ARTIFACT_REVIEW.json',dict(status='PASS_ACTUAL_MODEL_PRIVATE_HOOKS_PC_AND_A53_COMPILE_ONLY',
        actual_current_source_scenarios=11,normal_scenario_windows=2,targeted_failure_windows=9,additional_PC_exploration_windows=4,held_pidfd_concurrency_regression=True,
        math_DSO_and_quant_objects_reused_unchanged=True,all_final_source_native_outputs_and_logits_match_frozen_ordinary_CPU=True,
        runtime_reported_prefix_state_sequence_logits_digests_match=True,full_intermediate_state='NOT_TESTED',actual_PL_results_consumed=False,
        A53_private_ABI_exports=symbols,A53_native_ELF=elf,CPU_private_symbols=cpu_symbols,ARM_runtime='NOT_EXECUTED',
        real_device_generation_approval='UNBOUND',PL_mode_coordinator='NOT_IMPLEMENTED',BOARD='NOT_TESTED',production_enabled=False,
        ordinary_resource_probe_replaced=False,release_allowed=False,hardware_latency_saving_s=None))
    print('PASS_ACTUAL_MODEL_PRIVATE_HOOKS_PC_AND_A53_COMPILE_ONLY')
if __name__=='__main__':main()
