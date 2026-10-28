"""Replay existing complete PC diagnostic bytes through export and offline verifier.

Never runs a model, reads a board or resumes the paused CMA candidate.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import time
from offline_diag_handoff import export_pc, verify_archive, manifest_plan, need, CHUNK
from tt10_01_numeric import concatenated

ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'evidence/model_pl_A/20261024-ttft10-01-v1/pc-run-04/pc-new'


def dump(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    os.umask(0o077)
    args.evidence.mkdir(parents=True,exist_ok=False)
    args.work.mkdir(parents=True,exist_ok=False,mode=0o700)
    old={'full':'full_R0','warm':'warm_70','hit':'full_cache_70'}
    plans={};total=0
    for case,previous in old.items():
        source=SOURCE/previous/'diag'
        raw=(source/'manifest.json').read_bytes()
        manifest,allowed=manifest_plan(raw)
        allowed['hybrid-state.bin']=(source/'hybrid-state.bin').stat().st_size
        need(set(p.name for p in source.iterdir())==set(allowed),'original PC diagnostic inventory differs')
        plans[case]=(source,allowed)
        total+=sum(allowed.values())
    need(shutil.disk_usage(args.work).free>=3*total+1024**3,'insufficient PC replay disk headroom')
    copied={};paths={};start=time.monotonic_ns()
    try:
        for case,(source,allowed) in plans.items():
            target=args.work/case/'diag';target.mkdir(parents=True,mode=0o700)
            paths[case]=target
            for name,size in allowed.items():
                src=source/name;dst=target/name
                need(src.is_file() and not src.is_symlink(),'original must be a regular non-symlink file')
                before=src.stat();h=hashlib.sha256();count=0
                with src.open('rb') as f,dst.open('xb') as g:
                    for block in iter(lambda:f.read(CHUNK),b''):
                        g.write(block);h.update(block);count+=len(block)
                after=src.stat()
                need(count==size and (before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns)==
                     (after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns),'source changed while copying')
                dst.chmod(0o600)
                copied[case+'/'+name]=dict(bytes=count,sha256=h.hexdigest())
            print(json.dumps(dict(event='PC_COPY_COMPLETE',case=case,files=len(allowed))),flush=True)
        golden=concatenated(args.work/'full',args.work/'warm',args.work/'hit')
        need(golden['equal'],'existing raw originals not numerically equal')
        dump(args.evidence/'REFERENCE.json',golden)
        archive=args.work/'full-diagnostics.zip'
        exported=export_pc(paths,archive)
        dump(args.evidence/'EXPORT.json',exported)
        print(json.dumps(dict(event='PC_EXPORT_COMPLETE',raw_bytes=exported['raw_bytes'],archive_bytes=exported['archive_bytes'])),flush=True)
        verified=verify_archive(archive,exported['archive_sha256'])
        need(verified['comparison']==golden,'new verifier differs from unchanged legacy full-byte comparator')
        with __import__('zipfile').ZipFile(archive) as z:
            index=json.loads(z.read('HANDOFF.json'))
            need(index['files']==copied,'archive raw inventory/digests differ from originals')
        result=dict(status='PASS_ACTUAL_PC_FULL_RAW_HANDOFF_AND_COMPARISON',
            original_source=str(SOURCE),private_PC_copy=str(args.work),archive=str(archive),
            raw_files=len(copied),raw_bytes=total,archive_bytes=exported['archive_bytes'],
            archive_sha256=exported['archive_sha256'],source_read_passes_during_export=1,
            decompressed_read_passes_during_verification=1,all_legacy_comparison_fields_equal=True,
            full_original_file_digests_equal=True,original_source_files_modified=False,
            peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            elapsed_PC_s=(time.monotonic_ns()-start)/1e9,
            BOARD='NOT_TESTED',board_CMA_recovery='NOT_TESTED',model_runs=0,PL_calls=0,
            paused_CMA_candidate_imported_or_resumed=False,board_export_binding='NOT_IMPLEMENTED_UNAUTHORIZED')
        dump(args.evidence/'SOURCE_FILES.json',copied);dump(args.evidence/'VERIFIED.json',verified)
        dump(args.evidence/'RESULT.json',result)
        print(json.dumps(result,indent=2))
    except BaseException as exc:
        dump(args.evidence/'FAILURE.json',dict(status='FAIL_RETAINED',reason=type(exc).__name__+': '+str(exc),
            independent_partial_work=str(args.work),source_modified=False,BOARD='NOT_TESTED',model_runs=0,retry=False))
        raise


if __name__=='__main__':main()
