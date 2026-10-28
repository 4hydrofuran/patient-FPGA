"""Generated incremental SHA256 manifest; no payload/governance edits."""
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[3];E=R/'evidence/A06_acceptance/supplement-v1'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
 return h.hexdigest()
def main():
 output=E/'files.sha256.json';assert not output.exists()
 files={}
 paths=list(E.rglob('*'))
 paths += list((R/'platform/qwen35/a06').glob('*.py'))+list((R/'platform/qwen35/a06').glob('*.sh'))+list((R/'platform/qwen35/a06').glob('*.cpp'))
 paths += [R/p for p in ['platform/qwen35/a07/inspect_delivery.py','platform/qwen35/a07/test_delivery.py',
                        'docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md',
                        'docs/handoffs/A_A06_SUPPLEMENT_20261003.md','hw/linear_A/KERNEL_SOURCE.json']]
 for p in paths:
  if not p.is_file() or p.name=='seal-command.json' or '__pycache__' in p.parts:continue
  files[p.relative_to(R).as_posix()]=sha(p)
 B=R/'hw/linear_B_received/B03-supplement-e227297-20261003'
 inventory=json.loads((E/'inventory.json').read_text())
 for name,v in inventory['files'].items():
  p=B/'payload'/name;actual=sha(p);assert actual==v['sha256'],name
  files[p.relative_to(R).as_posix()]=actual
 for p in B.iterdir():
  if p.is_file():files[p.relative_to(R).as_posix()]=sha(p)
 with output.open('x',encoding='utf-8') as f:json.dump({'scope':'A06_SUPPLEMENT_NOT_FINAL_ACCEPTANCE','files':dict(sorted(files.items())),
       'excluded':['seal file itself','in-flight commands/seal-command.json'],'new_commit':None},f,indent=2)
 for name,digest in files.items():assert sha(R/name)==digest,name
 print(json.dumps({'status':'INCREMENTAL_HASH_VERIFIED','files':len(files),'seal_sha256':sha(output)}))
if __name__=='__main__':main()
