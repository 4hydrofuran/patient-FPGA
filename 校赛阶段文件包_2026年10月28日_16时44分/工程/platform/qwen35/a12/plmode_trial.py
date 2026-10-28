"""Serial bounded actual CPU model/mode experiment with current raw evidence."""
import argparse
import os
from pathlib import Path
import shutil
import time
from plmode_evidence import ROOT,OUT,read,save,sha,pin
from plmode_coordinator import Coordinator

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',required=True,type=int);p.add_argument('--tag',required=True)
    p.add_argument('--scenario',choices=['normal','fallback','begin_fsync'],default='normal');a=p.parse_args()
    assert a.tag.replace('-','').isalnum();os.umask(0o077);build=OUT/f'BUILD-v{a.revision}.json';b=read(build);folder=OUT/a.tag;folder.mkdir()
    state=Path(b['workspace'])/('mode-'+a.tag);state.mkdir(mode=0o700)
    save(folder/'LAUNCH.json',dict(build_sha256=sha(build),scenario=a.scenario,
        source=[pin(p) for p in sorted((ROOT/'platform/qwen35/a12').iterdir()) if p.is_file() and p.name.startswith(('plmode_','test_plmode_'))],BOARD='NOT_TESTED'))
    c=Coordinator(state/'history',build,trusted_candidate=True);windows=[];refusals=[];started=time.monotonic();error=None
    try:
        before_windows={p.name for p in Path(b['workspace']).glob('window-*')}
        if a.scenario=='begin_fsync':c.journal.inject_event='WINDOW_BEGIN'
        else:c.switch('BATCH_CANDIDATE')
        try:
            c.start('first-'+a.tag,fault='same_uuid_reload' if a.scenario=='fallback' else None)
            entry=c.active;windows.append(entry)
            try:c.switch('STRICT_CONTROL')
            except RuntimeError as e:refusals.append(str(e))
            else:raise AssertionError('mode switched during an active window')
            for _ in range(3):c.request_next()
            c.finish_native()
        except BaseException as exc:
            if a.scenario=='normal':raise
            if a.scenario=='begin_fsync':
                assert 'injected mode complete-record fsync failure' in str(exc) and c.journal.blocked and c.active is None
                assert {p.name for p in Path(b['workspace']).glob('window-*')}==before_windows
            else:
                assert c.phase=='FAILED_DRAINED_PC' and c.disabled and c.active is entry
                m=entry['manager'];page=entry['page']();assert page['claims']==5 and page['unknown_io'] and page['revoked'] and m.p.returncode==2
                assert 'generation node replaced/unloaded' in m.fault and len(m.control_results)==0
                try:c.fallback_for_new_input('first-'+a.tag)
                except RuntimeError as e:refusals.append(str(e))
                else:raise AssertionError('old input replayed')
                c.fallback_for_new_input('new-'+a.tag)
                assert c.mode=='STRICT_CONTROL' and c.retained[0]['page']()['unknown_io']
                try:c.switch('BATCH_CANDIDATE')
                except RuntimeError as e:refusals.append(str(e))
                else:raise AssertionError('fault-latched candidate reenabled')
                c.start('new-'+a.tag);windows.append(c.active)
                for _ in range(3):c.request_next()
                c.finish_native();assert c.retained[0]['page']()['claims']==5 and c.retained[0]['page']()['unknown_io']
        if a.scenario!='begin_fsync':c.close()
    except BaseException as exc:error=type(exc).__name__+': '+str(exc)
    observed=[]
    for i,entry in enumerate(windows):
        m=entry['manager'];target=folder/('window-'+str(i));target.mkdir()
        for path in m.directory.rglob('*'):
            if path.is_file():
                t=target/path.relative_to(m.directory);t.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,t)
        observed.append(dict(directory=str(m.directory),mirror='window-'+str(i),cap=m.cap,closed=m.closed,
            native_pid=m.p.pid,worker_exit_code=m.p.returncode,claims=m.claims,completed=m.completed,
            page=entry['proof']['page'] if entry.get('proof') else None,model_results=len(m.control_results),source_revoked=m.source.blocked,
            last_native_message=getattr(m,'last_native',None),reason=m.fault,private_messages=m.private_sequence,legacy_sequences=m.legacy_sequences,
            all_threads_stopped=all(not t.is_alive() for t in m.threads),writer_FD_retained=m.page.fd is not None,
            dirty_marker_retained=(m.directory/'state/DIRTY.json').exists()))
    shutil.copytree(state/'history',folder/'history')
    save(folder/'RESULT.json',dict(status='PASS_PC_MODE_SCENARIO' if error is None else 'FAILED_PC_MODE_SCENARIO',error=error,scenario=a.scenario,
        phase=c.phase,windows=observed,refusals=refusals,candidate_disabled=c.disabled,elapsed_s=time.monotonic()-started,
        owning_manager_pid=os.getpid(),retained_failed_PC_authorities=len(c.retained),BOARD='NOT_TESTED',actual_PL_results_consumed=False,
        private_state=str(state)))
    print('PASS_PC_MODE_SCENARIO' if error is None else error,flush=True)
    if error:raise SystemExit(1)
if __name__=='__main__':main()
