"""Preserve A03 and create the A04 evidence area; no build or model execution."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
out=ROOT/'eval/qwen35/a04';out.mkdir(exist_ok=False)
prior=json.loads((ROOT/'eval/qwen35/a03/closeout-v1/files.sha256.json').read_text())
bad=[p for p,h in prior.items() if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=h]
with (out/'preservation.json').open('x') as f:json.dump({'checked':len(prior),'mismatches':bad},f,indent=2)
assert not bad,bad
for p in ['docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md']:
    dest=out/'before'/p;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/p,dest)
with (out/'git-before.txt').open('x',encoding='utf-8') as f:
    subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
print(json.dumps({'A03_seal_verified':len(prior),'board':'NOT_TESTED'}))
