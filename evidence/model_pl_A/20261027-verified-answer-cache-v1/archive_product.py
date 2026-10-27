"""Archive the final tested local package and verify each written payload."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3];EV=Path(__file__).resolve().parent
RELEASE=ROOT/'release/a12_verified_answer_cache_20261027';PACKAGE=RELEASE/'hybrid34-threads2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
manifest=read(PACKAGE/'MANIFEST.json');parent=ROOT/'release/a12_fast_response_20261027_v2/short34-threads2'
old={r['path']:r for r in read(parent/'MANIFEST.json')['files']}
changes=dict(added=[],modified=[],public_contract_changes=[],hardware_or_native_changes=[])
for r in manifest['files']:
    if r['path'] not in old:changes['added'].append(r['path'])
    elif r['sha256']!=old[r['path']]['sha256']:
        changes['modified'].append(dict(path=r['path'],before=old[r['path']]['sha256'],after=r['sha256']))
        if '/contracts/qwen35/' in r['path']:changes['public_contract_changes'].append(r['path'])
        if any(x in r['path'] for x in ('/bin/','/hardware/','/w4a8.xclbin')):changes['hardware_or_native_changes'].append(r['path'])
assert not changes['public_contract_changes'] and not changes['hardware_or_native_changes']
(RELEASE/'CHANGES.json').write_text(json.dumps(changes,indent=2)+'\n',encoding='utf-8')
archive=RELEASE/'a12-verified-answer-cache-hybrid34-t2.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for r in manifest['files']:z.write(PACKAGE/r['path'],'hybrid34-threads2/'+r['path'])
    z.write(PACKAGE/'MANIFEST.json','hybrid34-threads2/MANIFEST.json')
with zipfile.ZipFile(archive) as z:
    for r in manifest['files']:
        data=z.read('hybrid34-threads2/'+r['path'])
        assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256'],r['path']
    assert z.read('hybrid34-threads2/MANIFEST.json')==(PACKAGE/'MANIFEST.json').read_bytes()
result=dict(status='PASS_PRODUCT_ZIP_CRC_SHA_READBACK',path=archive.relative_to(ROOT).as_posix(),
    bytes=archive.stat().st_size,sha256=sha(archive),verified_payload_files=len(manifest['files']),
    authorization_included=False,model_weights_included=False,BOARD='NOT_TESTED')
(RELEASE/'ARCHIVE.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
(EV/'ARCHIVE.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))
