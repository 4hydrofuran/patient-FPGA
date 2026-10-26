"""Reproduce rejected-history FD retention; verify local cleanup, never release."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
from plmode_evidence import ROOT,OUT,save,sha
from plmode_journal import ModeJournal

def child(snapshot):
    ns={'__name__':'plmode_constructor_counterexample','__file__':str(snapshot)}
    exec(compile(snapshot.read_text(),str(snapshot),'exec'),ns)
    with tempfile.TemporaryDirectory(prefix='a12-plmode-init-') as root:
        path=Path(root)/'history';j=ModeJournal(path,uuid.uuid4().hex)
        # Mechanically valid chain/closed marker; semantically invalid mode.
        j.append('SESSION_OPEN',default_mode='BATCH_CANDIDATE',domain='PC_CPU_MODEL',candidate_disabled=False,release_allowed=False,
            manager_pid=os.getpid(),manager_start_ticks=1)
        j.append('SESSION_CLOSE',candidate_disabled=False,release_allowed=False);j.finish()
        original=(path/'coordinator.jsonl').read_bytes();before=set(os.listdir('/proc/self/fd'))
        try:ns['Coordinator'](path,OUT/'BUILD-v2.json')
        except RuntimeError as exc:reason=str(exc)
        else:raise AssertionError('invalid history accepted')
        after=set(os.listdir('/proc/self/fd'))
        assert (path/'coordinator.jsonl').read_bytes()==original and (path/'DIRTY.json').is_file()
        print(json.dumps(dict(reason=reason,additional_fds=len(after-before),DIRTY_retained=True,history_unchanged=True,native_started=False,release_allowed=False)))

def main():
    old=OUT/'COORDINATOR_BEFORE_INIT_CLEANUP.py';new=ROOT/'platform/qwen35/a12/plmode_coordinator.py';rows=[]
    for path,expected in ((old,3),(new,0)):
        cmd=[sys.executable,__file__,'--child',str(path)];r=subprocess.run(cmd,capture_output=True,text=True,check=True)
        row=json.loads(r.stdout);assert not r.stderr and row['additional_fds']==expected;rows.append(dict(source_sha256=sha(path),command=cmd,exit_code=0,observation=row))
    save(OUT/'INIT_CLEANUP_COUNTEREXAMPLE.json',dict(status='PASS_REJECTED_HISTORY_LOCAL_FDS_CLOSED_DIRTY_PRESERVED',records=rows,BOARD='NOT_TESTED'))
    print('PASS_REJECTED_HISTORY_LOCAL_FDS_CLOSED_DIRTY_PRESERVED')
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':child(Path(sys.argv[2]))
    else:main()
