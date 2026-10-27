"""Bind only the corrected A53 artifact/metadata; PC runtime and inputs stay byte-identical."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
PACKAGE=ROOT/'release/a12_realtime_model_draft_20261027_v1/realtime34-threads3-out32'
sys.path.insert(0,str(ROOT/'platform/qwen35/web'))
from fast_response_prepare_support import refresh_bundle_manifest,verify_package
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

arm=read(EV/'BUILD-ARM-v3-a53.json');pc=read(EV/'BUILD-PC-v3.json')
binary=Path(arm['binary']);assert sha(binary)==arm['sha256']
flags=(binary.parent/'CMakeFiles/qwen35-a12.dir/flags.make').read_text()
assert '-mcpu=cortex-a53' in flags and '-march=native' not in flags
verify_package(PACKAGE)
old=read(PACKAGE/'MANIFEST.json')
runtime={row['path']:row['sha256'] for row in old['files'] if row['path'].endswith('.py') or '/web_gateway/' in row['path']}
before=sha(PACKAGE/'continuous/bundle/bin/qwen35-a12')
for kind in ('ordinary','continuous'):
    window=PACKAGE/kind;bundle=window/'bundle'
    shutil.copyfile(binary,bundle/'bin/qwen35-a12')
    profile=read(window/'profile.json');profile['prefix_identity']['executable_sha256']=arm['sha256'];save(window/'profile.json',profile)
    config=read(bundle/'control/prefix-config.json');config['identity']['executable_sha256']=arm['sha256'];save(bundle/'control/prefix-config.json',config)
    refresh_bundle_manifest(bundle)
for name in ('DERIVATION.json','REALTIME_SOURCE.json'):
    value=read(PACKAGE/name);value['native_arm_sha256']=arm['sha256'];value['arm_build']='explicit cortex-a53 / 2026.1 SDK'
    save(PACKAGE/name,value)
value=read(PACKAGE/'CACHE_SOURCE.json');value['current_live_binary_sha256']=arm['sha256'];save(PACKAGE/'CACHE_SOURCE.json',value)
pins=read(PACKAGE/'SOURCE_PINS.json')
if not (PACKAGE/'PARENT_SOURCE_PINS.json').exists():shutil.copyfile(PACKAGE/'SOURCE_PINS.json',PACKAGE/'PARENT_SOURCE_PINS.json')
pins.update(native_binary_sha256=arm['sha256'],current_native_pc_sha256=pc['sha256'],
            live_miss_prompt_policy='allowed-compact-01',native_source='SOURCE-v3.json / strict greedy draft verification',BOARD='NOT_TESTED')
save(PACKAGE/'SOURCE_PINS.json',pins)
for relative,expected in runtime.items():assert sha(PACKAGE/relative)==expected,relative
assert read(PACKAGE/'PC_PREFIX_CONFIG.json')['identity']['executable_sha256']==pc['sha256']
manifest=old
manifest['files']=[dict(path=p.relative_to(PACKAGE).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(PACKAGE.rglob('*'))
                   if p.is_file() and p!=PACKAGE/'MANIFEST.json' and '__pycache__' not in p.parts]
save(PACKAGE/'MANIFEST.json',manifest);verify_package(PACKAGE)
result=dict(status='PASS_EXPLICIT_A53_ARTIFACT_BINDING',before_arm_sha256=before,after_arm_sha256=arm['sha256'],
            PC_binary_unchanged=pc['sha256'],runtime_helpers_unchanged=True,PC_input_config_unchanged=True,
            runtime_files_verified=len(runtime),BOARD='NOT_TESTED')
save(EV/'ARM_A53_REBOUND.json',result);print(json.dumps(result,indent=2))
