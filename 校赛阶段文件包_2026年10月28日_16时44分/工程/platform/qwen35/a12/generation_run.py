"""Exercise the actual frozen Qwen front/Route and the new native consumer."""
import argparse
import os
from pathlib import Path
import shutil
import time
from generation_evidence import ROOT,OUT,read,save,sha,pin
from generation_manager import GenerationManager
from modelpl_run import expected_fault

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True)
    p.add_argument('--cap',type=int,choices=[1,72],default=72)
    p.add_argument('--fault',choices=['generation_mutate','generation_slot_stale','begin_fsync','drop_copy']);a=p.parse_args()
    assert a.tag.replace('-','').isalnum() and len(a.tag)<48;os.umask(0o077)
    build=OUT/f'BUILD-v{a.revision}.json';b=read(build);mirror=OUT/a.tag;mirror.mkdir();directory=Path(b['workspace'])/('run-'+a.tag)
    save(mirror/'LAUNCH.json',dict(build_sha256=sha(build),cap=a.cap,fault=a.fault,
        source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('generation_','test_generation_'))],
        BOARD='NOT_TESTED',actual_CPU_model=True,actual_FPGA_calls=None))
    m=GenerationManager.__new__(GenerationManager);started=time.monotonic();unexpected=False
    try:
        m.__init__(build,directory,cap=a.cap,fault=a.fault);m.ready()
        for index in range(3):m.run_request(index)
        result=m.normal_close();unexpected=bool(a.fault)
    except BaseException as exc:
        result=m.failed_observation(type(exc).__name__+': '+str(exc));unexpected=not bool(a.fault)
        result['last_native_message']=getattr(m,'last_native',None)
        if a.fault in ('generation_mutate','generation_slot_stale'):
            native=getattr(m,'last_native',None) or {};route=native.get('private_CPU_report',{}).get('a12_route',{});page=result['page']
            common=(result['control_results']==0 and page['revoked'] and page['unknown_io'] and result['dirty_marker_retained'] and
                result['writer_FD_retained'] and result['owned_pidfd_terminal'] and result['all_threads_stopped'] and result['worker_exit_code']==2)
            target=(m.issuer.blocked and 'file metadata/identity changed' in result['reason']) if a.fault=='generation_mutate' else (
                page['start_intent'] and route.get('pc_plm',{}).get('generation_consumer',{}).get('PC_test_original_start_committed') is True and
                route.get('pc_plm',{}).get('generation_consumer',{}).get('healthy_ns')==0)
            exact=(page['claims']==5 and target and len(m.issuer.locks)==2 and
                route.get('pc_started_calls')==route.get('cpu_run_count')==route.get('pc_verified_completions')==4 and route.get('pc_attempted_calls')==5 and
                native.get('private_control',{}).get('copy_checks')==4 and route.get('pc_poisoned') is True and route.get('pc_output_consumable') is False)
            result['fault_expectation']=dict(intended_fault_verified=bool(common and exact),common_failure_fences=bool(common),specific_target_verified=bool(exact))
            unexpected=not result['fault_expectation']['intended_fault_verified']
        elif a.fault:
            result['fault_expectation']=expected_fault(a.fault,result,directory);unexpected=not result['fault_expectation']['intended_fault_verified']
    result.update(elapsed_s=time.monotonic()-started,private_directory=str(directory),last_native_message=getattr(m,'last_native',None),
        verification_layer='PC_ACTUAL_QWEN_GENERATION_CONSUMER',real_PL_results_consumed=False,Board_generation_approval=False)
    save(mirror/'RESULT.json',result)
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            target=mirror/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    print(result['status'],a.tag,flush=True)
    if unexpected:raise SystemExit(1)
if __name__=='__main__':main()
