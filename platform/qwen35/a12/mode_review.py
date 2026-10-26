"""Audit private histories and every actual PC child; mirror small evidence."""
from pathlib import Path
import re
import shutil
from mode_evidence import ROOT,OUT,PARENT,WORK,read,save,sha,pin
from mode_journal import read_journal
from mode_history import validate_history
from microbatch_audit import audit

def review():
    cases=[];binding={}
    for name in ('transitions-01','cancel-01','transitions-02'):
        result=read(OUT/name/'RESULT.json');state=Path(result['state_directory'])
        rows=read_journal(state/'coordinator.jsonl');history=validate_history(rows,closed_required=True)
        assert not (state/'DIRTY.json').exists() and result['coordinator_closed'] and result['DIRTY_removed']
        for r in result['windows']:
            assert r['manager_pidfd_terminal'] and r['native_pidfd_terminal'] and r['page']['revoked']
            binding[r['tag']]=dict(case=name,window=r)
        target=OUT/'histories'/name;target.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(state/'coordinator.jsonl',target/'coordinator.jsonl')
        cases.append(dict(case=name,status='PASS_CLOSED_HISTORY_AND_LIVE_OBSERVATION_RECORDS',history=history,
            windows=len(result['windows']),refusals=len(result['refusals']),journal_sha256=sha(target/'coordinator.jsonl')))
    restart=read(OUT/'restart-01/RESULT.json');r=restart['ownership'];state=Path(r['state_directory'])
    assert restart['status']=='PASS_ACTUAL_ABRUPT_COORDINATOR_EXIT_NO_RESTART_OR_REPLAY'
    assert restart['live_handles_acquired'] and restart['manager_pidfd_terminal'] and restart['native_pidfd_terminal']
    assert restart['new_windows_launched_after_restart']==0 and restart['dirty_marker_retained']
    rows=read_journal(state/'coordinator.jsonl');history=validate_history(rows)
    assert history['session_open'] and history['active_window']==r['window_id'] and (state/'DIRTY.json').exists()
    target=OUT/'histories/restart-01';target.mkdir(parents=True,exist_ok=False)
    for name in ('coordinator.jsonl','DIRTY.json'):shutil.copyfile(state/name,target/name)
    binding[r['tag']]=dict(case='restart-01',window=None)
    cases.append(dict(case='restart-01',status='PASS_UNCLEAN_RESTART_REFUSED_NOT_RECOVERED',history=history))
    build=read(PARENT/'BUILD-v5-reviewed.json');windows=[]
    for tag,context in sorted(binding.items()):
        assert re.fullmatch('mc-[0-9a-f]{24}',tag)
        directory=OUT/('run-'+tag);workspace=Path(build['workspace'])/('run-'+tag)/'worker'
        m=read(directory/'MICROBATCH.json');child=read(directory/'MODE_CHILD.json')
        assert m['BOARD']=='NOT_TESTED' and m['PL_calls']==0 and child['control_thread_stopped']
        assert child['mode_child_sha256']==sha(ROOT/'platform/qwen35/a12/mode_child.py')
        assert m['workers'][0]['all_protocol_and_observer_threads_stopped'] and m['owner_FDs_closed_after_observer_stop']==[True]
        independent=audit(workspace,PARENT/'BUILD-v5-reviewed.json')
        normal=(directory/'RESULT.json').exists()
        if normal:
            actual=read(directory/'RESULT.json')
            assert independent['status']=='COMPLETE_ACTUAL_PC_MICROBATCH_TRANSCRIPT'
            assert actual['actual_cpu_permits']==2880 and actual['validated_answers']==['app_R0','app_hit']
            assert m['workers'][0]['grants']==2880//m['grant_size']
        else:
            actual=read(directory/'FAILURE.json')
            assert independent['status']=='REJECTED_OR_INCOMPLETE_RETAIN_OWNER' and actual['validated_answers']==[]
            assert m['workers'][0]['gate_before_close']&(1<<63)
        if context['window'] is not None:
            assert normal==(context['window']['outcome']=='PASS_PC_WINDOW')
            assert child['window_id']==context['window']['window_id']
        target=OUT/'native-transcripts'/tag;target.mkdir(parents=True,exist_ok=False)
        for p in sorted(workspace.iterdir()):
            assert p.is_file() and p.stat().st_size<=16*1024**2;shutil.copyfile(p,target/p.name);assert sha(p)==sha(target/p.name)
        windows.append(dict(tag=tag,case=context['case'],normal=normal,grant_size=m['grant_size'],
            source_capsule='CAPSULE-v3' if context['case']=='transitions-02' else 'CAPSULE-v2',
            independent_audit=independent,worker_exit_code=m['workers'][0]['worker_exit_code'],
            result_answers=actual['validated_answers'],transcripts=[pin(p) for p in sorted(target.iterdir())]))
    assert len(windows)==11 and sum(r['normal'] for r in windows)==7
    save(OUT/'MODE_REVIEW.json',dict(status='PASS_PC_MODE_HISTORIES_AND_NATIVE_TRANSCRIPTS',cases=cases,windows=windows,
        normal_windows=7,failure_windows=4,final_capsule_v3_windows=4,BOARD='NOT_TESTED',PL_calls=0,
        release_allowed=False,replay_allowed=False,production_mode_switch='NOT_IMPLEMENTED',
        limitation='Private live-run observations are recorded; retrospective files alone are not release or replay authority'))
    for number,path in [('v1',WORK),('v2',WORK.with_name(WORK.name[:-1]+'2'))]:
        target=OUT/('reader-source-'+number);target.mkdir(exist_ok=False)
        for p in (path/'source').iterdir():shutil.copyfile(p,target/p.name)
    print('PASS: 11 actual PC windows; 3 closed sessions and 1 unclean session refused')

if __name__=='__main__':review()
