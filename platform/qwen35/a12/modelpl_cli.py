"""Record exact no-board model commands and exits."""
import argparse
import sys
from modelpl_evidence import ROOT
from modelpl_build import run
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--tag',required=True);a,rest=p.parse_known_args();assert a.tag.replace('-','').isalnum()
    run([sys.executable,'-B',ROOT/'platform/qwen35/a12/modelpl_run.py','--tag',a.tag]+rest,'RUN-'+a.tag,ROOT,300)
