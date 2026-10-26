"""Finish current-code strict/fault checks after the full cap72 suite terminates."""
import subprocess
import sys
from promptpl_evidence import ROOT,OUT,read,save

def run(name,argv):
    cmd=[sys.executable,'-B',str(ROOT/'platform/qwen35/a12'/argv[0]),*argv[1:]]
    r=subprocess.run(cmd,capture_output=True,text=True)
    save(OUT/(name+'-COMMAND.json'),dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    print(name,r.returncode,r.stdout.strip(),flush=True)
    if r.returncode:raise SystemExit(r.returncode)

def main():
    assert len(read(OUT/'cohort02-SUITE.json')['windows'])==25
    if '--after-stdout' in sys.argv:
        assert read(OUT/'cohort02-audit-COMMAND.json')['exit_code']==0
        assert read(OUT/'STDOUT_BOUND_COUNTEREXAMPLE.json')['actual_stream_packets']>32
    else:
        run('cohort02-audit',['promptpl_audit.py','--suite','cohort02'])
        run('stdout-bound',['test_promptpl_stdout.py'])
    run('strict01',['promptpl_trial.py','--suite','strict01','--caps','1','--ids','DEV-001,DEV-004,DEV-005,DEV-011,DEV-012,V08'])
    run('strict01-audit',['promptpl_audit.py','--suite','strict01'])
    run('faults01',['promptpl_faults.py','--tag','faults01'])
    run('faults01-audit',['promptpl_audit.py','--suite','faults01'])
    print('PASS_CURRENT_CODE_FULL_COHORT_STRICT_SUBSET_AND_TARGETED_FAULTS',flush=True)
if __name__=='__main__':main()
