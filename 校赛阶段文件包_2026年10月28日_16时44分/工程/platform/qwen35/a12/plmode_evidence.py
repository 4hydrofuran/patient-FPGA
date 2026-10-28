"""Prepared PL mode integration, offline evidence. No Board entry point."""
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,read,save,sha,pin,BUNDLE
PARENT=ROOT/'evidence/model_pl_A/20261026-live-generation-v1'
OUT=ROOT/'evidence/model_pl_A/20261026-pl-mode-v1'
WORK=Path('/home/member-a/kv260-build/a12-pl-mode-20261026-v1')
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def prepare():
    OUT.mkdir();r=read(PARENT/'FINAL_REVIEW.json');files=[]
    for row in r['source']+r['evidence']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'];files.append(pin(p))
    files.extend(pin(PARENT/x) for x in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json'))
    mode=ROOT/'evidence/model_pl_A/20261026-mode-control-v1'
    for row in read(mode/'FINAL_REVIEW.json')['source']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'];files.append(pin(p))
    save(OUT/'BASELINE.json',dict(files=files,previous_turn_classification='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
if __name__=='__main__':prepare()
