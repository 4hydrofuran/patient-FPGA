"""Preserve the previous A05 release before continuing the batch investigation."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'eval/qwen35/a05/batch-fix-v1'
OUT.mkdir(exist_ok=False)
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
paths=['runtime/qwen35_w4a8','modules/linear_A','system_qwen35/app',
 'docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md',
 'docs/AI_ASSISTANCE.md','docs/status/A.md','docs/handoffs/A_A05_20261002.md']
for name in paths:
    p=ROOT/name;dst=OUT/'before'/name;dst.parent.mkdir(parents=True,exist_ok=True)
    if p.is_dir():shutil.copytree(p,dst,ignore=shutil.ignore_patterns('__pycache__'))
    else:shutil.copy2(p,dst)
seal=ROOT/'eval/qwen35/a05/files.sha256.json';prior=json.loads(seal.read_text())
bad=[p for p,h in prior.items() if sha(ROOT/p)!=h]
with (OUT/'preservation.json').open('x') as f:json.dump({'prior_seal':sha(seal),'checked':len(prior),'mismatches':bad},f,indent=2)
with (OUT/'git-before.txt').open('x') as f:subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
assert not bad,bad
print(json.dumps({'preserved':len(prior),'BOARD':'NOT_TESTED'}))
