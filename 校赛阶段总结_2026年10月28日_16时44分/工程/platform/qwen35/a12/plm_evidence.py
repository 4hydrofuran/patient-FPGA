"""PC wire integration of the real-XRT derivative; board remains hard disabled."""
import hashlib
import json
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'evidence/model_pl_A/20261026-pl-manager-v1'
PARENT=ROOT/'evidence/model_pl_A/20261026-pl-auth-binding-v1'
WORK=Path('/home/member-a/kv260-build/a12-pl-manager-20261026-v1')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def save(p,v):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2);f.write('\n')
def pin(p):
    p=Path(p);return dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
def prepare():
    OUT.mkdir(exist_ok=False);r=read(PARENT/'FINAL_REVIEW.json');files=[]
    for row in r['source']+r['evidence']:
        p=ROOT/row['path'];assert sha(p)==row['sha256'],row['path'];files.append(pin(p))
    files+=[pin(PARENT/'FINAL_REVIEW.json'),pin(PARENT/'TERMINAL_VERIFICATION.json')]
    save(OUT/'BASELINE.json',dict(files=files,previous_goal_turn='progress',goal_status='active',BOARD='NOT_TESTED'))
    for name in ('PROJECT_STATUS.json','DESIGN_GAP.md','DECISIONS.md','TEST_MATRIX.md','AI_ASSISTANCE.md'):
        shutil.copyfile(ROOT/'docs'/name,OUT/(name+'.before'))
if __name__=='__main__':prepare()
