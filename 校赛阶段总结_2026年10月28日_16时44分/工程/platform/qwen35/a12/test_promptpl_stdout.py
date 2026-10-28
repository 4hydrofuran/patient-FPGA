"""Replay longest actual cohort stdout through old/new parser; PC I/O proxy."""
import io
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
from promptpl_evidence import OUT,read,save
from promptpl_manager import stdout_scope
from modelpl_manager import ModelManager

def exercise(method,raw,requests):
    with tempfile.TemporaryDirectory(prefix='a12-promptpl-stream-') as d:
        faults=[];m=SimpleNamespace(directory=Path(d),p=SimpleNamespace(stdout=io.StringIO(raw)),messages=queue.Queue(),requests=requests,_fail=faults.append)
        method(m);items=[]
        while not m.messages.empty():items.append(m.messages.get_nowait())
        return dict(faults=faults,queued_packets=sum(q is not None for q in items),EOF_observed=bool(items and items[-1] is None))

def main():
    folder=max((OUT/'cohort02').iterdir(),key=lambda p:len((p/'native.stdout').read_text().splitlines()))
    raw=(folder/'native.stdout').read_text();meta=read(folder/'RESULT.json')
    requests=read(OUT/'cohorts'/meta['cohort_id']/'requests.json');count=len(raw.splitlines());assert count>32 and meta['worker_exit_code']==0
    old=exercise(ModelManager._stdout,raw,requests);new=exercise(stdout_scope['_stdout'],raw,requests)
    assert old['faults']==['real-model stdout: bounded native stream exceeded'] and old['queued_packets']==32
    assert new==dict(faults=[],queued_packets=count,EOF_observed=True)
    save(OUT/'STDOUT_BOUND_COUNTEREXAMPLE.json',dict(status='PASS_ACTUAL_STREAM_REJECTED_BY_OLD_8_TOKEN_BOUND_ACCEPTED_BY_DERIVED_24_TOKEN_BOUND',
        cohort_id=meta['cohort_id'],actual_stream_packets=count,formal_new_packet_bound=5+sum(r['max_tokens'] for r in requests if r['op']=='generate'),
        old=old,new=new,scope='ACTUAL_SAVED_CPU_STDOUT_WITH_PC_STRINGIO_QUEUE_PROXY_NOT_A_NEW_MODEL_OR_BOARD_RUN',BOARD='NOT_TESTED'))
    print('PASS_ACTUAL_STDOUT_BOUND_COUNTEREXAMPLE',count)
if __name__=='__main__':main()
