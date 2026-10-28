"""Sequential independent control windows; raw failures are never overwritten."""
import argparse
import sys
from plm_evidence import ROOT,OUT,save
from plm_build import run
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);a=p.parse_args()
    assert a.tag.replace('-','').isalnum();cases=[('strict',1,None),('batch',72,None)]
    cases += [(x,72,x) for x in ('begin_fsync','grant_fsync','end_fsync','receipt_fsync','grant_slow','end_slow','request_digest','legacy_replay','revoke_claim','nan_y','start','timeout','premature_unload','cached_T','reuse_generation')]
    names=[]
    for label,cap,fault in cases:
        tag=a.tag+'-'+label.replace('_','-');cmd=[sys.executable,'-B',ROOT/'platform/qwen35/a12/plm_run.py','--tag',tag,'--revision',str(a.revision),'--cap',str(cap)]
        if fault:cmd+=['--fault',fault]
        run(cmd,'RUN-'+tag,ROOT,180);names.append(tag)
    save(OUT/(a.tag+'-SUITE.json'),dict(status='PASS_ALL_EXPECTED_CONTROL_OUTCOMES',windows=names,BOARD='NOT_TESTED',model_execution=False,actual_FPGA_calls=None))
if __name__=='__main__':main()
