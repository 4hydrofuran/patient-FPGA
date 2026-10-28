"""Verify A04 seal and snapshot only A-owned files before A05 edits."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a05';OUT.mkdir(exist_ok=False)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
prior=json.loads((ROOT/'eval/qwen35/a04/files.sha256.json').read_text())
bad=[p for p,h in prior.items() if sha(ROOT/p)!=h]
with (OUT/'preservation.json').open('x') as f:json.dump({'checked':len(prior),'mismatches':bad},f,indent=2)
assert not bad,bad
paths=['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md',
       'system_qwen35/app/native.py','system_qwen35/app/voice_loop.py','system_qwen35/app/session.py','config/qwen35/selection.json']
for name in paths:
    dst=OUT/'before'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,dst)
with (OUT/'git-before.txt').open('x') as f:subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
print(json.dumps({'A04_verified':len(prior),'BOARD':'NOT_TESTED'}))
