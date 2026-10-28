"""Run disjoint PC windows serially; never multiply resident model pressure."""
import argparse
import os
import subprocess
import sys
from resident_evidence import ROOT, OUT, save


def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a=p.parse_args()
    assert a.tag.isalnum();os.umask(0o077)
    folder=OUT/a.tag;folder.mkdir()
    commands=[['-m','unittest','-v','test_resident_control','test_resident_admission']]
    for i,start in enumerate(range(0,25,4)):
        commands.append(['resident_run.py','--tag',a.tag+'c'+str(i+1),'--scenario','cohort','--start',str(start),'--count',str(min(4,25-start))])
    for fault in ('begin_fsync','end_fsync','receipt_fsync','end_slow','deadline','app_end_fsync','generation','cancel','busy'):
        commands.append(['resident_run.py','--tag',a.tag+'f'+fault.replace('_',''),'--scenario','fault','--fault',fault])
    for i,cmd in enumerate(commands):
        r=subprocess.run([sys.executable,*cmd],cwd=ROOT/'platform/qwen35/a12',capture_output=True,text=True,timeout=180)
        save(folder/('COMMAND_'+str(i).zfill(2)+'.json'),dict(command=[sys.executable,*cmd],exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,BOARD='NOT_TESTED'))
        print(i,r.returncode,r.stdout.strip()[-500:],flush=True)
        if r.returncode:
            print(r.stderr[-2000:],flush=True);raise SystemExit(r.returncode)
    save(folder/'RESULT.json',dict(status='PASS_SERIAL_PC_COMMANDS_NOT_YET_INDEPENDENTLY_AUDITED',commands=len(commands),BOARD='NOT_TESTED',PL_calls=None))


if __name__=='__main__':main()
