"""Immutable-baseline capture and final PC evidence seal for this candidate."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261026-health-fence-v1'
PRIOR=ROOT/'evidence/model_pl_A/20261026-native-request-journal-v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def pin(p):
    p=Path(p);return dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p))

def prepare():
    OUT.mkdir(exist_ok=False)
    paths={ROOT/'docs/PROJECT_STATUS.json',ROOT/'docs/DESIGN_GAP.md',ROOT/'docs/DECISIONS.md',
        ROOT/'docs/TEST_MATRIX.md',ROOT/'docs/AI_ASSISTANCE.md'}
    for directory,field in [('20261025-resource-probe-v1','code'),('20261025-offline-followup-v1','source'),
            ('20261025-request-journal-v2','source'),('20261026-native-request-journal-v1','source')]:
        review=ROOT/'evidence/model_pl_A'/directory/'FINAL_REVIEW.json'
        paths.add(review)
        for item in read(review)[field]:
            path=Path(item['path']);path=path if path.is_absolute() else ROOT/path
            assert sha(path)==item['sha256'],str(path)
            paths.add(path)
    for item in read(PRIOR/'FINAL_REVIEW.json')['evidence']:
        path=ROOT/item['path'];assert sha(path)==item['sha256'];paths.add(path)
    for p in (ROOT/'contracts/qwen35').rglob('*'):
        if p.is_file():paths.add(p)
    probe=ROOT/'evidence/model_pl_A/20261025-resource-probe-v1'
    paths.add(probe/'bundle-v2.zip')
    for p in (probe/'bundle-v2').rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:paths.add(p)
    rows=[pin(p) for p in sorted(paths)]
    save(OUT/'BASELINE.json',dict(status='CAPTURED_BEFORE_NEW_HEALTH_TESTS',files=rows,
        BOARD='NOT_TESTED',board_contacted=False,goal_status='active'))
    shutil.copyfile(ROOT/'docs/PROJECT_STATUS.json',OUT/'PROJECT_STATUS.before.json')
    for name in ('DESIGN_GAP','DECISIONS','TEST_MATRIX','AI_ASSISTANCE'):
        shutil.copyfile(ROOT/('docs/'+name+'.md'),OUT/(name+'.before.md'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');a=p.parse_args()
    if a.prepare:prepare()
