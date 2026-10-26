"""Run targeted new-workload CPU faults serially, stop at unexpected failure."""
import argparse
import subprocess
import sys
from promptpl_evidence import ROOT,OUT,read,save

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args();assert a.tag.isalnum()
    windows=[]
    for fault in ('begin_fsync','grant_fsync','end_fsync','receipt_fsync','end_slow','request_digest','same_uuid_reload','drop_copy'):
        suite=a.tag+'-'+fault.replace('_','-')
        cmd=[sys.executable,'-B',str(ROOT/'platform/qwen35/a12/promptpl_trial.py'),'--suite',suite,'--ids','DEV-012','--caps','72','--fault',fault]
        r=subprocess.run(cmd,capture_output=True,text=True)
        save(OUT/(suite+'-COMMAND.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));print(fault,r.returncode,r.stdout.strip(),flush=True)
        if r.returncode:raise SystemExit(r.returncode)
        windows.extend(read(OUT/(suite+'-SUITE.json'))['windows'])
    save(OUT/(a.tag+'-SUITE.json'),dict(status='COMPLETED_TARGETED_CPU_PRIVATE_PROMPT_FAULTS',windows=windows,BOARD='NOT_TESTED'))
    print('COMPLETED_TARGETED_CPU_PRIVATE_PROMPT_FAULTS',len(windows),flush=True)
if __name__=='__main__':main()
