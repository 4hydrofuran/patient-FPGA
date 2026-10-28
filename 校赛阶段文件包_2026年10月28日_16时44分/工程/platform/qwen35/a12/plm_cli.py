"""Record exact offline commands; never routes through a shell or board tool."""
import argparse
import sys
from plm_evidence import ROOT,WORK,read,OUT
from plm_build import run
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['run']);p.add_argument('--tag',required=True);a,rest=p.parse_known_args()
    assert a.tag.replace('-','').isalnum()
    run([sys.executable,'-B',ROOT/'platform/qwen35/a12/plm_run.py','--tag',a.tag]+rest,'RUN-'+a.tag,ROOT,180)
