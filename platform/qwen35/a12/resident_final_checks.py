"""Final PC source-epoch checks; serial model windows, no Board work."""
import os
import subprocess
import sys
from resident_evidence import ROOT,OUT,save,pin


def main():
    os.umask(0o077);folder=OUT/'finalchecks01';folder.mkdir()
    save(folder/'SOURCE.json',dict(source=[pin(q) for q in sorted((ROOT/'platform/qwen35/a12').glob('*resident*')) if q.is_file()]))
    commands=[['-m','unittest','-v','test_resident_control','test_resident_admission','test_resident_relocate']]
    for i,start in enumerate(range(0,25,4)):
        commands.append(['resident_run.py','--tag','finalcohort'+str(i+1),'--scenario','cohort','--start',str(start),'--count',str(min(4,25-start))])
    commands.append(['resident_run.py','--tag','finalflow','--scenario','flow'])
    commands.append(['resident_run.py','--tag','finalpolicy','--scenario','policy'])
    for i,cmd in enumerate(commands):
        r=subprocess.run([sys.executable,*cmd],cwd=ROOT/'platform/qwen35/a12',capture_output=True,text=True,timeout=180)
        save(folder/('COMMAND_'+str(i).zfill(2)+'.json'),dict(command=[sys.executable,*cmd],exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
        print(i,r.returncode,r.stdout.strip()[-500:],flush=True)
        if r.returncode:print(r.stderr[-2000:],flush=True);raise SystemExit(r.returncode)
    save(folder/'RESULT.json',dict(status='PASS_FINAL_PC_CHECKS_AWAIT_RAW_AUDIT',commands=len(commands),BOARD='NOT_TESTED'))


if __name__=='__main__':main()
