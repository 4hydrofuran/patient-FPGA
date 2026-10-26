"""Bounded actual CPU model windows with live-source binding, not Board approval."""
import argparse
import os
from pathlib import Path
import shutil
import time
from livegen_evidence import ROOT,OUT,read,save,sha,pin
from livegen_manager import Manager
from modelpl_run import expected_fault

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True,type=int);p.add_argument('--tag',required=True);p.add_argument('--cap',type=int,choices=[1,72],default=72)
    p.add_argument('--fault',choices=['same_uuid_reload','platform_mutation','begin_fsync']);a=p.parse_args()
    assert a.tag.replace('-','').isalnum() and len(a.tag)<48;os.umask(0o077);build=OUT/f'BUILD-v{a.revision}.json';b=read(build)
    folder=OUT/a.tag;folder.mkdir();directory=Path(b['workspace'])/('run-'+a.tag)
    save(folder/'LAUNCH.json',dict(cap=a.cap,fault=a.fault,build_sha256=sha(build),
        source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('livegen_','test_livegen_'))],
        BOARD='NOT_TESTED',actual_CPU_model=True,actual_FPGA_calls=None))
    m=Manager.__new__(Manager);started=time.monotonic();unexpected=False
    try:
        m.__init__(build,directory,cap=a.cap,fault=a.fault);m.ready()
        for i in range(3):m.run_request(i)
        result=m.normal_close();unexpected=bool(a.fault)
    except BaseException as exc:
        result=m.failed_observation(type(exc).__name__+': '+str(exc));result['last_native_message']=getattr(m,'last_native',None);unexpected=not bool(a.fault)
        if a.fault in ('same_uuid_reload','platform_mutation'):
            q=result['last_native_message'] or {};r=q.get('private_CPU_report',{}).get('a12_route',{});page=result['page'];source=m.binding_controller.source
            common=(page['revoked'] and page['unknown_io'] and page['claims']==5 and source.blocked and not source.normal_terminal and
                result['control_results']==0 and result['dirty_marker_retained'] and result['writer_FD_retained'] and result['owned_pidfd_terminal'] and
                result['all_threads_stopped'] and result['worker_exit_code']==2)
            counts=(r.get('pc_attempted_calls')==5 and r.get('pc_started_calls')==r.get('cpu_run_count')==r.get('pc_verified_completions')==4 and
                q.get('private_control',{}).get('copy_checks')==4 and r.get('pc_poisoned') is True and r.get('pc_output_consumable') is False)
            target=('generation node replaced/unloaded' in result['reason'] and m.registry.serial==0) if a.fault=='same_uuid_reload' else (
                'retains platform ownership' in result['reason'] and m.registry.serial==1 and not m.registry.retired and 'MUST_NOT_EXECUTE_RELEASE' not in result['reason'])
            result['fault_expectation']=dict(intended_fault_verified=bool(common and counts and target),common_failure_fences=bool(common),
                specific_target_verified=bool(counts and target));unexpected=not result['fault_expectation']['intended_fault_verified']
        elif a.fault:
            result['fault_expectation']=expected_fault(a.fault,result,directory);unexpected=not result['fault_expectation']['intended_fault_verified']
    source=getattr(m,'source',None);registry=getattr(m,'registry',None)
    result.update(source_mutation_serial=registry.serial if registry else None,source_revoked=source.blocked if source else None,
        source_normal_terminal=source.normal_terminal if source else None,
        elapsed_s=time.monotonic()-started,private_directory=str(directory),last_native_message=getattr(m,'last_native',None),
        verification_layer='PC_ACTUAL_QWEN_LIVE_SOURCE_FIXTURE_NATIVE_BINDING',real_PL_results_consumed=False,Board_generation_approval=False)
    save(folder/'RESULT.json',result)
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            target=folder/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    print(result['status'],a.tag,flush=True)
    if unexpected:raise SystemExit(1)
if __name__=='__main__':main()
