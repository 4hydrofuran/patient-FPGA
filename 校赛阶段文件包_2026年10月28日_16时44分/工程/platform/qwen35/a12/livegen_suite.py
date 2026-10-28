"""Serial actual model windows, with every command/exit status retained."""
import argparse
import sys
from livegen_evidence import ROOT,OUT,save
from livegen_build import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);a=p.parse_args();assert a.tag.isalnum()
    windows=[]
    for suffix,cap,fault in [('cap72',72,None),('cap1',1,None),('same-uuid',72,'same_uuid_reload'),('mutation',72,'platform_mutation'),('begin-fsync',72,'begin_fsync')]:
        tag=a.tag+'-'+suffix;cmd=[sys.executable,ROOT/'platform/qwen35/a12/livegen_run.py','--revision',a.revision,'--tag',tag,'--cap',cap]
        if fault:cmd.extend(['--fault',fault])
        run(cmd,tag+'-COMMAND');windows.append(tag)
    save(OUT/(a.tag+'-SUITE.json'),dict(status='PC_COMMANDS_PASSED_AUDIT_PENDING',windows=windows,BOARD='NOT_TESTED'))
if __name__=='__main__':main()
