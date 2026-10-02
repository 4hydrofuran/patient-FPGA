"""Copy existing hash-pinned assets for same-machine local verification only.

No downloads. This does not grant model redistribution or legal clearance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-voice-root',type=Path,required=True)
    parser.add_argument('--target-runtime',type=Path,required=True)
    args=parser.parse_args(); source=args.source_voice_root.resolve(); target=args.target_runtime.resolve()
    if source==target:parser.error('Use a separate installed runtime')
    if not (target/'installation.json').is_file():parser.error('Target must be an installed private runtime')
    rows=[]
    for kind in ('asr','tts'):
        lock=ROOT/f'assets/{kind}/model.lock.json'
        if (target/f'assets/{kind}/model.lock.json').read_bytes()!=lock.read_bytes():raise ValueError('Runtime asset lock differs')
        rows.extend(json.loads(lock.read_text('utf-8'))['files'])
    # Validate every source and every destination before copying anything.
    for row in rows:
        name=row['path']; src=source/name; dest=target/name
        if not name.startswith(('assets/asr/','assets/tts/')) or '\\' in name or '..' in name.split('/') or ':' in name:
            raise ValueError('Unsafe asset lock path')
        if src.is_symlink() or not src.resolve().is_relative_to(source):raise ValueError('Unsafe source asset')
        if dest.exists():raise FileExistsError('Refusing to overwrite runtime assets')
        if src.stat().st_size!=row['bytes'] or hashlib.sha256(src.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Local asset differs from pinned hash')
    for row in rows:
        dest=target/row['path']; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/row['path'],dest)
    (target/'local_assets.json').write_text(json.dumps(dict(scope='SAME_MACHINE_LOCAL_VERIFICATION_ONLY',
        redistribution='NOT_APPROVED',files=rows),indent=2)+'\n',encoding='utf-8')
    print('Existing pinned assets copied to private local runtime; sealed package contains no model weights.')


if __name__=='__main__':main()
