"""Seal this intake and confirm old artifacts weren't replaced; not an acceptance waiver."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]
E=ROOT/'evidence/A06_acceptance'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,data):
    with p.open('x',encoding='utf-8') as f:json.dump(data,f,indent=2,ensure_ascii=False)
def main():
    manifest=read(E/'intake-v1/download-manifest.json')
    B=ROOT/'hw/linear_B_received/B03-fdd1d656290b-20261003'
    for entry in manifest['files']:
        assert sha(B/entry['path'])==entry['sha256'],entry['path']
    for p,v in read(E/'A04_A05_input_identity.json').items():assert sha(ROOT/p)==v['sha256'],p
    k=read(ROOT/'hw/linear_A/KERNEL_SOURCE.json')
    assert not k['accepted'] and not k['frozen'] and k['xo_sha256'] is None
    assert read(ROOT/'docs/PROJECT_STATUS.json')['stage_status']=='NOT_ACCEPTED_DELIVERY_AND_LOCAL_LICENSE_BLOCKED'
    for p in ['contracts-after','config-after']:
        assert read(E/f'commands/{p}.json')['exit_code']==0
    history=read(ROOT/'eval/qwen35/a05/batch-fix-v1/files.sha256.json')
    for p in ['AGENTS.md','docs/PROJECT_STATUS.json','docs/status/A.md','docs/DESIGN_GAP.md','docs/TEST_MATRIX.md']:
        assert sha(E/'intake-v1/before'/p)==history[p],p
    files=[]
    for directory in [B,E,ROOT/'platform/qwen35/a06',ROOT/'hw/linear_A']:
        files.extend(p for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    files += [ROOT/p for p in ['AGENTS.md','docs/PROJECT_STATUS.json','docs/status/A.md',
                              'docs/DESIGN_GAP.md','docs/TEST_MATRIX.md',
                              'docs/handoffs/A_A06_RECEIPT_20261003.md']]
    # This outer record is still being written; do not seal its reservation.
    files=[p for p in files if p.name not in ['files.sha256.json','FINAL_AUDIT.json','final-audit.json']]
    seal={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(files))}
    save(E/'files.sha256.json',seal)
    result={'status':'PASS_INTEGRITY_NOT_KERNEL_ACCEPTANCE','sealed_files':len(seal),
            'seal_sha256':sha(E/'files.sha256.json'),'B_files_unchanged':len(manifest['files']),
            'A04_A05_inputs_unchanged':11,'before_governance_matches_A05_seal':5,
            'git_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'new_commit':None,'remote_write':False,'BOARD':'NOT_TESTED',
            'kernel_acceptance':'NOT_ACCEPTED','exclusions':['in-progress commands/final-audit.json','this FINAL_AUDIT.json','files.sha256.json itself']}
    save(E/'FINAL_AUDIT.json',result);print(json.dumps(result))
if __name__=='__main__':main()
