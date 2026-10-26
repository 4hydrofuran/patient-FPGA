"""Bounded resident application preparation; no Board entry or lease acquisition."""
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,read,save,sha,pin
PARENT=ROOT/'evidence/model_pl_A/20261026-prompt-private-v1'
OUT=ROOT/'evidence/model_pl_A/20261026-resident-v1'
WORK=Path('/home/member-a/kv260-build/a12-resident-20261026-v1')
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def prepare():
    OUT.mkdir();r=read(PARENT/'FINAL_REVIEW.json');files=r['source']+r['evidence']
    for row in files:assert sha(ROOT/row['path'])==row['sha256']
    save(OUT/'BASELINE.json',dict(files=files+[pin(PARENT/'FINAL_REVIEW.json'),pin(PARENT/'TERMINAL_VERIFICATION.json')],
        resident_spec=pin(ROOT/'docs/A12_BOUNDED_RESIDENT_SERVICE_DESIGN_20261026.md'),previous_turn_classification='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
    print('PREPARED_RESIDENT_OFFLINE_BASELINE')
if __name__=='__main__':prepare()
