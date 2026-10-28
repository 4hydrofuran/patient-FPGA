"""Separate no-board P1-3 candidate; never overwrite frozen earlier sources."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261026-microbatch-v1'
PRIOR=ROOT/'evidence/model_pl_A/20261026-health-fence-v1'
WORK=Path('/home/member-a/kv260-build/a12-microbatch-20261026-v1')
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
def pin(p):
    p=Path(p);return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def prepare():
    OUT.mkdir(exist_ok=False);d=read(PRIOR/'FINAL_REVIEW.json');paths=set()
    for row in d['source']+d['evidence']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'],str(p);paths.add(p)
    paths.add(PRIOR/'FINAL_REVIEW.json')
    save(OUT/'BASELINE.json',dict(status='PRESERVED_BEFORE_MICROBATCH_WORK',files=[pin(p) for p in sorted(paths)],
        previous_goal_turn='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md'):
        shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
if __name__=='__main__':prepare()
