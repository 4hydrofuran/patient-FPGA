"""Pinned original platform gates, live-source candidate, offline evidence only."""
from pathlib import Path
import shutil
from modelpl_evidence import ROOT,read,save,sha,pin,BUNDLE
PARENT=ROOT/'evidence/model_pl_A/20261026-generation-binding-v1'
OUT=ROOT/'evidence/model_pl_A/20261026-live-generation-v1'
WORK=Path('/home/member-a/kv260-build/a12-live-generation-20261026-v1')
DOCS=('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md')

def bundle_pin(relative):
    assert sha(BUNDLE/'manifest.json')=='4fcb6af2d9e7d5b89f876697de6bd8f11e36174666169544a9016009551f070f'
    rows={r['path']:r for r in read(BUNDLE/'manifest.json')['files']};p=BUNDLE/relative;r=rows[relative]
    assert sha(p)==r['sha256'] and p.stat().st_size==r['bytes'],relative
    return p

def prepare():
    OUT.mkdir();files=[]
    for row in read(PARENT/'FINAL_REVIEW.json')['source']+read(PARENT/'FINAL_REVIEW.json')['evidence']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'];files.append(pin(p))
    files.extend(pin(PARENT/x) for x in ('FINAL_REVIEW.json','TERMINAL_VERIFICATION.json'))
    original=[]
    for name in ('control/resource_probe_manager.py','control/support/mlp_base.py','control/support/idle_board_trial.py',
        'platform/qwen35/a12/cpu01b_window.py','platform/qwen35/a12/cpu02_support.py','config/profile.pending.json'):
        original.append(pin(bundle_pin(name)))
    save(OUT/'BASELINE.json',dict(files=files,original_gate_sources=original,previous_turn_classification='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in DOCS:shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
if __name__=='__main__':prepare()
