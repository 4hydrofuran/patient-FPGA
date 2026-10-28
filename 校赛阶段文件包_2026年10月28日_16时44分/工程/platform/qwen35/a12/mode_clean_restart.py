"""Reopen only a genuinely closed scenario; no new model or old-input replay."""
import argparse
from pathlib import Path
from mode_evidence import OUT,read,save
from mode_coordinator import ModeCoordinator
from mode_journal import ModeBlocked,read_journal
from mode_history import validate_history

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--scenario',required=True);p.add_argument('--capsule',type=Path,required=True);a=p.parse_args()
    result=read(OUT/a.scenario/'RESULT.json');state=Path(result['state_directory']);before=read_journal(state/'coordinator.jsonl')
    c=ModeCoordinator(state,a.capsule,trusted_worker=True);assert c.mode=='PC_STRICT_CONTROL' and c.disabled
    old_input=result['windows'][0]['input_id']
    try:c.launch(old_input)
    except ModeBlocked:pass
    else:raise AssertionError('old input replayed after a clean restart')
    try:c.switch('PC_BATCH_CANDIDATE')
    except ModeBlocked:pass
    else:raise AssertionError('latched candidate failure lost at restart')
    c.close();after=read_journal(state/'coordinator.jsonl');history=validate_history(after,closed_required=True)
    assert len(after)==len(before)+2
    save(OUT/a.scenario/'CLEAN_RESTART.json',dict(status='PASS_CLEAN_RESTART_STRICT_DEFAULT_AND_NO_REPLAY',
        rows_before=len(before),rows_after=len(after),history=history,new_model_runs=0,BOARD='NOT_TESTED'))
