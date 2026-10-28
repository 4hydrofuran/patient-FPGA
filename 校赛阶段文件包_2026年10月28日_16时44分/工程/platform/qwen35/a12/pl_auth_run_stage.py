"""Capture exact offline audit/package commands and return codes before freezing."""
import argparse
import sys
from pl_auth_evidence import ROOT
from pl_auth_build import command
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['review','package']);p.add_argument('--attempt',type=int,default=1);a=p.parse_args()
    command([sys.executable,'-B',ROOT/'platform/qwen35/a12'/('pl_auth_'+a.stage+'.py')],a.stage.upper()+'_COMMAND-v'+str(a.attempt),ROOT)
