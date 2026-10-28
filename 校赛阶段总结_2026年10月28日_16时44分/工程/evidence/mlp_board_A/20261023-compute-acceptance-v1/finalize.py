"""Preserve historical evidence and seal the new independently audited result."""
import hashlib,json,shutil
from pathlib import Path
E=Path(__file__).resolve().parent;ROOT=E.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_bytes())
old_names=['evidence/board_platform/A10_20261023_isolated_single_v1/seal_01.json',
           'evidence/mlp_board_A/20261023-integration-v1/stopped_audit_01/SEAL.json',
           'evidence/mlp_board_A/20261023-final-closeout-v1/SEAL.json',
           'evidence/mlp_board_A/20261023-open-investigation-v1/SEAL.json']
verified={}
for name in old_names:
    entries=read(ROOT/name)['files']
    for n,e in entries.items():
        p=ROOT/n;assert sha(p)==e['sha256'] and p.stat().st_size==e['bytes'],n
    verified[name]=len(entries)
checks=['contracts_01','config_01','engine_01','management_02','prepl_final_01','package_02','package_entry_01','audit_01','contracts_final_01','config_final_01']
for n in checks:assert read(E/(n+'.json'))['exit_code']==0,n
pin=sha(E/'bundle-v2/manifest.json')
assert pin==sha(E/'standard-entry-PC-check/manifest.json')==read(E/'AUDIT.json')['manifest_sha256']
status=read(ROOT/'docs/PROJECT_STATUS.json');assert status['stage']=='A11' and status['stage_status']=='PASS_WITH_LIMITATIONS'
assert status['a11_acceptance_20261023']['all_bit_exact'] and status['a11_acceptance_20261023']['real_submissions']==23
for n,e in read(E/'bundle-v2/manifest.json')['files'].items():
    p=E/'bundle-v2'/n;assert p.stat().st_size==e['bytes'] and sha(p)==e['sha256'],n
files=['docs/PROJECT_STATUS.json','docs/DESIGN_GAP.md','docs/DECISIONS.md','docs/TEST_MATRIX.md','docs/AI_ASSISTANCE.md','docs/status/A.md','docs/handoffs/A_A11_COMPLETE_20261023.md','design/qwen35/target_results.json']
dest=E/'governance_snapshot';dest.mkdir(exist_ok=False)
for n in files:
    p=dest/n;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/n,p)
dest=E/'source_snapshot';dest.mkdir(exist_ok=False)
for p in (ROOT/'platform/qwen35/a11').iterdir():
    if p.suffix in ('.py','.ps1','.cpp','.hpp','.sh'):shutil.copyfile(p,dest/p.name)
receipt=dict(status='PASS_FINAL_CONSISTENCY',A11='PASS_WITH_LIMITATIONS',A12='NOT_STARTED',
             old_seals_verified=verified,passed_checks=checks,manifest_sha256=pin,
             source_math_ABI_kernel_driver_changed=False,committed=False,pushed=False)
with (E/'FINAL_CHECK.json').open('x') as f:json.dump(receipt,f,indent=2)
entries={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(E.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='SEAL.json'}
with (E/'SEAL.json').open('x',encoding='utf-8') as f:json.dump(dict(status='SEALED_A11_PASS_WITH_LIMITATIONS',files=entries),f,ensure_ascii=False,indent=2)
assert all(sha(ROOT/n)==e['sha256'] for n,e in entries.items())
print(json.dumps(dict(status='SEALED_A11_PASS_WITH_LIMITATIONS',files=len(entries),old_seals_verified=verified,seal_sha256=sha(E/'SEAL.json'))))
