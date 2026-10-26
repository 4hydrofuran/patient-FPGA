"""Serial PC model windows; persist each exact command and exit status."""
import argparse
from pathlib import Path
import sys
from generation_evidence import ROOT,OUT,WORK,read,save
from generation_build import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);p.add_argument('--revision',type=int,required=True);a=p.parse_args()
    assert a.tag.replace('-','').isalnum()
    scenarios=[('cap72',72,None),('cap1',1,None),('generation-change',72,'generation_mutate'),
        ('slot-stale',72,'generation_slot_stale'),('begin-fsync',72,'begin_fsync'),('bad-copy',72,'drop_copy')]
    windows=[]
    for name,cap,fault in scenarios:
        tag=a.tag+'-'+name;cmd=[sys.executable,ROOT/'platform/qwen35/a12/generation_run.py','--revision',a.revision,'--tag',tag,'--cap',cap]
        if fault:cmd.extend(['--fault',fault])
        run(cmd,tag+'-COMMAND',ROOT,180);windows.append(tag)
    save(OUT/(a.tag+'-SUITE.json'),dict(status='COMMANDS_PASSED_AUDIT_PENDING',windows=windows,BOARD='NOT_TESTED',real_PL_results_consumed=False))
if __name__=='__main__':main()
