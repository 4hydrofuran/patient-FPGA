"""Offline generation consumer proof; no Board authorization or deployment."""
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,read,save,sha,pin
PARENT=ROOT/'evidence/model_pl_A/20261026-model-route-v1'
OUT=ROOT/'evidence/model_pl_A/20261026-generation-binding-v1'
WORK=Path('/home/member-a/kv260-build/a12-generation-binding-20261026-v1')
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def prepare():
    OUT.mkdir()
    files=[]
    review=read(PARENT/'FINAL_REVIEW.json')
    for row in review['source']+review['evidence']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'],row['path'];files.append(pin(p))
    files.extend(pin(PARENT/x) for x in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json'))
    save(OUT/'BASELINE.json',dict(files=files,BOARD='NOT_TESTED',real_generation_approval='UNBOUND'))
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
if __name__=='__main__':prepare()
