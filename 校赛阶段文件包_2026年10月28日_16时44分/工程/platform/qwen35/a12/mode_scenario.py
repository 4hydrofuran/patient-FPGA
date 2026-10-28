"""Real PC model scenario: idle changes, failed-input refusal and strict fallback."""
import argparse
import json
from pathlib import Path
import time
import uuid

from mode_evidence import ROOT,OUT,WORK,read,save,sha,pin
from mode_coordinator import ModeCoordinator
from mode_journal import ModeBlocked,read_journal
from mode_history import validate_history
from resource_probe_policy import ordinary_comparison

def run(tag,capsule,case):
    directory=OUT/tag;directory.mkdir(exist_ok=False)
    state=WORK/('state-'+tag);c=ModeCoordinator(state,capsule,trusted_worker=True);results=[];refusals=[]
    source=[pin(ROOT/'platform/qwen35/a12'/n) for n in ('mode_coordinator.py','mode_child.py','mode_journal.py',
        'mode_history.py','mode_reader.py','mode_registry.py','mode_scenario.py')]
    save(directory/'SOURCE_AT_LAUNCH.json',dict(capsule=str(capsule),capsule_sha256=sha(capsule),source=source))
    def refuse(name,call):
        try:call()
        except ModeBlocked as exc:
            refusals.append(dict(action=name,reason=str(exc),phase=c.phase));return
        raise AssertionError('unsafe operation was not refused: '+name)
    def execute(input_id,mode=None,fault=None,cancel=False):
        if mode:c.switch(mode)
        launched=c.launch(input_id,fault=fault)
        # A real Popen/pidfd is live here; this is not a lock-file-only claim.
        assert c.active['process'].poll() is None and not c.active['manager'].terminal()
        refuse('switch_during_live_window',lambda:c.switch('PC_BATCH_CANDIDATE'))
        if cancel:
            until=time.monotonic()+120
            while time.monotonic()<until:
                c.observe()
                r=c.active
                if r and r['page'] is not None and r['page'].snapshot()['shared_claims']>=5:break
                time.sleep(.005)
            assert c.active and c.active['page'] and c.active['page'].snapshot()['shared_claims']>=5
            c.cancel()
        result=c.wait(180);assert result.get('outcome'),result;results.append(result)
        print(json.dumps(dict(event='MODE_WINDOW_FINISHED',input_id=input_id,outcome=result['outcome'],phase=c.phase)),flush=True)
        return result
    try:
        if case=='transitions':
            execute('strict-new-1')
            execute('batch-new-1','PC_BATCH_CANDIDATE')
            failed=execute('batch-failed-1',fault='cached_revoke')
            assert failed['outcome']=='FAILED_PC_DRAINED_NO_REPLAY'
            refuse('replay_failed_input',lambda:c.launch('batch-failed-1'))
            refuse('candidate_after_fault',lambda:c.switch('PC_BATCH_CANDIDATE'))
            refuse('fallback_reuses_failed_input',lambda:c.fallback_for_new_input('batch-failed-1'))
            c.fallback_for_new_input('strict-fresh-2')
            execute('strict-fresh-2')
            refuse('candidate_stays_disabled',lambda:c.switch('PC_BATCH_CANDIDATE'))
            equal={}
            for name in ('app_R0','app_hit'):
                base=read(OUT/('run-'+results[0]['tag'])/name/'result.json')
                equal[name]=[ordinary_comparison(base,read(OUT/('run-'+r['tag'])/name/'result.json'))
                    for r in (results[1],results[-1])]
        else:
            failed=execute('cancelled-new-1','PC_BATCH_CANDIDATE',cancel=True)
            assert failed['outcome']=='FAILED_PC_DRAINED_NO_REPLAY'
            refuse('cancelled_input_not_replayed',lambda:c.fallback_for_new_input('cancelled-new-1'))
            c.fallback_for_new_input('strict-after-cancel-1');execute('strict-after-cancel-1');equal={}
        c.close();rows=read_journal(state/'coordinator.jsonl');history=validate_history(rows,closed_required=True)
        save(directory/'RESULT.json',dict(status='PASS_REAL_PC_MODE_TRANSITIONS',case=case,windows=results,refusals=refusals,
            equality=equal,history=history,state_directory=str(state),coordinator_closed=c.phase=='CLOSED',
            DIRTY_removed=not (state/'DIRTY.json').exists(),BOARD='NOT_TESTED',PL_calls=0,production_enabled=False,
            window_unit='THREE_REQUEST_ORDINARY_PC_VALIDATION_WINDOW_NOT_SERVICE_REQUEST_ROUTING'))
    except BaseException as exc:
        save(directory/'FAILURE.json',dict(status='FAIL_RETAINED_NO_REPLAY',reason=type(exc).__name__+': '+str(exc),
            phase=c.phase,state_directory=str(state),windows=results,refusals=refusals,BOARD='NOT_TESTED'))
        # Retain unknown process/page ownership; no kill/reset, no synthetic close.
        if c.active is not None:c.cancel(log=False)
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--capsule',type=Path,required=True)
    p.add_argument('--case',choices=['transitions','cancel'],default='transitions');a=p.parse_args();run(a.tag,a.capsule,a.case)
