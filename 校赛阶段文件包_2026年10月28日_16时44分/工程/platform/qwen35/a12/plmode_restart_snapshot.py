"""Capture actual clean restart as append-only evidence; never overwrite old mirror."""
import shutil
from pathlib import Path
from plmode_evidence import OUT,read,save,sha
from plmode_journal import read_journal
from plmode_history import validate

def main():
    folder=OUT/'fallback03';r=read(folder/'RESULT.json');original=Path(r['private_state'])/'history/coordinator.jsonl'
    rows=read_journal(original);before=read_journal_copy(folder/'history/coordinator.jsonl')
    assert len(rows)==len(before)+2 and [x['event'] for x in rows[-2:]]==['SESSION_OPEN','SESSION_CLOSE'] and rows[:len(before)]==before
    result=validate(rows,closed_required=True);assert result['candidate_disabled']
    copy=folder/'clean-restart-current.jsonl';shutil.copyfile(original,copy)
    save(folder/'CLEAN_RESTART.json',dict(status='PASS_CLEAN_RESTART_STRICT_LATCH_NO_MODEL_RUNS',original_private_log=str(original),
        before_sha256=sha(folder/'history/coordinator.jsonl'),after_sha256=sha(copy),rows_before=len(before),rows_after=len(rows),new_native_runs=0,BOARD='NOT_TESTED'))
    print('PASS_CLEAN_RESTART_STRICT_LATCH_NO_MODEL_RUNS')
def read_journal_copy(path):
    # Mirror permission bits are not Linux ownership evidence. Parse strict JSON
    # and compare it byte-for-byte/prefix against the safely read private log.
    from request_journal_audit import strict_json
    return [strict_json(x) for x in Path(path).read_bytes().splitlines()]
if __name__=='__main__':main()
