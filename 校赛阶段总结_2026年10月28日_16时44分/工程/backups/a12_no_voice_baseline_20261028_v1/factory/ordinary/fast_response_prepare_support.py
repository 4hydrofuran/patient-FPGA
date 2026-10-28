"""Local file verification shared with the fresh entry; contains no device I/O."""
import hashlib
import json
from pathlib import Path


def refresh_bundle_manifest(bundle):
    bundle=Path(bundle)
    p=bundle/'manifest.json';value=json.loads(p.read_text(encoding='utf-8'))
    value['files']=[dict(path=f.relative_to(bundle).as_posix(),bytes=f.stat().st_size,
                         sha256=hashlib.sha256(f.read_bytes()).hexdigest())
        for f in sorted(bundle.rglob('*')) if f.is_file() and f!=p and '__pycache__' not in f.parts]
    p.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')


def verify_package(root):
    root=Path(root).resolve()
    data=json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    if data.get('status')!='UNBOUND' or data.get('authorization_included') is not False:
        raise ValueError('only an unbound package may start')
    for row in data['files']:
        p=root/row['path']
        if not p.is_file() or p.stat().st_size!=row['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:
            raise RuntimeError('package file differs: '+row['path'])
    return data
