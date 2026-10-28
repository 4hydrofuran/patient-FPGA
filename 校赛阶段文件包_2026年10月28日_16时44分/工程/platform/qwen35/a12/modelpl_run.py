"""Authentic Qwen R0/warm/hit through real frontend/Route and CPU-only PLM adapter."""
import argparse
import os
from pathlib import Path
import shutil
import time
from modelpl_evidence import ROOT,OUT,read,save,sha,pin
from modelpl_manager import ModelManager

def expected_fault(fault,result,directory):
    page=result['page'];native=result.get('last_native_message') or {};reason=result['reason'];claims=page['claims']
    common=(result['control_results']==0 and page['revoked'] and result['dirty_marker_retained'] and result['writer_FD_retained'] and
        result['owned_pidfd_terminal'] and result['all_threads_stopped'] and result['worker_exit_code']==2)
    if fault in ('begin_fsync','grant_fsync','end_fsync'):
        event={'begin_fsync':'BEGIN','grant_fsync':'GRANT','end_fsync':'END'}[fault]
        correct=(claims==(1440 if fault=='end_fsync' else 0) and 'injected complete-record fsync failure' in reason and
            ('"event":"'+event+'"').encode() in (directory/'state/control.jsonl').read_bytes())
    elif fault=='receipt_fsync':correct=claims==1440 and 'injected receipt fsync failure' in reason and (directory/'state/app_R0-receipt.json').is_file()
    elif fault in ('grant_slow','end_slow'):correct=claims==(1440 if fault=='end_slow' else 0) and 'foreign/reused/stale health ticket' in reason
    elif fault=='request_digest':correct=claims==0 and native.get('type')=='error' and native.get('id')=='tampered-native-id' and 'private request bind failed' in native.get('message','')
    elif fault in ('drop_copy','cached_revoke'):
        route=native.get('private_CPU_report',{}).get('a12_route',{});private=native.get('private_control',{})
        if fault=='drop_copy':correct=(claims==1 and route.get('cpu_run_count')==1 and private.get('copy_checks')==0 and native.get('model_bridge_error')=='private graph copy differs')
        else:correct=(claims==5 and page['unknown_io'] and 'PC cached fifth-claim revoke fixture' in reason and
            route.get('pc_started_calls')==route.get('cpu_run_count')==route.get('pc_verified_completions')==4 and
            route.get('pc_attempted_calls')==5 and private.get('copy_checks')==4)
        correct=correct and route.get('pc_poisoned') is True and route.get('pc_output_consumable') is False
    else:correct=False
    return dict(intended_fault_verified=bool(common and correct),common_failure_fences=bool(common),specific_target_verified=bool(correct),scope='THIS_FAULT_ONLY_NO_EARLY_FAILURE_SUBSTITUTION')

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);p.add_argument('--cap',type=int,choices=[1,72],default=72)
    p.add_argument('--fault',choices=['begin_fsync','grant_fsync','end_fsync','receipt_fsync','grant_slow','end_slow','request_digest','drop_copy','cached_revoke']);a=p.parse_args()
    assert a.tag.replace('-','').isalnum() and len(a.tag)<48;os.umask(0o077);build=OUT/f'BUILD-v{a.revision}.json';b=read(build)
    mirror=OUT/a.tag;mirror.mkdir();directory=Path(b['workspace'])/('run-'+a.tag)
    save(mirror/'LAUNCH.json',dict(source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith('modelpl_')],
        build_sha256=sha(build),cap=a.cap,fault=a.fault,BOARD='NOT_TESTED',actual_CPU_model=True,actual_FPGA_calls=None))
    m=ModelManager.__new__(ModelManager);start=time.monotonic();unexpected=False
    try:
        m.__init__(build,directory,cap=a.cap,fault=a.fault);m.ready()
        for index in range(3):m.run_request(index)
        result=m.normal_close();unexpected=bool(a.fault)
    except BaseException as exc:
        result=m.failed_observation(type(exc).__name__+': '+str(exc));unexpected=not bool(a.fault)
        if a.fault:
            result['last_native_message']=getattr(m,'last_native',None);result['fault_expectation']=expected_fault(a.fault,result,directory)
            unexpected=not result['fault_expectation']['intended_fault_verified']
    result.update(elapsed_s=time.monotonic()-start,private_directory=str(directory),last_native_message=getattr(m,'last_native',None),
        verification_layer='ACTUAL_QWEN_CPU_MATH_ROUTE_PRIVATE_PROTOCOL_NOT_BOARD',real_PL_results_consumed=False)
    save(mirror/'RESULT.json',result)
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            target=mirror/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    print(result['status'],a.tag,flush=True)
    if unexpected:raise SystemExit(1)
if __name__=='__main__':main()
