"""Seal explicit A05 scope and verify original A04 files or pre-edit backups."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'eval/qwen35/a05'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
prior=json.loads((ROOT/'eval/qwen35/a04/files.sha256.json').read_text());unchanged=0;backups=[]
allowed={'docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md','docs/DECISIONS.md','docs/AI_ASSISTANCE.md','config/qwen35/selection.json','system_qwen35/app/cli.py','system_qwen35/app/voice_cli.py','system_qwen35/app/voice_loop.py','system_qwen35/app/checking.py'}
for name,h in prior.items():
    if sha(ROOT/name)==h:unchanged+=1;continue
    assert name in allowed,('unexpected old evidence change',name)
    saved=OUT/'before'/name;assert saved.is_file() and sha(saved)==h,('missing exact backup',name);backups.append(name)
build=json.loads((OUT/'runtime-build-v3.json').read_text())
for name,entry in build['files'].items():assert sha(Path(name))==entry['sha256'],name
for name,h in build['source_files'].items():
    if name.startswith('runtime/qwen35_w4a8/') and not name.endswith('README.md'):assert sha(ROOT/name)==h,name
sources=[]
for directory in ('runtime/qwen35_w4a8','modules/linear_A','platform/qwen35/a05','eval/qwen35/a05'):
    for p in (ROOT/directory).rglob('*'):
        if not p.is_file() or '__pycache__' in p.parts or p.name in ('files.sha256.json','files.sha256','FINAL_AUDIT.json'):continue
        if directory=='platform/qwen35/a05' and p.parent.name=='evidence':
            v=json.loads(p.read_text());
            if v.get('status')=='RESERVED_NOT_COMPLETED':
                assert any(str(x).endswith('/seal.py') for x in v.get('argv',[])),str(p)
                continue # own receipt completes after this process exits; never hash provisional bytes
        sources.append(p)
for name in sorted(allowed|{'docs/handoffs/A_A05_20261002.md','system_qwen35/app/native_w4a8.py'}):sources.append(ROOT/name)
with (OUT/'git-after.txt').open('x') as f:subprocess.run(['git','status','--short'],cwd=ROOT,stdout=f,check=True)
sources.append(OUT/'git-after.txt');seal={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(sources))}
with (OUT/'files.sha256.json').open('x') as f:json.dump(seal,f,ensure_ascii=False,indent=2)
with (OUT/'files.sha256').open('x') as f:
    for name,h in seal.items():f.write(h+'  '+name+'\n')
audit={'old_A04_count':len(prior),'old_unchanged':unchanged,'old_current_documents_exact_backups':backups,'current_files':len(seal),'sha256_manifest':sha(OUT/'files.sha256.json'),'binary_integrity':'PASS','numeric_source_matches_build':'PASS','stage':'PARTIAL_PC_S1_WORKING_PHYSICAL_T2_T4_T8_NOT_ACCEPTED','commit':None,'BOARD':'NOT_TESTED','seal_self_and_completion_receipt_excluded':True}
with (OUT/'FINAL_AUDIT.json').open('x') as f:json.dump(audit,f,indent=2)
print(json.dumps(audit))
