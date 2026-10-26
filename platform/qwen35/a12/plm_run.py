"""Run a bounded synthetic control window through actual backend DSOs and manager."""
import argparse
import os
from pathlib import Path
import time
from plm_evidence import OUT,WORK,read,save,sha,pin,ROOT
from plm_manager import Manager

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);p.add_argument('--cap',type=int,choices=[1,72],default=72)
    p.add_argument('--fault',choices=['begin_fsync','grant_fsync','end_fsync','receipt_fsync','grant_slow','end_slow','request_digest','legacy_replay','revoke_claim','nan_y','start','timeout','premature_unload','cached_T','reuse_generation']);a=p.parse_args()
    assert a.tag.replace('-','').isalnum() and len(a.tag)<48;os.umask(0o077)
    build=OUT/f'BUILD-v{a.revision}.json';work=Path(read(build)['workspace']);directory=work/('run-'+a.tag);mirror=OUT/a.tag;mirror.mkdir()
    sources=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith('plm_')]
    save(mirror/'LAUNCH.json',dict(build_sha256=sha(build),source=sources,cap=a.cap,fault=a.fault,BOARD='NOT_TESTED'))
    m=Manager.__new__(Manager);started=time.monotonic();unexpected=False
    try:
        m.__init__(build,directory,cap=a.cap,fault=a.fault)
        m.ready()
        for i in range(3):m.run_request(i,native_fault=a.fault if a.fault in ('revoke_claim','nan_y','start','timeout','premature_unload','cached_T','reuse_generation') else None)
        result=m.normal_close();unexpected=bool(a.fault)
    except BaseException as exc:
        result=m.failed_observation(type(exc).__name__+': '+str(exc))
        unexpected=not a.fault or not(result['control_results']==0 and result['dirty_marker_retained'] and result['page']['revoked'] and
            result['writer_FD_retained'] and not result['release_allowed'] and not result['replay_allowed'])
    result.update(elapsed_s=time.monotonic()-started,measurement_scope='CONTROL_HARNESS_ONLY_NOT_LATENCY_BENCHMARK',private_directory=str(directory),
        last_native_message=getattr(m,'last_native',None))
    save(mirror/'RESULT.json',result)
    # Small bounded control originals only. No weights/diagnostic model originals.
    import shutil
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            target=mirror/path.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    print(result['status'],a.tag,flush=True)
    if unexpected:raise SystemExit(1)
if __name__=='__main__':main()
