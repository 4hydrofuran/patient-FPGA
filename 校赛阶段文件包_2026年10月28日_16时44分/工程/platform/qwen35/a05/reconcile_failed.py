"""A's explicit failed-job reconciliation; no automatic stale-lock recovery."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'platform/ra02'))
from build_queue import CENTRAL,exclusive
p=argparse.ArgumentParser();p.add_argument('--job',required=True);a=p.parse_args()
with exclusive(CENTRAL):
    active=CENTRAL/'active.json';marker=json.loads(active.read_text());receipt=json.loads((CENTRAL/'results'/(a.job+'.json')).read_text())
    assert marker['job']==a.job and marker['owner']=='A' and receipt['status']=='FAILED' and receipt['exit_code']!=0
    processes=subprocess.check_output(['ps','-eo','pid,ppid,stat,args'],text=True)
    matches=[line for line in processes.splitlines() if any(s in line for s in ('cc1plus','cmake --build','/bin/bash /mnt/c/Patientqwen/platform/qwen35/a05/build.sh'))]
    assert not matches,matches
    dst=CENTRAL/'results'/(a.job+'.reconciled-active.json');assert not dst.exists();active.rename(dst)
    report={'job':a.job,'failed_receipt':receipt,'process_snapshot':processes,'matching_active_builds':matches,'archived_marker':str(dst),'action':'A explicitly reconciled completed failed process; marker archived, not discarded'}
    with (ROOT/'eval/qwen35/a05'/(a.job+'-reconciliation.json')).open('x') as f:json.dump(report,f,indent=2)
    print(json.dumps({'reconciled':a.job,'archived_marker':str(dst)}))
