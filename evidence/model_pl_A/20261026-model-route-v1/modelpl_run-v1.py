"""Authentic Qwen R0/warm/hit through real frontend/Route and CPU-only PLM adapter."""
import argparse
import os
from pathlib import Path
import shutil
import time
from modelpl_evidence import ROOT,OUT,read,save,sha,pin
from modelpl_manager import ModelManager

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
        if a.fault:unexpected=not(result['control_results']==0 and result['page']['revoked'] and result['dirty_marker_retained'] and result['writer_FD_retained'])
    result.update(elapsed_s=time.monotonic()-start,private_directory=str(directory),last_native_message=getattr(m,'last_native',None),
        verification_layer='ACTUAL_QWEN_CPU_MATH_ROUTE_PRIVATE_PROTOCOL_NOT_BOARD',real_PL_results_consumed=False)
    save(mirror/'RESULT.json',result)
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            target=mirror/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    print(result['status'],a.tag,flush=True)
    if unexpected:raise SystemExit(1)
if __name__=='__main__':main()
