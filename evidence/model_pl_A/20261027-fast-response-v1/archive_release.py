"""Create and reread only the sealed new release packages."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[3]
release=ROOT/'release/a12_fast_response_20261027_v2'
rows=[]
for package in sorted(p for p in release.iterdir() if p.is_dir()):
    manifest=json.loads((package/'MANIFEST.json').read_text(encoding='utf-8'))
    archive=release/(package.name+'.zip')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for row in manifest['files']:
            z.write(package/row['path'],package.name+'/'+row['path'])
        z.write(package/'MANIFEST.json',package.name+'/MANIFEST.json')
    with zipfile.ZipFile(archive) as z:
        for row in manifest['files']:
            payload=z.read(package.name+'/'+row['path'])
            if len(payload)!=row['bytes'] or hashlib.sha256(payload).hexdigest()!=row['sha256']:
                raise RuntimeError('new archive differs: '+row['path'])
        if z.read(package.name+'/MANIFEST.json')!=(package/'MANIFEST.json').read_bytes():raise RuntimeError('archive manifest differs')
    rows.append(dict(profile_id=package.name,path=archive.relative_to(ROOT).as_posix(),bytes=archive.stat().st_size,
        sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),payload_files_verified=len(manifest['files']),
        CRC_and_SHA_readback='PASS',authorization_included=False,BOARD='NOT_TESTED'))
(release/'ARCHIVES.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
(Path(__file__).with_name('ARCHIVES.json')).write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,indent=2))
