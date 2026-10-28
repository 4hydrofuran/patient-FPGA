"""Candidate static selftest only; never loads ARM libraries or opens a device."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys


def verify(root):
    root=Path(root).resolve();m=json.loads((root/'manifest.json').read_text())
    declared=set()
    for entry in m['files']:
        name=entry['path'];parts=PurePosixPath(name).parts
        if not name or '\\' in name or PurePosixPath(name).is_absolute() or '..' in parts:
            raise ValueError('unsafe manifest path')
        p=root/name
        if any(q.is_symlink() for q in (p,*p.parents) if q!=root and root in q.parents):
            raise ValueError('symlink payload')
        if name in declared or name=='manifest.json':raise ValueError('duplicate/self manifest')
        declared.add(name)
        if p.stat().st_size!=entry['bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('payload hash differs: '+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    if actual!=declared:raise ValueError('missing/extra payload')
    cfg=json.loads((root/'config/backend.pending.json').read_text())
    if cfg['allow_device_access'] is not False or cfg['fallback']!='disabled':raise ValueError('candidate default must deny device access')
    if m.get('authorization_included') is not False or m['tests']['board']['status']!='NOT_TESTED':
        raise ValueError('unproved board authorization/status')
    return dict(status='PASS_STATIC_CANDIDATE_ONLY',files=len(declared),BOARD='NOT_TESTED')


if __name__=='__main__':print(json.dumps(verify(Path(__file__).resolve().parents[1])))
