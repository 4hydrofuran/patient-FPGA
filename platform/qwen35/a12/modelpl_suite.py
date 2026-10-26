"""Sequential real-Qwen ordinary windows; failures remain separate and unmodified."""
import argparse
import sys
from modelpl_evidence import ROOT,OUT,save
from modelpl_build import run
def main():
    p=argparse.ArgumentParser();p.add_argument('--revision',type=int,required=True);p.add_argument('--tag',required=True);a=p.parse_args();assert a.tag.replace('-','').isalnum()
    cases=[('strict',1,None),('batch',72,None)]+[(k,72,k) for k in ('begin_fsync','grant_fsync','end_fsync','receipt_fsync','grant_slow','end_slow','request_digest','drop_copy','cached_revoke')]
    tags=[]
    for name,cap,fault in cases:
        tag=a.tag+'-'+name.replace('_','-');cmd=[sys.executable,'-B',ROOT/'platform/qwen35/a12/modelpl_run.py','--revision',str(a.revision),'--tag',tag,'--cap',str(cap)]
        if fault:cmd+=['--fault',fault]
        run(cmd,'RUN-'+tag,ROOT,300);tags.append(tag)
    save(OUT/(a.tag+'-SUITE.json'),dict(status='PASS_ALL_EXPECTED_ACTUAL_CPU_MODEL_OUTCOMES',windows=tags,actual_CPU_model=True,BOARD='NOT_TESTED',actual_FPGA_calls=None))
if __name__=='__main__':main()
