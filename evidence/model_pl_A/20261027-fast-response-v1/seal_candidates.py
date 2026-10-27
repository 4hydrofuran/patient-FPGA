"""Seal the final small Python/metadata corrections before any release-v2 tests."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
WEB=ROOT/'platform/qwen35/web'
sys.path.insert(0,str(WEB))
from fast_response_prepare import manifest,save,sha

release=ROOT/'release/a12_fast_response_20261027_v2'
changes=[]
source=WEB/'vendor/web_gateway/src/patient_web/reference/session.py'
for package in sorted(release.iterdir()):
    if not package.is_dir():continue
    for kind in ('ordinary','continuous'):
        target=package/kind/'web_gateway/src/patient_web/reference/session.py'
        before=sha(target);shutil.copyfile(source,target)
        changes.append(dict(path=target.relative_to(ROOT).as_posix(),before=before,after=sha(target)))
    p=package/'BUDGETS.json';budget=json.loads(p.read_text(encoding='utf-8'))
    budget['selected_question']=budget['selected_request_id'];budget['selected_request_id']='app_R0';save(p,budget)
    origin=json.loads((ROOT/'evidence/model_pl_A/20261027-fast-response-v1/SOURCE_PINS.json').read_text(encoding='utf-8'))
    gateway=[]
    for row in origin['files']:
        p=WEB/'vendor'/row['path']
        if p.is_file() and sha(p)!=row['sha256']:
            gateway.append(dict(path=row['path'],original_sha256=row['sha256'],derived_sha256=sha(p)))
    save(package/'DERIVATION.json',dict(provider='A',frontend_original_commit=origin['frontend_commit'],
        gateway_changed_files=gateway,
        added_runtime_files=['short_prompt_adapter.py','fast_response_profile.py','fast_response_entry.py',
            'fast_response_preflight.py','fast_response_prepare_support.py','fast_response_verify.py','fast_response_pc.py'],
        host_config='profile.json and web-config.json',
        external_model_weights=True,public_math_changed=False,public_ABI_changed=False,
        binary_changed=False,board_tested=False))
    meta=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'));meta['files']=manifest(package);save(package/'MANIFEST.json',meta)
save(Path(__file__).with_name('SEALED_CORRECTIONS.json'),dict(stage='BEFORE_RELEASE_V2_PC_TESTS',changes=changes,
    metadata_correction='selected_request_id=app_R0; selected_question stored separately',BOARD='NOT_TESTED'))
print(json.dumps(dict(status='SEALED_OFFLINE',packages=3,corrected_python_files=len(changes))))
