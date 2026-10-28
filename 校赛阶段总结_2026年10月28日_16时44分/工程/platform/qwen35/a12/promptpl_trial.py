"""Serial private-protocol actual CPU model windows; never Board operations."""
import argparse
import os
from pathlib import Path
import re
import select
import shutil
import time
from promptpl_evidence import ROOT,OUT,WORK,read,save,sha,pin
from promptpl_manager import Manager
from livegen_binding import ReadOnlyPage

def terminal(fd):
    poll=select.poll();poll.register(fd,select.POLLIN);return bool(poll.poll(0))

def one(suite,item,cap,fault):
    folder=OUT/suite/(item['id']+'-cap'+str(cap));folder.mkdir(parents=True);build=read(item['build_path'])
    directory=WORK/(suite+'-'+item['id']+'-cap'+str(cap))
    save(folder/'LAUNCH.json',dict(build_path=item['build_path'],build_sha256=sha(item['build_path']),cap=cap,fault=fault,
        source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith('promptpl_')],BOARD='NOT_TESTED'))
    m=Manager.__new__(Manager);m.page=None;m.p=None;m.fault=None;held=None;observer=None;error=None;started=time.monotonic()
    try:
        m.__init__(item['build_path'],directory,cap=cap,fault=fault)
        held=os.dup(m.pidfd);observer=ReadOnlyPage(m.page,build['observer_library'],build['observer_sha256'])
        m.ready()
        for i in range(3):m.run_request(i)
        result=m.normal_close();assert fault is None,'fault injection did not reject this window'
    except BaseException as exc:
        error=type(exc).__name__+': '+str(exc)
        result=m.failed_observation(error) if getattr(m,'monitor',None) is not None else dict(status='FAILED_BEFORE_NATIVE_MONITOR',reason=error,BOARD='NOT_TESTED')
    done=held is not None and terminal(held)
    page=observer() if observer is not None else None
    result.update(suite=suite,cohort_id=item['id'],cap=cap,injection=fault,error=error,private_directory=str(directory),
        owned_native_pid=m.p.pid if m.p else None,independent_pidfd_terminal=done,independent_page=page,
        elapsed_window_s=time.monotonic()-started,model_result_files=len(list(directory.glob('*-MODEL_RESULT.json'))),
        real_PL_results_consumed=False,BOARD='NOT_TESTED',release_allowed=False,replay_allowed=False)
    # Copy only after verified terminal; a timeout is not a completed experiment.
    if m.p is not None and not done:
        save(folder/'LIVE_WAIT.json',result);print('LIVE_WAIT',suite,item['id'],m.p.pid,flush=True)
        raise RuntimeError('owned native remains live; do not restart this window')
    for p in directory.rglob('*'):
        if p.is_file():
            target=folder/p.relative_to(directory);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    save(folder/'RESULT.json',result)
    if observer is not None:observer.close()
    if held is not None:os.close(held)
    expected=(error is None) if fault is None else bool(error and result.get('worker_exit_code')==2 and result['model_result_files']==0 and
        page and page['revoked'] and (directory/'state/DIRTY.json').exists())
    print('WINDOW',item['id'],cap,'EXPECTED' if expected else 'UNEXPECTED',result.get('claims',page['claims'] if page else None),flush=True)
    if not expected:raise RuntimeError('unexpected private prompt window result: '+str(error))
    return dict(id=item['id'],cap=cap,folder=folder.relative_to(OUT).as_posix(),status=result['status'],injection=fault)

def main():
    p=argparse.ArgumentParser();p.add_argument('--suite',required=True);p.add_argument('--ids',default='all');p.add_argument('--caps',default='72')
    p.add_argument('--fault',choices=['begin_fsync','grant_fsync','end_fsync','receipt_fsync','end_slow','request_digest','same_uuid_reload','drop_copy'])
    a=p.parse_args();assert re.fullmatch('[a-z0-9-]{1,40}',a.suite);os.umask(0o077)
    items=read(OUT/'COHORTS.json')['cohorts'];ids=None if a.ids=='all' else a.ids.split(',');items=[r for r in items if ids is None or r['id'] in ids]
    assert items and (ids is None or {r['id'] for r in items}==set(ids));caps=[int(s) for s in a.caps.split(',')];assert caps and set(caps)<={1,72} and len(set(caps))==len(caps)
    (OUT/a.suite).mkdir();results=[]
    for i,item in enumerate(items):
        for cap in caps if i%2==0 else list(reversed(caps)):results.append(one(a.suite,item,cap,a.fault))
    save(OUT/(a.suite+'-SUITE.json'),dict(status='COMPLETED_ACTUAL_CPU_PRIVATE_PROMPT_WINDOWS',windows=results,BOARD='NOT_TESTED',real_PL_results_consumed=False))
    print('COMPLETED_ACTUAL_CPU_PRIVATE_PROMPT_WINDOWS',len(results),flush=True)
if __name__=='__main__':main()
