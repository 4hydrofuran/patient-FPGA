"""Preserve prior seal and seal current A-owned continuation evidence, without circular hashes."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a05/batch-fix-v1'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
prior=json.loads((ROOT/'eval/qwen35/a05/files.sha256.json').read_text(encoding='utf-8'));changed=[]
for name,h in prior.items():
    if sha(ROOT/name)==h:continue
    saved=OUT/'before'/name
    if name in ('platform/qwen35/a05/native_client.py','platform/qwen35/a05/state_regression.py'):saved=OUT/'before'/Path(name).name
    assert saved.is_file() and sha(saved)==h,('prior evidence not preserved',name)
    changed.append({'path':name,'old_sha256':h,'saved':str(saved.relative_to(ROOT))})
status=json.loads((ROOT/'docs/PROJECT_STATUS.json').read_text(encoding='utf-8'));report=json.loads((OUT/'REPORT.json').read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'modules/linear_A/manifest.json').read_text(encoding='utf-8'))
assert status['stage_status']==report['status']==manifest['status']=='PASS_PC_A05_FULL_MODEL_PHYSICAL_T8'
assert status['a05_physical_ubatch']==manifest['physical_ubatch']==8
assert all(v=='NOT_TESTED' for k,v in report['domains'].items() if k!='PC')
assert status['linux_memory_bytes'] is None and status['pl_bo_budget_bytes'] is None
for p in ['REPORT.md','REPORT.json','commands.json','runtime-build-v8.json']:assert (OUT/p).is_file()
audit={'prior_entries':len(prior),'unchanged':len(prior)-len(changed),'changed_but_exact_prior_bytes_saved':changed,
 'current_status_consistent':True,'BOARD':'NOT_TESTED','new_commit':None}
with (OUT/'FINAL_AUDIT.json').open('x',encoding='utf-8') as f:json.dump(audit,f,ensure_ascii=False,indent=2)
with (OUT/'git-after.txt').open('x',encoding='utf-8') as f:subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
paths=set()
for name in ['eval/qwen35/a05','runtime/qwen35_w4a8','platform/qwen35/a05','modules/linear_A','system_qwen35/app']:
    paths.update(p for p in (ROOT/name).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
for name in ['AGENTS.md','docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/handoffs/A_A05_CLOSEOUT_20261002.md']:
    paths.add(ROOT/name)
excluded={OUT/'files.sha256.json',OUT/'seal-receipt.json',ROOT/'platform/qwen35/a05/evidence/continue-seal-v2.json'}
files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(paths) if p not in excluded}
seal=OUT/'files.sha256.json'
with seal.open('x',encoding='utf-8') as f:json.dump(files,f,ensure_ascii=False,indent=2)
receipt={'files':len(files),'sha256':sha(seal),'old_seal_sha256':sha(ROOT/'eval/qwen35/a05/files.sha256.json'),
 'excluded_self_and_own_command_receipt':[str(p.relative_to(ROOT)) for p in sorted(excluded)],'old_seal_preserved':True}
with (OUT/'seal-receipt.json').open('x',encoding='utf-8') as f:json.dump(receipt,f,ensure_ascii=False,indent=2)
print(json.dumps(receipt))
